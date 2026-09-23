"""Transactional local allocation for persisted WARDOGS lobbies.

No WDRCON request or Squad allocation callback is made here.
"""

import json
import time
from datetime import datetime, timezone

from services.wardogs_lobby import clear_wardogs_observation, validate_lobby


HEALTH_MAX_AGE_SECONDS = 300


def _owned_lobby(conn, lobby_id):
    row = conn.execute(
        'SELECT schema_version, roster_json FROM wardogs_lobbies WHERE lobby_id=?',
        (lobby_id,),
    ).fetchone()
    if row is None:
        raise ValueError('WARDOGS lobby not found')
    if row['schema_version'] != 1:
        raise ValueError('Unsupported WARDOGS lobby version')
    return validate_lobby(json.loads(row['roster_json']))


def _reserved_owner(conn, server_id, lobby_id):
    rows = conn.execute(
        "SELECT lobby_id FROM server_allocations WHERE server_id=? AND state='reserved'",
        (server_id,),
    ).fetchall()
    return len(rows) == 1 and rows[0]['lobby_id'] == lobby_id


def allocate_wardogs_server_for_lobby(get_db_connection, lobby_id):
    """Return a server ID, or None when no compatible server is free.

    The registry reservation, history row, and lobby association commit together.
    BEGIN IMMEDIATE serializes competing allocators even after a process restart.
    """
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        lobby = _owned_lobby(conn, lobby_id)
        owners = conn.execute(
            "SELECT id, game_type, current_lobby_id FROM servers WHERE current_lobby_id=?",
            (lobby_id,),
        ).fetchall()
        associated_id = lobby.get('serverId')
        if associated_id is not None:
            if (len(owners) != 1 or owners[0]['id'] != associated_id
                    or owners[0]['game_type'] != 'wardogs'
                    or not _reserved_owner(conn, associated_id, lobby_id)):
                raise ValueError('WARDOGS allocation ownership is inconsistent')
            return associated_id
        if owners:
            raise ValueError('WARDOGS allocation ownership is inconsistent')

        now = time.time()
        row = conn.execute("""
            SELECT s.id FROM servers s
            WHERE s.game_type='wardogs' AND s.enabled=1
              AND s.status='healthy' AND s.last_health_status='healthy'
              AND s.last_health_check_at >= ?
              AND s.approved_at IS NOT NULL
              AND (s.current_lobby_id IS NULL OR s.current_lobby_id='')
              AND NOT EXISTS (
                  SELECT 1 FROM server_allocations a
                  WHERE a.server_id=s.id AND a.state='reserved'
              )
            ORDER BY s.id LIMIT 1
        """, (now - HEALTH_MAX_AGE_SECONDS,)).fetchone()
        if row is None:
            return None
        server_id = row['id']
        changed = conn.execute("""
            UPDATE servers SET current_lobby_id=?, status='reserved',
                reserved_at=?, updated_at=?
            WHERE id=? AND (current_lobby_id IS NULL OR current_lobby_id='')
        """, (lobby_id, now, now, server_id)).rowcount
        if changed != 1:
            raise ValueError('WARDOGS server reservation changed concurrently')
        conn.execute("""
            INSERT INTO server_allocations (server_id, lobby_id, state, reserved_at)
            VALUES (?, ?, 'reserved', ?)
        """, (server_id, lobby_id, now))
        lobby['serverId'] = server_id
        conn.execute("""
            UPDATE wardogs_lobbies SET roster_json=?, updated_at=? WHERE lobby_id=?
        """, (json.dumps(lobby, ensure_ascii=True, sort_keys=True),
              datetime.now(timezone.utc).isoformat(), lobby_id))
        return server_id


def cleanup_wardogs_lobby(get_db_connection, lobby_id):
    """Explicit admin cleanup only; never called by disconnects or probes."""
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        lobby = _owned_lobby(conn, lobby_id)
        server_id = lobby.get('serverId')
        if server_id is None and conn.execute(
            'SELECT 1 FROM servers WHERE current_lobby_id=?', (lobby_id,)
        ).fetchone():
            raise ValueError('WARDOGS allocation ownership is inconsistent')
        if server_id is not None:
            server = conn.execute(
                'SELECT * FROM servers WHERE id=?', (server_id,)
            ).fetchone()
            if (server is None or server['game_type'] != 'wardogs'
                    or server['current_lobby_id'] != lobby_id
                    or not _reserved_owner(conn, server_id, lobby_id)):
                raise ValueError('WARDOGS allocation ownership is inconsistent')
            now = time.time()
            conn.execute("""
                UPDATE server_allocations SET state='released', released_at=?,
                    release_reason='wardogs_lobby_cleanup'
                WHERE server_id=? AND lobby_id=? AND state='reserved'
            """, (now, server_id, lobby_id))
            conn.execute("""
                UPDATE servers SET current_lobby_id=NULL, reserved_at=NULL,
                    status=?, updated_at=? WHERE id=?
            """, (server['last_health_status'] if server['enabled'] else 'disabled',
                  now, server_id))
        conn.execute('DELETE FROM wardogs_lobbies WHERE lobby_id=?', (lobby_id,))
        clear_wardogs_observation(lobby_id, server_id)
        return server_id
