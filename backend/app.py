#IMPORTS AND INITIAL SETUP
import eventlet, json, logging, random, os, sys, time
from dotenv import load_dotenv
eventlet.monkey_patch()
sys.modules.setdefault('app', sys.modules[__name__])
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
from datetime import timedelta
from flask import Flask, request
from flask_jwt_extended import JWTManager, create_access_token, get_jwt_identity, verify_jwt_in_request
from flask_socketio import SocketIO, emit, join_room
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from types import SimpleNamespace
from app_state import (
    AUTH_LOGIN_MAX_ATTEMPTS,
    AUTH_RATE_LIMIT_WINDOW_SECONDS,
    AUTH_REGISTER_MAX_ATTEMPTS,
    BACKEND_HOST,
    BACKEND_PORT,
    BACKEND_PUBLIC_URL,
    BASE_DIR,
    DATABASE_PATH,
    DEV_MODE,
    FRONTEND_ORIGINS,
    GROUP_CODE_ALPHABET,
    GROUP_CODE_LENGTH,
    JWT_ACCESS_TOKEN_EXPIRES_HOURS,
    FINALIZED_LOBBY_CLEANUP_SECONDS,
    LIVE_ROLL_READY_GRACE_SECONDS,
    LIVE_ROLL_READY_OVERRIDE_ENABLED,
    LOBBY_DISCONNECT_GRACE_SECONDS,
    MAX_LOBBY_PLAYERS,
    PASSWORD_AUTH_ENABLED,
    QUEUE_MODES,
    SQUADJS_BRIDGE_TOKEN,
    SQUADJS_BRIDGE_URL,
    STEAM_WEB_API_KEY,
    countdown_active,
    countdown_paused,
    countdown_pause_lock,
    group_lock,
    groups,
    lobbies,
    matchmaking_queue,
    pending_match,
    player_activity,
    queue_lock,
    user_to_group,
    users,
)
from app_core import (
    allocate_server_for_lobby,
    approve_server,
    broadcast_server_message,
    build_lobby_server_presence,
    build_lobby_join_url,
    change_server_to_selected_map,
    create_server,
    end_server_match,
    fetch_completed_matches,
    fetch_lobby_audit_events,
    get_admin_diagnostics,
    get_automation_control,
    get_bridge_health,
    get_database_health,
    get_db_connection,
    get_history_counts,
    get_server_by_id,
    get_server_connection_details,
    get_selected_map_team_labels,
    get_server_pool_capacity,
    get_user_profile,
    get_user_record,
    hash_password,
    list_available_servers,
    list_servers,
    record_lobby_event,
    is_admin_user,
    can_toggle_admin_mode,
    is_valid_steam_id,
    kick_player_from_server,
    load_queue,
    load_users,
    migrate_legacy_json_files,
    normalize_user_record,
    release_server_allocation,
    run_server_health_check,
    save_runtime_state,
    save_users,
    save_completed_match,
    set_server_enabled,
    set_automation_mode,
    set_self_admin_mode,
    squadjs_bridge_request,
    start_live_roll_monitor,
    test_server_connection,
    update_display_name_service,
    user_has_steam_id,
    init_database,
    initialize_state
)
from matchmaking import (
    cancel_pending_match,
    finalize_pending_match,
    handle_socket_data,
)
from bootstrap import start_server
from wiring import register_http_routes, register_socket_routes
from services.bridge import fetch_connected_server_players as fetch_connected_server_players_service
from services.queue import has_available_server_capacity
from services.profile import (
    build_profile_status as build_profile_status_service,
    update_display_name as update_display_name_service,
    update_steam_id as update_steam_id_service,
    is_valid_steam_id as is_valid_steam_id_service,
)
from runtime import (
    cleanup_on_start as cleanup_on_start_runtime,
    cleanup_stale_players as cleanup_stale_players_runtime,
    periodic_runtime_state_persistence as periodic_runtime_state_persistence_runtime,
    periodic_queue_management as periodic_queue_management_runtime,
    start_periodic_tasks as start_periodic_tasks_runtime
)
from state.group import (
    broadcast_group_update,
    get_group_payload,
    get_player_groups,
    get_user_group
)
from state.lobby import (
    build_player_profile_map,
    broadcast_open_lobbies_update,
    emit_active_lobby_sync,
    find_active_lobby_for_user,
    get_active_lobbies,
    get_match_accept_payload,
    get_open_lobbies,
    get_player_sids,
    get_username_by_sid,
    get_user_room,
    is_user_in_any_lobby,
    remove_player_session,
    upsert_player_activity
)
from state.queue import build_queue_payload
from state.runtime import is_countdown_paused, set_countdown_paused
from sockets.auth import (
    handle_authenticate_event,
    handle_connect_event,
    handle_disconnect_event,
    login_socket_event,
    register_socket_event,
)
from sockets.group import (
    handle_group_create_event,
    handle_group_join_event,
    handle_group_kick_event,
    handle_group_leave_event,
    handle_group_queue_event,
    handle_group_status_event,
    handle_group_transfer_event,
    handle_group_unqueue_event,
)
from sockets.lobby import (
    handle_countdown_status_event,
    handle_delete_lobby_event,
    handle_get_lobby_data_event,
    handle_join_lobby_event,
    handle_leave_lobby_event,
    handle_open_lobbies_status_event,
    handle_prev_phase_event,
    handle_server_presence_event,
    handle_skip_phase_event,
    handle_start_lobby_event,
    handle_toggle_countdown_pause_event,
    vote_map_event,
)
from sockets.profile import (
    handle_profile_status_event,
    handle_update_display_name_event,
    handle_update_steam_id_event
)
from sockets.queue import (
    handle_accept_match_event,
    handle_clear_queue_event,
    handle_join_queue_event,
    handle_leave_queue_event,
    handle_queue_status_event,
    handle_seed_queue_event,
)
import matchmaking as matchmaking_module

