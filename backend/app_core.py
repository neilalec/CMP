import json
import logging
import os
import sqlite3

from app_state import (
    BASE_DIR,
    BRIDGE_ERROR_LOG_INTERVAL_SECONDS,
    DATABASE_PATH,
    LEGACY_QUEUE_FILE,
    LEGACY_USERS_FILE,
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
    broadcast_server_message as broadcast_server_message_service,
    change_server_to_selected_map as change_server_to_selected_map_service,
    get_bridge_health as get_bridge_health_service,
    get_database_health as get_database_health_service,
    squadjs_bridge_request as squadjs_bridge_request_service
)
from services.live_roll import start_live_roll_monitor as start_live_roll_monitor_service
from services.profile import (
    build_profile_status as build_profile_status_service,
    get_user_profile as get_user_profile_service,
    is_valid_steam_id as is_valid_steam_id_service,
    update_steam_id as update_steam_id_service
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
                position INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE
            )
        """)
        conn.commit()


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


def initialize_state():
    init_database()
    migrate_legacy_json_files()
    users.clear()
    users.update({
        username: normalize_user_record(record)
        for username, record in load_users().items()
    })
    matchmaking_queue.clear()
    matchmaking_queue.extend(load_queue())


def load_queue():
    with queue_lock:
        try:
            with get_db_connection() as conn:
                rows = conn.execute(
                    'SELECT username FROM queue_entries ORDER BY position ASC'
                ).fetchall()
                return [row['username'] for row in rows]
        except Exception as e:
            logging.getLogger(__name__).error(f"Failed to load queue from SQLite: {str(e)}")
            return []


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
    return get_user_profile_service(username, get_user_record, queue_ref, is_user_in_any_lobby)


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


def get_database_health():
    return get_database_health_service(get_db_connection, DATABASE_PATH)


def get_bridge_health():
    return get_bridge_health_service(squadjs_bridge_request, SQUADJS_BRIDGE_URL)


def change_server_to_selected_map(selected_map):
    return change_server_to_selected_map_service(selected_map, squadjs_bridge_request)


def broadcast_server_message(message):
    return broadcast_server_message_service(message, squadjs_bridge_request)


def build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=False):
    from app import lobbies as lobbies_ref
    return build_lobby_server_presence_service(
        lobby_id=lobby_id,
        lobbies=lobbies_ref,
        get_user_profile=get_user_profile,
        bridge_request=squadjs_bridge_request,
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
        broadcast_server_message=broadcast_server_message,
        change_server_to_selected_map=change_server_to_selected_map,
        dev_mode=dev_mode,
        logger=logger
    )
