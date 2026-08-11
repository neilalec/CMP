import json
import logging
import os
import sqlite3
import time

from app_state import (
    ADMIN_TEAM_ENFORCEMENT_BYPASS_ENABLED,
    ADMIN_STEAM_IDS,
    AUTOMATION_CONTROL,
    AUTOMATION_MODES,
    BASE_DIR,
    BRIDGE_ERROR_LOG_INTERVAL_SECONDS,
    DATABASE_PATH,
    DEFAULT_QUEUE_MODE,
    DEV_MODE,
    DEV_LIVE_ROLL_OVERRIDE_USERNAME,
    DEV_LIVE_ROLL_OVERRIDE_STEAM_ID,
    FINALIZED_LOBBY_CLEANUP_SECONDS,
    LEGACY_QUEUE_FILE,
    LIVE_MATCH_MAX_SECONDS,
    LEGACY_USERS_FILE,
    LIVE_ROLL_POLL_SECONDS,
    LIVE_ROLL_RETRY_SECONDS,
    LIVE_ROLL_READY_GRACE_SECONDS,
    LIVE_ROLL_READY_OVERRIDE_ENABLED,
    LIVE_ROLL_READY_RATIO,
    LIVE_ROLL_THRESHOLD_GRACE_SECONDS,
    LIVE_ROLL_TEAM_SWAP_RETRY_SECONDS,
    QUEUE_MODES,
    SQUAD_SERVER_CONNECT_ADDRESS,
    SQUAD_SERVER_NAME,
    SQUAD_SERVER_PASSWORD,
    SQUADJS_BRIDGE_TOKEN,
    SQUADJS_BRIDGE_URL,
    bridge_status,
    disabled_queue_modes,
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
    create_synthetic_lobby_join_url as create_synthetic_lobby_join_url_service,
    end_match as end_match_service,
    force_team_change as force_team_change_service,
    fetch_best_round_result as fetch_best_round_result_service,
    fetch_latest_round_result as fetch_latest_round_result_service,
    get_server_layer_status as get_server_layer_status_service,
    get_selected_map_team_labels as get_selected_map_team_labels_service,
    get_bridge_health as get_bridge_health_service,
    get_database_health as get_database_health_service,
    kick_player as kick_player_service,
    register_match_context as register_match_context_service,
    set_server_slomo as set_server_slomo_service,
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
    update_display_name as update_display_name_service,
    update_steam_id as update_steam_id_service
)
from services.server_registry import (
    allocate_server_for_lobby as allocate_server_for_lobby_service,
    approve_server as approve_server_service,
    build_bridge_request_for_server,
    build_join_url_from_server_details as build_join_url_from_server_details_service,
    build_steam_lobby_join_url as build_steam_lobby_join_url_service,
    build_squad_join_url as build_squad_join_url_service,
    build_live_session_snapshot,
    create_server as create_server_registry_service,
    enrich_server_result_with_discovery,
    get_server_by_id as get_server_by_id_service,
    get_eos_runtime_status as get_eos_runtime_status_service,
    get_server_pool_capacity as get_server_pool_capacity_service,
    init_server_registry_tables as init_server_registry_tables_service,
    list_available_servers as list_available_servers_service,
    list_servers as list_servers_service,
    normalize_steam_lobby_id,
    release_server_allocation as release_server_allocation_service,
    run_server_health_check as run_server_health_check_service,
    select_preferred_live_session,
    set_server_enabled as set_server_enabled_service,
    test_server_connection as test_server_connection_service,
)
from services.state_persistence import (
    init_runtime_state_tables as init_runtime_state_tables_service,
    load_active_groups as load_active_groups_service,
    load_active_lobbies as load_active_lobbies_service,
    save_runtime_state as save_runtime_state_service,
)
from state.lobby import is_user_in_any_lobby
from state.runtime import pause_aware_sleep