GROUP_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
GROUP_CODE_LENGTH = 6

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(BASE_DIR, 'matchmaking.log')),
        logging.StreamHandler()
    ]
)

class LogFilter(logging.Filter):
    def filter(self, record):
        # Filter out routine socket messages
        if any(msg in record.getMessage() for msg in [
            'Sending packet MESSAGE',
            'Received packet MESSAGE',
            'Broadcasting queue update',
            'Queue before broadcast'
        ]):
            return False
        return True

logger = logging.getLogger(__name__)
logger.addFilter(LogFilter())

initialize_state()

# Reduce engineio/socketio logging
logging.getLogger('engineio').setLevel(logging.WARNING)
logging.getLogger('socketio').setLevel(logging.WARNING)
logging.getLogger('werkzeug').setLevel(logging.WARNING)

def generate_group_code():
    for _ in range(1000):
        code = ''.join(random.choice(GROUP_CODE_ALPHABET) for _ in range(GROUP_CODE_LENGTH))
        if code not in groups:
            return code
    raise RuntimeError('Unable to generate a unique group code')

#APP CONFIGURATION
app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
logger.info("Starting Flask application")

# CORS setup
logger.info("Configuring CORS")
CORS(app, 
     resources={
         r"/*": {
             "origins": FRONTEND_ORIGINS,
             "methods": ["GET", "POST", "OPTIONS", "WEBSOCKET"],
             "allow_headers": ["*"],
             "supports_credentials": True,
             "expose_headers": ["*"]
         }
     })
logger.info("CORS configured")

#JWT setup
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'dev-jwt-secret')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=JWT_ACCESS_TOKEN_EXPIRES_HOURS)

