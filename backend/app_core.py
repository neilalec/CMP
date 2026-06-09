import json
import logging
import os
import sqlite3

from app_state import (
    ADMIN_STEAM_IDS,
    BASE_DIR,
    BRIDGE_ERROR_LOG_INTERVAL_SECONDS,
    DATABASE_PATH,
    DEFAULT_QUEUE_MODE,
    DEV_LIVE_ROLL_OVERRIDE_USERNAME,
    LEGACY_QUEUE_FILE,
    LEGACY_USERS_FILE,
    LIVE_ROLL_POLL_SECONDS,
    LIVE_ROLL_RETRY_SECONDS,
    LIVE_ROLL_READY_GRACE_SECONDS,
    LIVE_ROLL_READY_RATIO,
    LIVE_ROLL_TEAM_SWAP_RETRY_SECONDS,
    QUEUE_MODES,
    SQUAD_SERVER_CONNECT_ADDRESS,
    SQUAD_SERVER_NAME,
    SQUAD_SERVER_PASSWORD,
    SQUADJS_BRIDGE_TOKEN,
    SQUADJS_BRIDGE_URL,
    bridge_status,
    groups,
    lobbies,
    matchmaking_queue,
    pending_match,
    player_activity,
    queue_lock,
    user_to_group,
    users,
)
from services.bridge import (
    build_lobby_server_presence as build_lobby_server_presence_service,
    build_server_connection_details as build_server_connection_details_service,
    broadcast_server_message as broadcast_server_message_service,
    change_server_to_selected_map as change_server_to_selected_map_service,
    force_team_change as force_team_change_service,
    fetch_latest_round_result as fetch_latest_round_result_service,
    get_server_layer_status as get_server_layer_status_service,
    get_bridge_health as get_bridge_health_service,
    get_database_health as get_database_health_service,
    set_next_server_map as set_next_server_map_service,
    squadjs_bridge_request as squadjs_bridge_request_service
)
from services.auth_security import hash_password, needs_password_rehash
from services.live_roll import start_live_roll_monitor as start_live_roll_monitor_service
from services.history import (
    build_admin_diagnostics as build_admin_diagnostics_service,
    fetch_completed_matches as fetch_completed_matches_service,
    fetch_lobby_audit_events as fetch_lobby_audit_events_service,
    get_history_counts as get_history_counts_service,
    init_history_tables as init_history_tables_service,
    record_lobby_event as record_lobby_event_service,
    save_completed_match as save_completed_match_service
)
from services.profile import (
    build_profile_status as build_profile_status_service,
    get_user_profile as get_user_profile_service,
    is_valid_steam_id as is_valid_steam_id_service,
    update_steam_id as update_steam_id_service
)
from services.server_registry import (
    allocate_server_for_lobby as allocate_server_for_lobby_service,
    approve_server as approve_server_service,
    build_bridge_request_for_server,
    build_steam_lobby_join_url as build_steam_lobby_join_url_service,
    build_squad_join_url as build_squad_join_url_service,
    create_server as create_server_registry_service,
    get_server_by_id as get_server_by_id_service,
    get_server_pool_capacity as get_server_pool_capacity_service,
    init_server_registry_tables as init_server_registry_tables_service,
    list_available_servers as list_available_servers_service,
    list_servers as list_servers_service,
    release_server_allocation as release_server_allocation_service,
    run_server_health_check as run_server_health_check_service,
    set_server_enabled as set_server_enabled_service,
    test_server_connection as test_server_connection_service,
)
from state.lobby import is_user_in_any_lobby
from state.runtime import pause_aware_sleep


