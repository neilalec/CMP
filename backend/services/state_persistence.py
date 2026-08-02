import json
import time
from typing import Any


def _json_safe(value: Any):
    if isinstance(value, set):
        return sorted(_json_safe(item) for item in value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _json_safe(item)
            for key, item in value.items()
        }
    return value


def _to_json(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=True, sort_keys=True)


def _from_json(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def init_runtime_state_tables(get_db_connection):
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_lobbies (
                lobby_id TEXT PRIMARY KEY,
                updated_at REAL NOT NULL,
                lobby_json TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS active_groups (
                code TEXT PRIMARY KEY,
                updated_at REAL NOT NULL,
                group_json TEXT NOT NULL
            )
        """)
        conn.commit()


def _restore_lobby(lobby_id, payload):
    lobby = dict(payload or {})
    lobby['lobby_id'] = str(lobby.get('lobby_id') or lobby_id)
    lobby['players'] = list(lobby.get('players') or [])
    lobby['teams'] = {
        'team1': list((lobby.get('teams') or {}).get('team1') or []),
        'team2': list((lobby.get('teams') or {}).get('team2') or [])
    }
    lobby['captains'] = lobby.get('captains') or {'team1': None, 'team2': None}
    lobby['map_votes'] = dict(lobby.get('map_votes') or {})
    lobby['vote_counts'] = dict(lobby.get('vote_counts') or {})
    lobby['map_pool'] = list(lobby.get('map_pool') or [])
    lobby['player_groups'] = dict(lobby.get('player_groups') or {})
    lobby['server_details'] = dict(lobby.get('server_details') or {})
    lobby['team_labels'] = dict(lobby.get('team_labels') or {})
    lobby['disconnected_players'] = set(lobby.get('disconnected_players') or [])
    lobby['live_roll_team_swap_attempts'] = dict(lobby.get('live_roll_team_swap_attempts') or {})
    lobby.setdefault('step', 2)
    lobby.setdefault('announcement', None)
    lobby.setdefault('round_result', None)
    return lobby


def load_active_lobbies(get_db_connection):
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT lobby_id, lobby_json
            FROM active_lobbies
            ORDER BY updated_at ASC
        """).fetchall()

    lobbies = {}
    for row in rows:
        lobby_id = row['lobby_id']
        lobbies[lobby_id] = _restore_lobby(lobby_id, _from_json(row['lobby_json'], {}))
    return lobbies


def save_active_lobbies(get_db_connection, lobbies, *, now=None):
    updated_at = time.time() if now is None else now
    rows = [
        (lobby_id, updated_at, _to_json(lobby))
        for lobby_id, lobby in (lobbies or {}).items()
    ]
    live_ids = [row[0] for row in rows]

    with get_db_connection() as conn:
        if live_ids:
            placeholders = ','.join('?' for _ in live_ids)
            conn.execute(
                f"DELETE FROM active_lobbies WHERE lobby_id NOT IN ({placeholders})",
                live_ids
            )
        else:
            conn.execute("DELETE FROM active_lobbies")

        conn.executemany(
            """
            INSERT INTO active_lobbies (lobby_id, updated_at, lobby_json)
            VALUES (?, ?, ?)
            ON CONFLICT(lobby_id) DO UPDATE SET
                updated_at = excluded.updated_at,
                lobby_json = excluded.lobby_json
            """,
            rows
        )
        conn.commit()


def _restore_group(code, payload):
    group = dict(payload or {})
    group['code'] = str(group.get('code') or code)
    group['leader'] = str(group.get('leader') or '')
    group['members'] = list(group.get('members') or [])
    return group


def load_active_groups(get_db_connection):
    with get_db_connection() as conn:
        rows = conn.execute("""
            SELECT code, group_json
            FROM active_groups
            ORDER BY updated_at ASC
        """).fetchall()

    groups = {}
    for row in rows:
        code = row['code']
        group = _restore_group(code, _from_json(row['group_json'], {}))
        if group.get('leader') and group.get('members'):
            groups[code] = group
    return groups


def save_active_groups(get_db_connection, groups, *, now=None):
    updated_at = time.time() if now is None else now
    rows = [
        (code, updated_at, _to_json(group))
        for code, group in (groups or {}).items()
    ]
    live_codes = [row[0] for row in rows]

    with get_db_connection() as conn:
        if live_codes:
            placeholders = ','.join('?' for _ in live_codes)
            conn.execute(
                f"DELETE FROM active_groups WHERE code NOT IN ({placeholders})",
                live_codes
            )
        else:
            conn.execute("DELETE FROM active_groups")

        conn.executemany(
            """
            INSERT INTO active_groups (code, updated_at, group_json)
            VALUES (?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                updated_at = excluded.updated_at,
                group_json = excluded.group_json
            """,
            rows
        )
        conn.commit()


def save_runtime_state(get_db_connection, lobbies, groups, *, now=None):
    save_active_lobbies(get_db_connection, lobbies, now=now)
    save_active_groups(get_db_connection, groups, now=now)