def validate_auth_configuration():
    if DEV_MODE:
        return

    if PASSWORD_AUTH_ENABLED:
        raise RuntimeError('Password auth must be disabled when CMP_DEV_MODE=0')

    if not FRONTEND_ORIGINS:
        raise RuntimeError('FRONTEND_ORIGINS must include the production frontend origin')

    if not BACKEND_PUBLIC_URL.startswith('https://'):
        raise RuntimeError('BACKEND_PUBLIC_URL must use HTTPS in production')

    if not SQUADJS_BRIDGE_TOKEN:
        raise RuntimeError('SQUADJS_BRIDGE_TOKEN must be set in production')

    if not SQUADJS_BRIDGE_URL:
        raise RuntimeError('SQUADJS_BRIDGE_URL must be set in production')

    if not STEAM_WEB_API_KEY:
        raise RuntimeError('STEAM_WEB_API_KEY must be set in production so Steam display names can be resolved reliably')

    if not os.path.isabs(DATABASE_PATH):
        raise RuntimeError('DATABASE_PATH must be an absolute persistent path in production')

    weak_values = {'', 'change-me', 'dev-secret-key', 'dev-jwt-secret'}
    for key in ('SECRET_KEY', 'JWT_SECRET_KEY'):
        value = str(app.config.get(key) or '')
        if value in weak_values or len(value) < 32:
            raise RuntimeError(f'{key} must be a strong production secret')

    insecure_public_origins = [
        origin for origin in FRONTEND_ORIGINS
        if origin.startswith('http://') and 'localhost' not in origin and '127.0.0.1' not in origin
    ]
    if insecure_public_origins:
        raise RuntimeError(
            f'Production FRONTEND_ORIGINS must use HTTPS for public origins: {insecure_public_origins}'
        )


validate_auth_configuration()
jwt = JWTManager(app)

SOCKET_EVENTS =  {
    'CONNECTION': {
        'CONNECT': 'connect',
        'DISCONNECT': 'disconnect',
        'ERROR': 'connect_error',
        'RECONNECT': 'reconnect'
    },

  
    'AUTH': {
        'LOGIN': 'login',
        'LOGIN_SUCCESS': 'login_success',
        'LOGIN_ERROR': 'login_error',
        'AUTHENTICATE': 'authenticate',
        'AUTHENTICATION_SUCCESS': 'authentication_success',
        'AUTHENTICATION_ERROR': 'authentication_error',
        'REGISTER': 'register',
        'REGISTER_SUCCESS': 'register_success',
        'REGISTER_ERROR': 'register_error'
    },

  
    'QUEUE': {
        'JOIN': 'join-queue',
        'JOINED': 'queue_joined',
        'LEAVE': 'leave-queue',
        'LEFT': 'queue_left',
        'UPDATE': 'queue_update',
        'STATUS': 'queue_status',
        'FIND_MATCH': 'find-match',
        'MATCH_FOUND': 'match_found',
        'SEED': 'queue_seed',
        'CLEAR': 'queue_clear',
        'ACCEPT_MATCH': 'queue_accept_match',
        'MATCH_ACCEPT_CANCELLED': 'queue_match_accept_cancelled'
    },

  
    'LOBBY': {
        'CREATED': 'lobby_created',
        'JOIN': 'join-lobby',
        'LEAVE': 'leave-lobby',
        'DELETE': 'delete-lobby',
        'UPDATE': 'lobby_update',
        'DATA': 'lobby_data',
        'GET_DATA': 'get-lobby-data',
        'SERVER_PRESENCE': 'lobby_server_presence',
        'VOTE_MAP': 'vote-map',
        'MAP_SELECTED': 'map_selected',
        'START': 'start-lobby',
        'READY': 'lobby_ready',
        'COUNTDOWN': {
            'VOTING': 'lobby_countdown_voting'
        },
        'SKIP_PHASE': 'skip-phase',
        'PREV_PHASE': 'prev-phase',
    },

    'COUNTDOWN': {
        'TOGGLE_PAUSE': 'pause-countdown',
        'PAUSE_STATE': 'countdown_pause_state',
        'STATUS': 'countdown_status'
    },

    'OPEN_LOBBIES': {
        'STATUS': 'open_lobbies_status',
        'UPDATE': 'open_lobbies_update'
    },

    'GROUP': {
        'CREATE': 'group_create',
        'JOIN': 'group_join',
        'KICK': 'group_kick',
        'LEAVE': 'group_leave',
        'TRANSFER': 'group_transfer',
        'STATUS': 'group_status',
        'UPDATE': 'group_update',
        'QUEUE': 'group_queue',
        'UNQUEUE': 'group_unqueue'
    },

    'PROFILE': {
        'STATUS': 'profile_status',
        'UPDATE_DISPLAY_NAME': 'profile_update_display_name',
        'UPDATE_STEAM_ID': 'profile_update_steam_id'
    },

    'MESSAGE': 'message',
}; 