def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password TEXT NOT NULL,
                steam_id TEXT NOT NULL DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS queue_entries (
                mode TEXT NOT NULL DEFAULT 'skirmish',
                position INTEGER NOT NULL,
                username TEXT NOT NULL UNIQUE,
                PRIMARY KEY (mode, position)
            )
        """)
        columns = {
            row['name']
            for row in conn.execute("PRAGMA table_info(queue_entries)").fetchall()
        }
        if 'mode' not in columns:
            conn.execute(
                "ALTER TABLE queue_entries ADD COLUMN mode TEXT NOT NULL DEFAULT 'skirmish'"
            )
        conn.commit()
    init_history_tables_service(get_db_connection)
    init_server_registry_tables_service(get_db_connection)


def get_secret_key():
    import app as backend_app
    return backend_app.app.config.get('SECRET_KEY', 'cmp-dev-secret')


def normalize_user_record(record):
    if isinstance(record, dict):
        return {
            'password': record.get('password', ''),
            'steam_id': str(record.get('steam_id', '') or '').strip()
        }
    return {
        'password': record,
        'steam_id': ''
    }


def migrate_legacy_json_files():
    bootstrap_logger = logging.getLogger(__name__)
    with get_db_connection() as conn:
        user_count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        queue_count = conn.execute('SELECT COUNT(*) FROM queue_entries').fetchone()[0]

        if user_count == 0 and os.path.exists(LEGACY_USERS_FILE):
            try:
                with open(LEGACY_USERS_FILE, 'r', encoding='utf-8') as f:
                    legacy_users = json.load(f)
                rows = []
                for username, record in legacy_users.items():
                    normalized = normalize_user_record(record)
                    rows.append((username, normalized.get('password', ''), normalized.get('steam_id', '')))
                conn.executemany(
                    'INSERT OR REPLACE INTO users (username, password, steam_id) VALUES (?, ?, ?)',
                    rows
                )
                bootstrap_logger.info(f"Migrated {len(rows)} users from legacy JSON store")
            except Exception as e:
                bootstrap_logger.error(f"Failed to migrate legacy users.json: {str(e)}")

        if queue_count == 0 and os.path.exists(LEGACY_QUEUE_FILE):
            try:
                with open(LEGACY_QUEUE_FILE, 'r', encoding='utf-8') as f:
                    legacy_queue = json.load(f)
                rows = [(index, username) for index, username in enumerate(legacy_queue)]
                conn.executemany(
                    'INSERT OR REPLACE INTO queue_entries (position, username) VALUES (?, ?)',
                    rows
                )
                bootstrap_logger.info(f"Migrated {len(rows)} queued players from legacy JSON store")
            except Exception as e:
                bootstrap_logger.error(f"Failed to migrate legacy queue.json: {str(e)}")

        conn.commit()


def load_users():
    try:
        with get_db_connection() as conn:
            rows = conn.execute(
                'SELECT username, password, steam_id FROM users ORDER BY username'
            ).fetchall()
            return {
                row['username']: {
                    'password': row['password'],
                    'steam_id': row['steam_id'] or ''
                }
                for row in rows
            }
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to load users from SQLite: {str(e)}")
        return {}


def save_users():
    try:
        with get_db_connection() as conn:
            conn.execute('DELETE FROM users')
            conn.executemany(
                'INSERT INTO users (username, password, steam_id) VALUES (?, ?, ?)',
                [
                    (
                        username,
                        normalize_user_record(record).get('password', ''),
                        normalize_user_record(record).get('steam_id', '')
                    )
                    for username, record in users.items()
                ]
            )
            conn.commit()
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to save users to SQLite: {str(e)}")


def migrate_plaintext_passwords():
    migrated_count = 0
    for username, record in list(users.items()):
        normalized = normalize_user_record(record)
        if needs_password_rehash(normalized.get('password')):
            normalized['password'] = hash_password(normalized.get('password'))
            users[username] = normalized
            migrated_count += 1

    if migrated_count:
        save_users()
        logging.getLogger(__name__).info(f"Migrated {migrated_count} plaintext passwords to password hashes")


def initialize_state():
    init_database()
    migrate_legacy_json_files()
    users.clear()
    users.update({
        username: normalize_user_record(record)
        for username, record in load_users().items()
    })
    migrate_plaintext_passwords()
    loaded_queues = load_queue()
    matchmaking_queue.clear()
    matchmaking_queue.update({
        mode_id: list(loaded_queues.get(mode_id, []))
        for mode_id in QUEUE_MODES
    })


def load_queue():
    queues = {mode_id: [] for mode_id in QUEUE_MODES}
    with queue_lock:
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    'SELECT mode, username FROM queue_entries ORDER BY mode ASC, position ASC'
                ).fetchall()
                for row in rows:
                    mode = row['mode'] if row['mode'] in QUEUE_MODES else DEFAULT_QUEUE_MODE
                    queues.setdefault(mode, []).append(row['username'])
                return queues
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to load queue from SQLite: {str(e)}")
            return queues


def get_user_record(username):
    record = users.get(username)
    if record is None:
        return None
    normalized = normalize_user_record(record)
    if normalized != record:
        users[username] = normalized
        save_users()
    return normalized


def user_has_steam_id(username):
    record = get_user_record(username)
    return bool(record and record.get('steam_id'))


def get_user_profile(username):
    from app import matchmaking_queue as queue_ref
    queued_users = {
        queued_username
        for members in queue_ref.values()
        for queued_username in members
    }
    return get_user_profile_service(
        username,
        get_user_record,
        queued_users,
        is_user_in_any_lobby,
        ADMIN_STEAM_IDS
    )


def is_admin_user(username):
    profile = get_user_profile(username)
    return bool(profile and profile.get('is_admin'))


def is_valid_steam_id(steam_id):
    return is_valid_steam_id_service(steam_id)


def squadjs_bridge_request(path, method='GET', payload=None, timeout=5):
    return squadjs_bridge_request_service(
        path=path,
        bridge_url=SQUADJS_BRIDGE_URL,
        bridge_token=SQUADJS_BRIDGE_TOKEN,
        payload=payload,
        method=method,
        timeout=timeout,
        bridge_status=bridge_status,
        error_log_interval_seconds=BRIDGE_ERROR_LOG_INTERVAL_SECONDS
    )


def get_bridge_request_for_server(*, server_id=None, lobby_id=None):
    if lobby_id:
        server_id = (lobbies.get(lobby_id) or {}).get('server_id')
    if server_id:
        server = get_server_by_id(server_id, include_secret=True)
        if server:
            return build_bridge_request_for_server(server)
    return squadjs_bridge_request


def get_database_health():
    return get_database_health_service(get_db_connection, DATABASE_PATH)


def get_bridge_health(server_id=None):
    server = get_server_by_id(server_id) if server_id else None
    return get_bridge_health_service(
        get_bridge_request_for_server(server_id=server_id),
        (server or {}).get('bridge_url') or SQUADJS_BRIDGE_URL
    )


def get_server_connection_details(server_id=None, lobby_id=None):
    server = get_server_by_id(server_id) if server_id else None
    return build_server_connection_details_service(
        bridge_request=get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id),
        configured_name=(server or {}).get('display_name') or SQUAD_SERVER_NAME,
        password=(server or {}).get('join_password') or SQUAD_SERVER_PASSWORD,
        connect_address=(server or {}).get('connect_address') or SQUAD_SERVER_CONNECT_ADDRESS
    )


def change_server_to_selected_map(selected_map, server_id=None, lobby_id=None):
    return change_server_to_selected_map_service(
        selected_map,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def set_next_server_map(selected_map, server_id=None, lobby_id=None):
    return set_next_server_map_service(
        selected_map,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def force_player_to_expected_team(steam_id, server_id=None, lobby_id=None):
    return force_team_change_service(
        steam_id,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def get_server_layer_status(selected_map, server_id=None, lobby_id=None):
    return get_server_layer_status_service(
        selected_map,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def fetch_latest_round_result(server_id=None, lobby_id=None):
    return fetch_latest_round_result_service(
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def record_lobby_event(lobby_id, event_type, payload=None, *, created_at):
    return record_lobby_event_service(
        get_db_connection,
        lobby_id,
        event_type,
        payload,
        created_at=created_at
    )


def save_completed_match(lobby_id, lobby, *, completed_at):
    result = save_completed_match_service(
        get_db_connection,
        lobby_id,
        lobby,
        completed_at=completed_at
    )
    release_server_allocation(lobby_id, reason='match_completed')
    return result


def fetch_completed_matches(limit=20):
    return fetch_completed_matches_service(get_db_connection, limit=limit)


def fetch_lobby_audit_events(lobby_id=None, limit=30):
    return fetch_lobby_audit_events_service(get_db_connection, lobby_id=lobby_id, limit=limit)


def get_history_counts():
    return get_history_counts_service(get_db_connection)


def get_admin_diagnostics():
    from app import lobbies as lobbies_ref, matchmaking_queue as queue_ref, pending_match as pending_match_ref
    return build_admin_diagnostics_service(
        get_database_health=get_database_health,
        get_bridge_health=get_bridge_health,
        get_server_connection_details=get_server_connection_details,
        fetch_latest_round_result=fetch_latest_round_result,
        fetch_lobby_audit_events=fetch_lobby_audit_events,
        get_history_counts=get_history_counts,
        lobbies=lobbies_ref,
        queue_modes=QUEUE_MODES,
        matchmaking_queue=queue_ref,
        pending_match=pending_match_ref,
        servers=list_servers()
    )


def list_servers():
    return list_servers_service(get_db_connection, get_secret_key())


def get_server_by_id(server_id, include_secret=False):
    return get_server_by_id_service(get_db_connection, server_id, get_secret_key(), include_secret=include_secret)


def create_server(payload, submitted_by=''):
    return create_server_registry_service(get_db_connection, get_secret_key(), payload, submitted_by=submitted_by)


def test_server_connection(payload):
    return test_server_connection_service(payload)


def run_server_health_check(server_id):
    return run_server_health_check_service(get_db_connection, get_secret_key(), server_id)


def set_server_enabled(server_id, enabled):
    return set_server_enabled_service(get_db_connection, get_secret_key(), server_id, enabled)


def approve_server(server_id, approved_by):
    return approve_server_service(get_db_connection, get_secret_key(), server_id, approved_by)


def list_available_servers():
    return list_available_servers_service(get_db_connection, get_secret_key())


def get_server_pool_capacity():
    return get_server_pool_capacity_service(get_db_connection, get_secret_key())


def allocate_server_for_lobby(lobby_id):
    return allocate_server_for_lobby_service(get_db_connection, get_secret_key(), lobby_id)


def release_server_allocation(lobby_id, reason='released'):
    return release_server_allocation_service(get_db_connection, get_secret_key(), lobby_id, reason)


def build_lobby_join_url(lobby_id):
    lobby = lobbies.get(lobby_id) or {}
    server_details = lobby.get('server_details') or {}
    steam_lobby_id = server_details.get('steamLobbyId') or server_details.get('steam_lobby_id') or ''
    if steam_lobby_id:
        return build_steam_lobby_join_url_service(steam_lobby_id)
    connect_address = server_details.get('connectAddress') or server_details.get('ip') or ''
    join_password = server_details.get('password') or ''
    return build_squad_join_url_service(connect_address, join_password)


def broadcast_server_message(message, server_id=None, lobby_id=None):
    return broadcast_server_message_service(
        message,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=False):
    from app import lobbies as lobbies_ref
    return build_lobby_server_presence_service(
        lobby_id=lobby_id,
        lobbies=lobbies_ref,
        get_user_profile=get_user_profile,
        bridge_request=get_bridge_request_for_server(lobby_id=lobby_id),
        tolerate_bridge_unavailable=tolerate_bridge_unavailable
    )


def start_live_roll_monitor(lobby_id):
    from app import socketio, lobbies as lobbies_ref, logger, DEV_MODE as dev_mode
    return start_live_roll_monitor_service(
        lobby_id=lobby_id,
        lobbies=lobbies_ref,
        socketio=socketio,
        build_lobby_server_presence=build_lobby_server_presence,
        pause_aware_sleep=pause_aware_sleep,
        broadcast_server_message=lambda message: broadcast_server_message(message, lobby_id=lobby_id),
        change_server_to_selected_map=lambda selected_map: change_server_to_selected_map(selected_map, lobby_id=lobby_id),
        set_next_server_map=lambda selected_map: set_next_server_map(selected_map, lobby_id=lobby_id),
        force_player_to_expected_team=lambda steam_id: force_player_to_expected_team(steam_id, lobby_id=lobby_id),
        get_server_layer_status=lambda selected_map: get_server_layer_status(selected_map, lobby_id=lobby_id),
        get_server_connection_details=lambda: get_server_connection_details(lobby_id=lobby_id),
        fetch_latest_round_result=lambda: fetch_latest_round_result(lobby_id=lobby_id),
        record_lobby_event=record_lobby_event,
        save_completed_match=save_completed_match,
        ready_ratio=LIVE_ROLL_READY_RATIO,
        ready_grace_seconds=LIVE_ROLL_READY_GRACE_SECONDS,
        poll_seconds=LIVE_ROLL_POLL_SECONDS,
        retry_seconds=LIVE_ROLL_RETRY_SECONDS,
        team_swap_retry_seconds=LIVE_ROLL_TEAM_SWAP_RETRY_SECONDS,
        dev_mode=dev_mode,
        dev_override_username=DEV_LIVE_ROLL_OVERRIDE_USERNAME,
        logger=logger
    )