class AutomationCommandBlocked(RuntimeError):
    pass


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
                steam_id TEXT NOT NULL DEFAULT '',
                display_name TEXT NOT NULL DEFAULT '',
                steam_persona_name TEXT NOT NULL DEFAULT '',
                display_name_source TEXT NOT NULL DEFAULT 'legacy',
                admin_test_mode_disabled INTEGER NOT NULL DEFAULT 0
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
        user_columns = {
            row['name']
            for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if 'display_name' not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
        if 'steam_persona_name' not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN steam_persona_name TEXT NOT NULL DEFAULT ''")
        if 'display_name_source' not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN display_name_source TEXT NOT NULL DEFAULT 'legacy'")
        if 'admin_test_mode_disabled' not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN admin_test_mode_disabled INTEGER NOT NULL DEFAULT 0")
        conn.commit()
    init_history_tables_service(get_db_connection)
    init_server_registry_tables_service(get_db_connection)
    init_runtime_state_tables_service(get_db_connection)


def get_secret_key():
    import app as backend_app
    return backend_app.app.config.get('SECRET_KEY', 'cmp-dev-secret')


def normalize_user_record(record):
    if isinstance(record, dict):
        display_name = str(record.get('display_name', '') or '').strip()
        steam_persona_name = str(record.get('steam_persona_name', '') or '').strip()
        return {
            'password': record.get('password', ''),
            'steam_id': str(record.get('steam_id', '') or '').strip(),
            'display_name': display_name,
            'steam_persona_name': steam_persona_name,
            'display_name_source': str(record.get('display_name_source') or ('steam' if display_name else 'legacy')).strip(),
            'is_admin': bool(record.get('is_admin')),
            'admin_test_mode_disabled': bool(record.get('admin_test_mode_disabled'))
        }
    return {
        'password': record,
        'steam_id': '',
        'display_name': '',
        'steam_persona_name': '',
        'display_name_source': 'legacy',
        'is_admin': False,
        'admin_test_mode_disabled': False
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
                    rows.append((
                        username,
                        normalized.get('password', ''),
                        normalized.get('steam_id', ''),
                        normalized.get('display_name', ''),
                        normalized.get('steam_persona_name', ''),
                        normalized.get('display_name_source', 'legacy'),
                        1 if normalized.get('admin_test_mode_disabled') else 0
                    ))
                conn.executemany(
                    '''
                    INSERT OR REPLACE INTO users
                    (username, password, steam_id, display_name, steam_persona_name, display_name_source, admin_test_mode_disabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''',
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
                '''
                SELECT username, password, steam_id, display_name, steam_persona_name, display_name_source, admin_test_mode_disabled
                FROM users
                ORDER BY username
                '''
            ).fetchall()
            return {
                row['username']: {
                    'password': row['password'],
                    'steam_id': row['steam_id'] or '',
                    'display_name': row['display_name'] or '',
                    'steam_persona_name': row['steam_persona_name'] or '',
                    'display_name_source': row['display_name_source'] or 'legacy',
                    'admin_test_mode_disabled': bool(row['admin_test_mode_disabled'])
                }
                for row in rows
            }
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to load users from SQLite: {str(e)}")
        return {}


def save_users():
    try:
        rows = []
        for username, record in users.items():
            normalized = normalize_user_record(record)
            rows.append((
                username,
                normalized.get('password', ''),
                normalized.get('steam_id', ''),
                normalized.get('display_name', ''),
                normalized.get('steam_persona_name', ''),
                normalized.get('display_name_source', 'legacy'),
                1 if normalized.get('admin_test_mode_disabled') else 0
            ))

        with get_db_connection() as conn:
            conn.execute('DELETE FROM users')
            conn.executemany(
                '''
                INSERT INTO users
                (username, password, steam_id, display_name, steam_persona_name, display_name_source, admin_test_mode_disabled)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ''',
                rows
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
    disabled_queue_modes.clear()
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
    restored_groups = load_active_groups_service(get_db_connection)
    groups.clear()
    groups.update(restored_groups)
    user_to_group.clear()
    for code, group in groups.items():
        for member in group.get('members', []):
            user_to_group[member] = code

    restored_lobbies = load_active_lobbies_service(get_db_connection)
    lobbies.clear()
    lobbies.update(restored_lobbies)


def save_runtime_state():
    return save_runtime_state_service(get_db_connection, lobbies, groups)


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
    if DEV_MODE and str(username or '').strip().lower() == 'sam':
        return True
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


def can_toggle_admin_mode(username):
    profile = get_user_profile(username)
    return bool(profile and profile.get('can_toggle_admin'))


def set_self_admin_mode(username, enabled):
    if not can_toggle_admin_mode(username):
        raise PermissionError('Root admin access required')
    record = get_user_record(username)
    if not record:
        raise ValueError('User not found')
    record['admin_test_mode_disabled'] = not bool(enabled)
    users[username] = record
    save_users()
    return get_user_profile(username)


def get_admin_steam_ids():
    disabled_root_admin_ids = {
        str((record or {}).get('steam_id') or '').strip()
        for record in users.values()
        if record and record.get('admin_test_mode_disabled')
    }
    admin_ids = {
        steam_id
        for steam_id in ADMIN_STEAM_IDS
        if steam_id not in disabled_root_admin_ids
    }
    for record in users.values():
        steam_id = str((record or {}).get('steam_id') or '').strip()
        if steam_id and record.get('is_admin') and not record.get('admin_test_mode_disabled'):
            admin_ids.add(steam_id)
    return admin_ids


def is_admin_steam_id(steam_id):
    return str(steam_id or '').strip() in get_admin_steam_ids()


def is_team_enforcement_bypass_steam_id(steam_id):
    return ADMIN_TEAM_ENFORCEMENT_BYPASS_ENABLED and is_admin_steam_id(steam_id)


def get_automation_control():
    mode = AUTOMATION_CONTROL.get('mode') or 'on'
    return {
        'mode': mode,
        'availableModes': sorted(AUTOMATION_MODES),
        'rconWritesEnabled': mode == 'on'
    }


def set_automation_mode(mode):
    normalized = str(mode or '').strip().lower()
    if normalized not in AUTOMATION_MODES:
        raise ValueError(f'Automation mode must be one of: {", ".join(sorted(AUTOMATION_MODES))}')
    AUTOMATION_CONTROL['mode'] = normalized
    return get_automation_control()


def get_automation_mode():
    return AUTOMATION_CONTROL.get('mode') or 'on'


def require_rcon_writes_enabled(action):
    mode = get_automation_mode()
    if mode != 'on':
        raise AutomationCommandBlocked(
            f'RCON write blocked because automation mode is "{mode}" while attempting {action}.'
        )


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
    details = build_server_connection_details_service(
        bridge_request=get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id),
        configured_name=(server or {}).get('display_name') or SQUAD_SERVER_NAME,
        password=(server or {}).get('join_password') or SQUAD_SERVER_PASSWORD,
        connect_address=(server or {}).get('connect_address') or SQUAD_SERVER_CONNECT_ADDRESS,
        steam_lobby_id=(server or {}).get('steam_lobby_id')
    )
    discovery_result = {
        'serverInfo': details.get('bridge') or {},
        'bridge': {
            'details': details.get('bridge') or {},
        },
    }
    enrich_server_result_with_discovery(
        discovery_result,
        {
            **(server or {}),
            'connect_address': details.get('connectAddress') or '',
            'steam_lobby_id': details.get('steam_lobby_id') or '',
        },
        status='healthy' if details.get('bridgeAvailable') else 'offline',
        error_message=details.get('bridgeError') or '',
    )
    details['networkIdentity'] = discovery_result.get('networkIdentity') or {}
    details['steamLobbyDiscovery'] = discovery_result.get('steamLobbyDiscovery') or {}
    details['sessionDiscovery'] = discovery_result.get('sessionDiscovery') or {}
    details['eosDiscovery'] = discovery_result.get('eosDiscovery') or {}
    current_live_session = build_live_session_snapshot(discovery_result, checked_at=time.time())
    persisted_live_session = dict((server or {}).get('metadata', {}).get('liveSession') or {})
    details['liveSession'] = select_preferred_live_session(current_live_session, persisted_live_session)
    details['joinStrategy'] = discovery_result.get('joinStrategy') or {}
    details['joinStrategy'] = {
        **details['joinStrategy'],
        'verifiedLiveSessionId': details['liveSession'].get('targetServerId') or '',
        'verifiedLiveSessionFresh': bool(details['liveSession'].get('fresh')),
        'verifiedLiveSessionAt': details['liveSession'].get('lastSeenAt') or 0,
        'verifiedLiveSessionSource': details['liveSession'].get('source') or '',
    }
    details['joinUrl'] = build_join_url_from_server_details_service(details)
    return details


def change_server_to_selected_map(selected_map, server_id=None, lobby_id=None, faction1=None, faction2=None):
    require_rcon_writes_enabled('change layer')
    return change_server_to_selected_map_service(
        selected_map,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id),
        faction1=faction1,
        faction2=faction2
    )


def set_next_server_map(selected_map, server_id=None, lobby_id=None, faction1=None, faction2=None):
    require_rcon_writes_enabled('set next layer')
    return set_next_server_map_service(
        selected_map,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id),
        faction1=faction1,
        faction2=faction2
    )