#after SOCKET_EVENTS definition
logger.info("=== Socket Events Configuration ===")
logger.info(f"Queue Leave Event: {SOCKET_EVENTS['QUEUE']['LEAVE']}")
logger.info(f"Queue Join Event: {SOCKET_EVENTS['QUEUE']['JOIN']}")
logger.info(f"Queue Status Event: {SOCKET_EVENTS['QUEUE']['STATUS']}")
logger.info(f"Queue Update Event: {SOCKET_EVENTS['QUEUE']['UPDATE']}")

# SocketIO setup
logger.info("Initializing SocketIO")
socketio = SocketIO(
    app,
    cors_allowed_origins=FRONTEND_ORIGINS,
    async_mode='eventlet',
    logger=False,
    engineio_logger=False,
    ping_timeout=5000,
    ping_interval=25000,
    cors_credentials=True,
    async_handlers=False
)
logger.info("SocketIO initialized")

# Keep the app-level names stable for existing socket/runtime wiring while routing
# queue and lobby orchestration through the extracted matchmaking module.
update_queue_state = matchmaking_module.update_queue_state
check_queue_and_start_countdown = matchmaking_module.check_queue_and_start_countdown
add_to_queue = matchmaking_module.add_to_queue
build_lobby_map_pool = matchmaking_module.build_lobby_map_pool
save_queue = matchmaking_module.save_queue
start_map_voting = matchmaking_module.start_map_voting
broadcast_queue_update = matchmaking_module.broadcast_queue_update
create_lobby = matchmaking_module.create_lobby
assign_teams = matchmaking_module.assign_teams
select_captains = matchmaking_module.select_captains
select_map_from_votes = matchmaking_module.select_map_from_votes


def expire_restored_finalized_lobby(lobby_id, delay_seconds=0):
    if delay_seconds > 0:
        eventlet.sleep(delay_seconds)
    lobby = lobbies.get(lobby_id)
    if not lobby or lobby.get('step') != 5:
        return

    now = time.time()
    for player in lobby.get('players') or []:
        activity = player_activity.get(player)
        if activity and activity.get('lobby_id') == lobby_id:
            activity['lobby_id'] = None
            activity['status'] = 'authenticated'
            activity['last_seen'] = now
        try:
            emit_active_lobby_sync(player, None)
        except Exception as exc:
            logger.warning("Failed to clear active lobby sync for %s after restored finalized cleanup: %s", player, exc)

    lobbies.pop(lobby_id, None)
    save_runtime_state()
    try:
        broadcast_open_lobbies_update()
    except Exception as exc:
        logger.warning("Failed to broadcast open lobbies after restored finalized cleanup for %s: %s", lobby_id, exc)
    try:
        broadcast_queue_update()
    except Exception as exc:
        logger.warning("Failed to broadcast queue update after restored finalized cleanup for %s: %s", lobby_id, exc)
    logger.info("Removed restored finalized lobby %s", lobby_id)


def resume_restored_lobby_tasks():
    restored_count = 0
    finalized_cleanup_count = 0
    state_changed = False
    now = time.time()
    for lobby_id, lobby in list(lobbies.items()):
        step = lobby.get('step')
        if step == 2:
            eventlet.spawn(start_map_voting, lobby_id)
            restored_count += 1
        elif step in (3, 4) and lobby.get('selected_map'):
            start_live_roll_monitor(lobby_id)
            restored_count += 1
        elif step == 5:
            if not lobby.get('server_released_at'):
                try:
                    release_server_allocation(lobby_id, reason='restored_finalized_lobby')
                    lobby['server_released_at'] = now
                    state_changed = True
                except Exception as exc:
                    logger.warning(
                        "Failed to release server for restored finalized lobby %s: %s",
                        lobby_id,
                        exc,
                    )

            finalized_at = float(lobby.get('finalized_at') or 0)
            if not finalized_at or now - finalized_at >= FINALIZED_LOBBY_CLEANUP_SECONDS:
                expire_restored_finalized_lobby(lobby_id)
                finalized_cleanup_count += 1
                state_changed = True
            else:
                eventlet.spawn(
                    expire_restored_finalized_lobby,
                    lobby_id,
                    max(0, FINALIZED_LOBBY_CLEANUP_SECONDS - (now - finalized_at))
                )
                restored_count += 1
    if state_changed:
        save_runtime_state()
    if restored_count:
        logger.info("Resumed background tasks for %s restored lobbies", restored_count)
    if finalized_cleanup_count:
        logger.info("Removed %s expired finalized restored lobbies", finalized_cleanup_count)

