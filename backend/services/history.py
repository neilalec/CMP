import json
from typing import Any


def _to_json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=True, sort_keys=True)


def _from_json(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def init_history_tables(get_db_connection):
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS lobby_audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lobby_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                created_at REAL NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_lobby_audit_events_lobby_created
            ON lobby_audit_events (lobby_id, created_at DESC)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS completed_matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lobby_id TEXT NOT NULL UNIQUE,
                selected_map TEXT NOT NULL DEFAULT '',
                server_name TEXT NOT NULL DEFAULT '',
                created_at REAL,
                live_started_at REAL,
                completed_at REAL NOT NULL,
                players_json TEXT NOT NULL DEFAULT '[]',
                teams_json TEXT NOT NULL DEFAULT '{}',
                server_details_json TEXT NOT NULL DEFAULT '{}',
                round_result_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_completed_matches_completed_at
            ON completed_matches (completed_at DESC)
        """)
        conn.commit()


def record_lobby_event(get_db_connection, lobby_id, event_type, payload=None, *, created_at):
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO lobby_audit_events (lobby_id, event_type, created_at, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (lobby_id, event_type, created_at, _to_json(payload))
        )
        conn.commit()


def save_completed_match(get_db_connection, lobby_id, lobby, *, completed_at):
    players = list(lobby.get('players') or [])
    teams = dict(lobby.get('teams') or {})
    server_details = dict(lobby.get('server_details') or {})
    round_result = dict(lobby.get('round_result') or {})
    selected_map = str(lobby.get('selected_map') or '')
    server_name = str(
        server_details.get('serverName')
        or server_details.get('bridge', {}).get('serverName')
        or ''
    )

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO completed_matches (
                lobby_id,
                selected_map,
                server_name,
                created_at,
                live_started_at,
                completed_at,
                players_json,
                teams_json,
                server_details_json,
                round_result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(lobby_id) DO UPDATE SET
                selected_map = excluded.selected_map,
                server_name = excluded.server_name,
                created_at = excluded.created_at,
                live_started_at = excluded.live_started_at,
                completed_at = excluded.completed_at,
                players_json = excluded.players_json,
                teams_json = excluded.teams_json,
                server_details_json = excluded.server_details_json,
                round_result_json = excluded.round_result_json
            """,
            (
                lobby_id,
                selected_map,
                server_name,
                lobby.get('created_at'),
                lobby.get('live_started_at'),
                completed_at,
                _to_json(players),
                _to_json(teams),
                _to_json(server_details),
                _to_json(round_result)
            )
        )
        conn.commit()


def fetch_completed_matches(get_db_connection, *, limit=20):
    with get_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                id,
                lobby_id,
                selected_map,
                server_name,
                created_at,
                live_started_at,
                completed_at,
                players_json,
                teams_json,
                server_details_json,
                round_result_json
            FROM completed_matches
            ORDER BY completed_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

    matches = []
    for row in rows:
        matches.append({
            'id': row['id'],
            'lobby_id': row['lobby_id'],
            'selected_map': row['selected_map'],
            'server_name': row['server_name'],
            'created_at': row['created_at'],
            'live_started_at': row['live_started_at'],
            'completed_at': row['completed_at'],
            'players': _from_json(row['players_json'], []),
            'teams': _from_json(row['teams_json'], {}),
            'server_details': _from_json(row['server_details_json'], {}),
            'round_result': _from_json(row['round_result_json'], {})
        })
    return matches


def fetch_lobby_audit_events(get_db_connection, *, lobby_id=None, limit=30):
    with get_db_connection() as conn:
        if lobby_id:
            rows = conn.execute(
                """
                SELECT id, lobby_id, event_type, created_at, payload_json
                FROM lobby_audit_events
                WHERE lobby_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (lobby_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, lobby_id, event_type, created_at, payload_json
                FROM lobby_audit_events
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            ).fetchall()

    events = []
    for row in rows:
        events.append({
            'id': row['id'],
            'lobby_id': row['lobby_id'],
            'event_type': row['event_type'],
            'created_at': row['created_at'],
            'payload': _from_json(row['payload_json'], {})
        })
    return events


def get_history_counts(get_db_connection):
    with get_db_connection() as conn:
        match_count = conn.execute('SELECT COUNT(*) FROM completed_matches').fetchone()[0]
        event_count = conn.execute('SELECT COUNT(*) FROM lobby_audit_events').fetchone()[0]
    return {
        'completedMatches': match_count,
        'lobbyEvents': event_count
    }


def build_admin_diagnostics(
    *,
    get_database_health,
    get_bridge_health,
    get_server_connection_details,
    fetch_latest_round_result,
    fetch_lobby_audit_events,
    get_history_counts,
    lobbies,
    queue_modes,
    matchmaking_queue,
    pending_match,
    servers
):
    try:
        server_details = get_server_connection_details()
    except Exception as error:
        server_details = {'bridgeAvailable': False, 'bridgeError': str(error)}

    try:
        latest_round_result = fetch_latest_round_result()
    except Exception as error:
        latest_round_result = {'error': str(error)}

    active_lobbies = []
    for lobby_id, lobby in lobbies.items():
        active_lobbies.append({
            'lobby_id': lobby_id,
            'step': lobby.get('step'),
            'players': len(lobby.get('players') or []),
            'selected_map': lobby.get('selected_map'),
            'announcement': lobby.get('announcement'),
            'live_roll_done': bool(lobby.get('live_roll_done')),
            'server_details_provided_at': lobby.get('server_details_provided_at'),
            'live_started_at': lobby.get('live_started_at')
        })

    queue_state = {}
    total_queue_size = 0
    first_pending_match = None
    for mode_id, config in queue_modes.items():
        size = len(matchmaking_queue.get(mode_id, []))
        total_queue_size += size
        mode_pending = pending_match.get(mode_id)
        pending_payload = {
            'id': mode_pending.get('id'),
            'acceptedCount': len([player for player, accepted in (mode_pending.get('accepted') or {}).items() if accepted]),
            'requiredCount': len(mode_pending.get('players') or []),
            'countdown': mode_pending.get('countdown')
        } if mode_pending else None
        if pending_payload and not first_pending_match:
            first_pending_match = {
                **pending_payload,
                'queueMode': mode_id,
                'label': config['label']
            }
        queue_state[mode_id] = {
            'label': config['label'],
            'size': size,
            'maxPlayers': config['max_players'],
            'teamSize': config['team_size'],
            'pendingMatch': pending_payload
        }

    return {
        'generatedAt': __import__('time').time(),
        'database': get_database_health(),
        'bridge': get_bridge_health(),
        'server': server_details,
        'latestRoundResult': latest_round_result,
        'queueSize': total_queue_size,
        'pendingMatch': first_pending_match,
        'queueModes': queue_state,
        'activeLobbies': active_lobbies,
        'historyCounts': get_history_counts(),
        'recentEvents': fetch_lobby_audit_events(limit=20),
        'servers': servers or []
    }