def force_player_to_expected_team(steam_id, server_id=None, lobby_id=None):
    if is_team_enforcement_bypass_steam_id(steam_id):
        return {'ok': True, 'skipped': True, 'reason': 'admin_team_bypass'}
    require_rcon_writes_enabled('force team change')
    return force_team_change_service(
        steam_id,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def kick_player_from_server(player_id, reason='Match complete.', server_id=None, lobby_id=None):
    if is_admin_steam_id(player_id):
        return {'ok': True, 'skipped': True, 'reason': 'admin_bypass'}
    require_rcon_writes_enabled('kick player')
    return kick_player_service(
        player_id,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id),
        reason=reason
    )


def end_server_match(server_id=None, lobby_id=None):
    require_rcon_writes_enabled('end match')
    return end_match_service(
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def get_server_layer_status(selected_map, server_id=None, lobby_id=None):
    return get_server_layer_status_service(
        selected_map,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def get_selected_map_team_labels(selected_map, server_id=None, lobby_id=None):
    try:
        return get_selected_map_team_labels_service(
            selected_map,
            get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
        )
    except Exception:
        logging.getLogger(__name__).warning(
            'Could not resolve team labels for selected map %s',
            selected_map,
            exc_info=True
        )
        return {}


def fetch_latest_round_result(server_id=None, lobby_id=None):
    return fetch_latest_round_result_service(
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def fetch_best_round_result(lobby_id=None, selected_layer='', live_started_at=None, server_details_provided_at=None, server_id=None):
    return fetch_best_round_result_service(
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id),
        lobby_id=lobby_id or '',
        selected_layer=selected_layer or '',
        live_started_at=live_started_at,
        server_details_provided_at=server_details_provided_at
    )


def register_match_context(lobby_id, context):
    return register_match_context_service(
        get_bridge_request_for_server(lobby_id=lobby_id),
        context
    )


def record_lobby_event(lobby_id, event_type, payload=None, *, created_at):
    result = record_lobby_event_service(
        get_db_connection,
        lobby_id,
        event_type,
        payload,
        created_at=created_at
    )
    save_runtime_state()
    return result


def save_completed_match(lobby_id, lobby, *, completed_at):
    return save_completed_match_service(
        get_db_connection,
        lobby_id,
        lobby,
        completed_at=completed_at
    )


def fetch_completed_matches(limit=20, username=None, scored_only=False):
    return fetch_completed_matches_service(
        get_db_connection,
        limit=limit,
        username=username,
        scored_only=scored_only
    )


def fetch_lobby_audit_events(lobby_id=None, limit=30):
    return fetch_lobby_audit_events_service(get_db_connection, lobby_id=lobby_id, limit=limit)


def get_history_counts():
    return get_history_counts_service(get_db_connection)


def get_admin_diagnostics():
    from app import lobbies as lobbies_ref, matchmaking_queue as queue_ref, pending_match as pending_match_ref
    return build_admin_diagnostics_service(
        get_database_health=get_database_health,
        get_bridge_health=get_bridge_health,
        get_eos_runtime_status=get_eos_runtime_status_service,
        get_server_connection_details=get_server_connection_details,
        fetch_latest_round_result=fetch_latest_round_result,
        fetch_lobby_audit_events=fetch_lobby_audit_events,
        get_history_counts=get_history_counts,
        lobbies=lobbies_ref,
        queue_modes=QUEUE_MODES,
        matchmaking_queue=queue_ref,
        pending_match=pending_match_ref,
        servers=list_servers(),
        automation_control=get_automation_control(),
        admin_steam_ids=get_admin_steam_ids()
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
    live_session = server_details.get('liveSession') or {}
    if (
        live_session.get('matched')
        and live_session.get('fresh')
        and live_session.get('targetServerId')
    ):
        try:
            synthetic_lobby = create_synthetic_lobby_join_url_service(
                get_bridge_request_for_server(server_id=lobby.get('server_id'), lobby_id=lobby_id),
                live_session.get('targetServerId')
            )
            synthetic_join_url = str(synthetic_lobby.get('joinUrl') or '').strip()
            if synthetic_join_url:
                lobby['server_details'] = {
                    **server_details,
                    'syntheticLobby': synthetic_lobby,
                    'joinUrl': synthetic_join_url,
                    'joinStrategy': {
                        **(server_details.get('joinStrategy') or {}),
                        'joinMethod': 'synthetic_steam_lobby',
                        'source': 'synthetic_steam_lobby',
                        'target': str(synthetic_lobby.get('lobbyId') or '').strip(),
                        'ready': True,
                        'verifiedLiveSessionId': live_session.get('targetServerId') or '',
                        'verifiedLiveSessionFresh': True,
                        'verifiedLiveSessionAt': live_session.get('lastSeenAt') or 0,
                        'verifiedLiveSessionSource': live_session.get('source') or '',
                    }
                }
                return synthetic_join_url
        except Exception as error:
            logging.getLogger(__name__).warning(
                'Synthetic lobby join generation failed for lobby %s: %s',
                lobby_id,
                error
            )

    join_url = build_join_url_from_server_details_service(server_details)
    if join_url:
        return join_url
    potential_steam_lobby_id = server_details.get('steamLobbyId') or server_details.get('steam_lobby_id') or ''
    steam_lobby_id = normalize_steam_lobby_id(potential_steam_lobby_id)
    if steam_lobby_id:
        return build_steam_lobby_join_url_service(steam_lobby_id)
    connect_address = server_details.get('connectAddress') or server_details.get('ip') or ''
    join_password = server_details.get('password') or ''
    return build_squad_join_url_service(connect_address, join_password)


def broadcast_server_message(message, server_id=None, lobby_id=None):
    require_rcon_writes_enabled('broadcast server message')
    return broadcast_server_message_service(
        message,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def set_server_slomo(value, server_id=None, lobby_id=None):
    require_rcon_writes_enabled('set server slomo')
    return set_server_slomo_service(
        value,
        get_bridge_request_for_server(server_id=server_id, lobby_id=lobby_id)
    )


def build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=False):
    from app import lobbies as lobbies_ref
    return build_lobby_server_presence_service(
        lobby_id=lobby_id,
        lobbies=lobbies_ref,
        get_user_profile=get_user_profile,
        bridge_request=get_bridge_request_for_server(lobby_id=lobby_id),
        is_bypass_steam_id=is_admin_steam_id,
        is_team_bypass_steam_id=is_team_enforcement_bypass_steam_id,
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
        set_server_slomo=lambda value: set_server_slomo(value, lobby_id=lobby_id),
        change_server_to_selected_map=lambda selected_map, faction1=None, faction2=None: change_server_to_selected_map(
            selected_map,
            lobby_id=lobby_id,
            faction1=faction1,
            faction2=faction2
        ),
        set_next_server_map=lambda selected_map, faction1=None, faction2=None: set_next_server_map(
            selected_map,
            lobby_id=lobby_id,
            faction1=faction1,
            faction2=faction2
        ),
        end_server_match=lambda: end_server_match(lobby_id=lobby_id),
        force_player_to_expected_team=lambda steam_id: force_player_to_expected_team(steam_id, lobby_id=lobby_id),
        get_server_layer_status=lambda selected_map: get_server_layer_status(selected_map, lobby_id=lobby_id),
        get_server_connection_details=lambda: get_server_connection_details(lobby_id=lobby_id),
        fetch_latest_round_result=lambda selected_map=None, live_started_at=None, server_details_provided_at=None: fetch_best_round_result(
            lobby_id=lobby_id,
            selected_layer=selected_map,
            live_started_at=live_started_at,
            server_details_provided_at=server_details_provided_at
        ) or fetch_latest_round_result(lobby_id=lobby_id),
        register_match_context=lambda context: register_match_context(lobby_id, context),
        record_lobby_event=record_lobby_event,
        save_completed_match=save_completed_match,
        kick_player_from_server=kick_player_from_server,
        release_server_allocation=release_server_allocation,
        broadcast_open_lobbies_update=lambda: __import__('app').broadcast_open_lobbies_update(),
        broadcast_queue_update=lambda: __import__('app').broadcast_queue_update(),
        player_activity=player_activity,
        get_player_sids=lambda username: __import__('app').get_player_sids(username),
        emit_active_lobby_sync=lambda username, lobby_id: __import__('app').emit_active_lobby_sync(username, lobby_id),
        automation_mode_provider=get_automation_mode,
        save_runtime_state=save_runtime_state,
        ready_ratio=LIVE_ROLL_READY_RATIO,
        threshold_grace_seconds=LIVE_ROLL_THRESHOLD_GRACE_SECONDS,
        ready_grace_seconds=LIVE_ROLL_READY_GRACE_SECONDS,
        poll_seconds=LIVE_ROLL_POLL_SECONDS,
        retry_seconds=LIVE_ROLL_RETRY_SECONDS,
        team_swap_retry_seconds=LIVE_ROLL_TEAM_SWAP_RETRY_SECONDS,
        finalized_cleanup_delay_seconds=FINALIZED_LOBBY_CLEANUP_SECONDS,
        live_match_max_seconds=LIVE_MATCH_MAX_SECONDS,
        dev_mode=dev_mode,
        ready_override_enabled=LIVE_ROLL_READY_OVERRIDE_ENABLED,
        dev_override_username=DEV_LIVE_ROLL_OVERRIDE_USERNAME,
        dev_override_steam_id=DEV_LIVE_ROLL_OVERRIDE_STEAM_ID,
        logger=logger
    )