#HELPER FUNCTIONS

register_http_routes(app)
register_socket_routes(socketio)

def handle_connect(auth):
    if auth is None:
        auth = request.args.get('auth', {})
        if isinstance(auth, str):
            try:
                auth = json.loads(auth)
            except Exception:
                auth = {}

    def decode_token_for_legacy_wrapper(_token):
        verify_jwt_in_request()
        return {'sub': get_jwt_identity()}

    return handle_connect_event(
        auth,
        request=request,
        logger=logger,
        emit=emit,
        socket_events=SOCKET_EVENTS,
        decode_token=decode_token_for_legacy_wrapper,
        is_countdown_paused=is_countdown_paused,
        find_active_lobby_for_user=find_active_lobby_for_user,
        upsert_player_activity=upsert_player_activity,
        join_room=join_room,
        get_user_room=get_user_room
    )


def handle_join_queue(data):
    return handle_join_queue_event(
        data,
        socket_events=SOCKET_EVENTS,
        emit=emit,
        socketio=socketio,
        broadcast_queue_update=broadcast_queue_update,
        request=request,
        logger=logger,
        group_lock=group_lock,
        get_user_group=get_user_group,
        user_has_steam_id=user_has_steam_id,
        build_queue_payload=build_queue_payload,
        queue_lock=queue_lock,
        matchmaking_queue=matchmaking_queue,
        queue_modes=QUEUE_MODES,
        pending_match=pending_match,
        lobbies=lobbies,
        upsert_player_activity=upsert_player_activity,
        save_queue=save_queue,
        check_queue_and_start_countdown=check_queue_and_start_countdown,
        has_available_server_capacity=has_available_server_capacity
    )

# Public app-module surface for wiring, app_core, and tests.
# Keep this list deliberate: if another module needs something from `app`,
# add it here on purpose rather than relying on incidental module globals.
APP_PUBLIC_EXPORTS = (
    'AUTH_LOGIN_MAX_ATTEMPTS',
    'AUTH_RATE_LIMIT_WINDOW_SECONDS',
    'AUTH_REGISTER_MAX_ATTEMPTS',
    'BACKEND_HOST',
    'BACKEND_PORT',
    'DEV_MODE',
    'FRONTEND_ORIGINS',
    'LIVE_ROLL_READY_GRACE_SECONDS',
    'LIVE_ROLL_READY_OVERRIDE_ENABLED',
    'MAX_LOBBY_PLAYERS',
    'PASSWORD_AUTH_ENABLED',
    'QUEUE_MODES',
    'STEAM_WEB_API_KEY',
    'SOCKET_EVENTS',
    'app',
    'allocate_server_for_lobby',
    'approve_server',
    'assign_teams',
    'broadcast_group_update',
    'broadcast_open_lobbies_update',
    'broadcast_queue_update',
    'build_lobby_server_presence',
    'build_lobby_join_url',
    'build_profile_status_service',
    'build_queue_payload',
    'cancel_pending_match',
    'can_toggle_admin_mode',
    'change_server_to_selected_map',
    'check_queue_and_start_countdown',
    'countdown_active',
    'countdown_pause_lock',
    'countdown_paused',
    'create_access_token',
    'create_server',
    'create_lobby',
    'emit_active_lobby_sync',
    'fetch_completed_matches',
    'fetch_connected_server_players_service',
    'find_active_lobby_for_user',
    'finalize_pending_match',
    'generate_group_code',
    'get_active_lobbies',
    'get_admin_diagnostics',
    'get_automation_control',
    'get_server_by_id',
    'get_bridge_health',
    'get_database_health',
    'get_group_payload',
    'get_match_accept_payload',
    'get_open_lobbies',
    'get_player_groups',
    'get_player_sids',
    'get_server_connection_details',
    'get_selected_map_team_labels',
    'get_server_pool_capacity',
    'get_user_group',
    'get_user_profile',
    'get_user_record',
    'get_user_room',
    'get_username_by_sid',
    'group_lock',
    'groups',
    'handle_accept_match_event',
    'handle_authenticate_event',
    'handle_clear_queue_event',
    'handle_connect',
    'handle_connect_event',
    'handle_countdown_status_event',
    'handle_delete_lobby_event',
    'handle_disconnect_event',
    'handle_get_lobby_data_event',
    'handle_group_create_event',
    'handle_group_join_event',
    'handle_group_kick_event',
    'handle_group_leave_event',
    'handle_group_queue_event',
    'handle_group_status_event',
    'handle_group_transfer_event',
    'handle_group_unqueue_event',
    'handle_join_lobby_event',
    'handle_join_queue',
    'handle_join_queue_event',
    'handle_leave_lobby_event',
    'handle_leave_queue_event',
    'handle_open_lobbies_status_event',
    'handle_prev_phase_event',
    'handle_profile_status_event',
    'handle_queue_status_event',
    'handle_seed_queue_event',
    'handle_server_presence_event',
    'handle_skip_phase_event',
    'handle_socket_data',
    'handle_start_lobby_event',
    'handle_toggle_countdown_pause_event',
    'handle_update_display_name_event',
    'handle_update_steam_id_event',
    'hash_password',
    'end_server_match',
    'is_admin_user',
    'kick_player_from_server',
    'is_countdown_paused',
    'is_user_in_any_lobby',
    'join_room',
    'jwt',
    'lobbies',
    'logger',
    'login_socket_event',
    'list_available_servers',
    'list_servers',
    'matchmaking_queue',
    'pending_match',
    'queue_lock',
    'record_lobby_event',
    'register_socket_event',
    'release_server_allocation',
    'remove_player_session',
    'request',
    'run_server_health_check',
    'save_runtime_state',
    'save_queue',
    'save_users',
    'select_captains',
    'select_map_from_votes',
    'set_server_enabled',
    'set_automation_mode',
    'set_self_admin_mode',
    'set_countdown_paused',
    'socketio',
    'squadjs_bridge_request',
    'start_live_roll_monitor',
    'start_map_voting',
    'test_server_connection',
    'update_display_name_service',
    'update_steam_id_service',
    'upsert_player_activity',
    'user_has_steam_id',
    'user_to_group',
    'users',
    'verify_jwt_in_request',
    'vote_map_event',
)

__all__ = APP_PUBLIC_EXPORTS

#MAIN ENTRY POINT
if __name__ == '__main__':
     start_server(
        app_state=SimpleNamespace(app=app, socketio=socketio),
        cleanup_on_start=lambda: cleanup_on_start_runtime(
            reset_state=initialize_state,
            save_queue=save_queue,
            logger=logger
        ),
        start_periodic_tasks=lambda: start_periodic_tasks_runtime(
            socketio=socketio,
            periodic_queue_management=lambda: periodic_queue_management_runtime(
                app_context=app.app_context,
                broadcast_queue_update=broadcast_queue_update,
                logger=logger,
                eventlet=eventlet,
                countdown_active_ref=lambda: countdown_active
            ),
            cleanup_stale_players_task=lambda: cleanup_stale_players_runtime(
                queue_lock=queue_lock,
                player_activity=player_activity,
                matchmaking_queue=matchmaking_queue,
                lobbies=lobbies,
                broadcast_queue_update=broadcast_queue_update,
                broadcast_open_lobbies_update=broadcast_open_lobbies_update,
                socketio=socketio,
                build_player_profile_map=build_player_profile_map,
                select_captains=select_captains,
                emit_active_lobby_sync=emit_active_lobby_sync,
                record_lobby_event=record_lobby_event,
                release_server_allocation=release_server_allocation,
                save_runtime_state=save_runtime_state,
                lobby_disconnect_grace_seconds=LOBBY_DISCONNECT_GRACE_SECONDS,
                logger=logger,
                eventlet=eventlet
            ),
            runtime_state_persistence_task=lambda: periodic_runtime_state_persistence_runtime(
                save_runtime_state=save_runtime_state,
                logger=logger,
                eventlet=eventlet
            ),
            resume_lobby_tasks=resume_restored_lobby_tasks,
            logger=logger
        ),
        save_queue=save_queue,
        save_runtime_state=save_runtime_state,
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        logger=logger
     )
