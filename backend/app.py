#IMPORTS AND INITIAL SETUP
import eventlet, json, time, logging, random, asyncio, os, sqlite3, sys
from dotenv import load_dotenv
eventlet.monkey_patch()
sys.modules.setdefault('app', sys.modules[__name__])
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_socketio import SocketIO, emit, join_room, leave_room
from collections import Counter
from flask_cors import CORS
from threading import Lock, RLock
from types import SimpleNamespace
from functools import wraps
from app_state import (
    ALL_SKIRMISH_MAPS,
    BACKEND_HOST,
    BACKEND_PORT,
    BACKEND_PUBLIC_URL,
    BASE_DIR,
    BRIDGE_ERROR_LOG_INTERVAL_SECONDS,
    CLEANUP_INTERVAL,
    DATABASE_PATH,
    DEV_MODE,
    FRONTEND_ORIGINS,
    GROUP_CODE_ALPHABET,
    GROUP_CODE_LENGTH,
    JWT_ACCESS_TOKEN_EXPIRES_HOURS,
    LEGACY_QUEUE_FILE,
    LEGACY_USERS_FILE,
    MAX_LOBBY_PLAYERS,
    MATCH_ACCEPT_COUNTDOWN,
    QUEUE_CHECK_INTERVAL,
    SYNC_INTERVAL,
    SQUADJS_BRIDGE_TOKEN,
    SQUADJS_BRIDGE_URL,
    bridge_status,
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
    broadcast_server_message,
    build_lobby_server_presence,
    change_server_to_selected_map,
    get_bridge_health,
    get_database_health,
    get_db_connection,
    get_user_profile,
    get_user_record,
    is_valid_steam_id,
    load_queue,
    load_users,
    migrate_legacy_json_files,
    normalize_user_record,
    save_users,
    squadjs_bridge_request,
    start_live_roll_monitor,
    user_has_steam_id,
    init_database,
    initialize_state
)
from matchmaking import (
    add_to_queue,
    assign_teams,
    broadcast_queue_update,
    cancel_pending_match,
    check_queue_and_start_countdown,
    create_lobby,
    finalize_pending_match,
    handle_socket_data,
    log_event,
    save_queue,
    select_captains,
    select_map_from_votes,
    start_map_voting,
    start_match_acceptance,
    update_queue_state
)
from bootstrap import start_server
from wiring import register_http_routes, register_socket_routes
from services.bridge import (
    BridgeUnavailable,
    build_lobby_server_presence as build_lobby_server_presence_service,
    broadcast_server_message as broadcast_server_message_service,
    change_server_to_selected_map as change_server_to_selected_map_service,
    fetch_connected_server_players as fetch_connected_server_players_service,
    get_bridge_health as get_bridge_health_service,
    get_database_health as get_database_health_service,
    squadjs_bridge_request as squadjs_bridge_request_service
)
from services.live_roll import start_live_roll_monitor as start_live_roll_monitor_service
from services.profile import (
    build_profile_status as build_profile_status_service,
    get_user_profile as get_user_profile_service,
    update_steam_id as update_steam_id_service,
    is_valid_steam_id as is_valid_steam_id_service
)
from services.queue import (
    add_to_queue as add_to_queue_service,
    build_queue_payload as build_queue_payload_service,
    cancel_pending_match as cancel_pending_match_service,
    check_queue_and_start_countdown as check_queue_and_start_countdown_service,
    finalize_pending_match as finalize_pending_match_service,
    start_match_acceptance as start_match_acceptance_service,
    update_queue_state as update_queue_state_service
)
from runtime import (
    cleanup_on_start as cleanup_on_start_runtime,
    cleanup_stale_players as cleanup_stale_players_runtime,
    periodic_queue_management as periodic_queue_management_runtime,
    start_auth_timeout as start_auth_timeout_runtime,
    start_periodic_tasks as start_periodic_tasks_runtime
)
from state.group import (
    broadcast_group_update,
    get_group_payload,
    get_player_groups,
    get_user_group
)
from state.lobby import (
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
from state.runtime import (
    is_countdown_paused,
    pause_aware_sleep,
    set_countdown_paused,
    with_retry
)
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
    handle_group_leave_event,
    handle_group_queue_event,
    handle_group_status_event,
    handle_group_unqueue_event,
)
from sockets.lobby import (
    handle_countdown_status_event,
    handle_get_lobby_data_event,
    handle_join_lobby_event,
    handle_leave_lobby_event,
    handle_open_lobbies_status_event,
    handle_prev_phase_event,
    handle_server_presence_event,
    handle_skip_phase_event,
    handle_start_lobby_event,
    handle_toggle_countdown_pause_event,
    select_map_from_votes as select_map_from_votes_event,
    vote_map_event,
)
from sockets.profile import handle_profile_status_event, handle_update_steam_id_event
from sockets.queue import (
    handle_accept_match_event,
    handle_join_queue_event,
    handle_leave_queue_event,
    handle_queue_status_event,
)

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
        'LEAVE': 'group_leave',
        'STATUS': 'group_status',
        'UPDATE': 'group_update',
        'QUEUE': 'group_queue',
        'UNQUEUE': 'group_unqueue'
    },

    'PROFILE': {
        'STATUS': 'profile_status',
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

#HELPER FUNCTIONS

register_http_routes(app)
register_socket_routes(socketio)

#QUEUE
def update_queue_state(save=True, broadcast=True):
    """Atomic queue state update"""
    try:
        update_queue_state_service(
            queue_lock=queue_lock,
            save_queue=save_queue,
            socketio=socketio,
            socket_events=SOCKET_EVENTS,
            matchmaking_queue=matchmaking_queue,
            save=save,
            broadcast=broadcast
        )
    except Exception as e:
        logger.error(f"Failed to update queue state: {str(e)}")

def check_queue_and_start_countdown():
    """Start match acceptance immediately when the queue fills."""
    try:
        check_queue_and_start_countdown_service(
            queue_lock=queue_lock,
            pending_match=pending_match,
            matchmaking_queue=matchmaking_queue,
            max_lobby_players=MAX_LOBBY_PLAYERS,
            start_match_acceptance=start_match_acceptance
        )
    except Exception as e:
        logger.error(f"Error starting match acceptance: {e}")

def add_to_queue(username):
    return add_to_queue_service(username, matchmaking_queue, upsert_player_activity, save_queue)

def save_queue(queue=None):
    """Save queue to SQLite"""
    try:
        queue_to_save = list(matchmaking_queue if queue is None else queue)
        with get_db_connection() as conn:
            conn.execute('DELETE FROM queue_entries')
            conn.executemany(
                'INSERT INTO queue_entries (position, username) VALUES (?, ?)',
                [(index, username) for index, username in enumerate(queue_to_save)]
            )
            conn.commit()
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to save queue to SQLite: {str(e)}")
        pass

def start_map_voting(lobby_id):
    """Handle map voting countdown and selection"""
    try:
        countdown = 30  # 30 second countdown
        lobby = lobbies.get(lobby_id)
        
        if not lobby:
            logger.error(f"Lobby {lobby_id} not found when starting map vote")
            return

        lobby['countdown_token'] = lobby.get('countdown_token', 0) + 1
        countdown_token = lobby['countdown_token']
            
        logger.info(f"Starting map voting countdown for lobby {lobby_id}")
        
        # Initialize map_votes if not exists
        if 'map_votes' not in lobby:
            lobby['map_votes'] = {}

        # Pick a random 5-map pool for this lobby
        if 'map_pool' not in lobby or not lobby['map_pool']:
            lobby['map_pool'] = random.sample(ALL_SKIRMISH_MAPS, k=min(5, len(ALL_SKIRMISH_MAPS)))
            
        # Store the countdown in the lobby state
        lobby['voting_countdown'] = countdown
            
        while countdown > 0:
            if lobby.get('step') != 2 or lobby.get('skip_phase'):
                return
            if lobby.get('countdown_token') != countdown_token:
                return
            if is_countdown_paused():
                eventlet.sleep(0.2)
                continue

            # Emit countdown update with specific event
            socketio.emit('lobby_countdown_voting', {
                'countdown': countdown,
                'lobby_id': lobby_id,
                'type': 'voting',
                'map_pool': lobby.get('map_pool', []),
                'map_votes': lobby['map_votes'],
                'vote_counts': {vote: sum(1 for v in lobby['map_votes'].values() if v == vote) 
                              for vote in set(lobby['map_votes'].values())}
            }, room=lobby_id)
            
            logger.debug(f"Map voting countdown: {countdown}, Votes: {lobby['map_votes']}")
            pause_aware_sleep(1)
            countdown -= 1
            lobby['voting_countdown'] = countdown
        
        if lobby.get('step') != 2 or lobby.get('skip_phase'):
            return
        if lobby.get('countdown_token') != countdown_token:
            return

        # After countdown ends, tally votes
        if lobby['map_votes']:
            # Count votes for each map
            vote_counts = {}
            for username, map_choice in lobby['map_votes'].items():
                vote_counts[map_choice] = vote_counts.get(map_choice, 0) + 1
            
            logger.info(f"Final vote counts: {vote_counts}")
            
            # Find map(s) with most votes
            max_votes = max(vote_counts.values())
            winning_maps = [map_name for map_name, votes in vote_counts.items() if votes == max_votes]
            
            # Select winning map (randomly if tied)
            selected_map = random.choice(winning_maps)
            logger.info(f"Selected map: {selected_map} with {max_votes} votes")
        else:
            # If no votes, randomly select a map
            fallback_pool = lobby.get('map_pool') or ALL_SKIRMISH_MAPS
            selected_map = random.choice(fallback_pool)
            logger.info(f"No votes cast, randomly selected map: {selected_map}")
        
        # Update lobby with selected map
        lobby['selected_map'] = selected_map
        lobby['step'] = 3
        lobby['countdown'] = None
        lobby['voting_countdown'] = None
        lobby['vote_counts'] = vote_counts if 'vote_counts' in locals() else {}
        
        # Notify clients about selected map
        socketio.emit('lobby_update', {
            'step': 3,
            'selected_map': selected_map,
            'lobby_id': lobby_id,
            'voting_countdown': None,
            'vote_counts': vote_counts if 'vote_counts' in locals() else {},
            'announcement': None
        }, room=lobby_id)
        socketio.emit(SOCKET_EVENTS['LOBBY']['MAP_SELECTED'], {
            'lobby_id': lobby_id,
            'map': selected_map,
            'step': 3,
            'voting_countdown': None,
            'vote_counts': vote_counts if 'vote_counts' in locals() else {}
        }, room=lobby_id)
        
        logger.info(f"Map {selected_map} selected for lobby {lobby_id}")
        start_live_roll_monitor(lobby_id)
        
    except Exception as e:
        logger.error(f"Error in map voting countdown: {str(e)}")
    
@with_retry(max_attempts=3)
def broadcast_queue_update(countdown=None):
    """Broadcast queue status to all connected clients"""
    try:
        logger.debug(f"Queue before broadcast: {list(matchmaking_queue)}")
        queue_status = build_queue_payload(countdown=countdown)

        # Broadcast to all clients without specifying a room
        socketio.emit(
            SOCKET_EVENTS['QUEUE']['UPDATE'], 
            queue_status,
            room=None
        )
        
        logger.debug(f"Broadcasting queue update: {queue_status}")
    except Exception as e:
        logger.error(f"Error in broadcast_queue_update: {str(e)}")

#LOBBY
def create_lobby(players_override=None):
    """Create a lobby when enough players are in queue"""
    with queue_lock:
        players = list(players_override[:MAX_LOBBY_PLAYERS]) if players_override else None
        if players is not None:
            if len(players) < MAX_LOBBY_PLAYERS:
                return False
        elif len(matchmaking_queue) >= MAX_LOBBY_PLAYERS:
            players = matchmaking_queue[:MAX_LOBBY_PLAYERS]
        else:
            return False

    try:
        logger.debug(f"Creating lobby for players: {players}")

        teams = assign_teams(players)
        captains = select_captains(teams)
        map_pool = random.sample(ALL_SKIRMISH_MAPS, k=min(5, len(ALL_SKIRMISH_MAPS)))
        lobby_id = f"lobby_{int(time.time())}"
        lobby_data = {
            'lobby_id': lobby_id,
            'players': players,
            'teams': teams,
            'captains': captains,
            'step': 2,
            'selected_map': None,
            'server_details': None,
            'countdown_active': False,
            'map_votes': {},
            'map_pool': map_pool,
            'voting_countdown': 30,
            'countdown': None,
            'countdown_token': 0,
            'player_groups': get_player_groups(players),
            'announcement': None,
            'live_roll_done': False,
            'live_roll_token': 0
        }

        lobbies[lobby_id] = lobby_data

        with queue_lock:
            for player in players:
                if player in matchmaking_queue:
                    matchmaking_queue.remove(player)
                if player in player_activity:
                    upsert_player_activity(player, status='in_lobby', lobby_id=lobby_id)
            save_queue()

        broadcast_queue_update()

        for player in players:
            for sid in get_player_sids(player):
                try:
                    socketio.server.enter_room(sid, lobby_id)
                except Exception as join_error:
                    logger.debug(
                        f"Skipping stale SID {sid} while joining lobby {lobby_id} for {player}: {join_error}"
                    )

        logger.info(f"Created lobby {lobby_id} with players {players}")
        for player in players:
            for sid in get_player_sids(player):
                try:
                    socketio.emit(SOCKET_EVENTS['LOBBY']['CREATED'], lobby_data, room=sid)
                except Exception as emit_error:
                    logger.debug(
                        f"Skipping stale SID {sid} while notifying lobby creation for {player}: {emit_error}"
                    )
            socketio.emit(SOCKET_EVENTS['LOBBY']['CREATED'], lobby_data, room=get_user_room(player))
            emit_active_lobby_sync(player, lobby_id)
        eventlet.spawn(start_map_voting, lobby_id)
        broadcast_open_lobbies_update()
        return True
    except Exception as e:
        logger.error(f"Error creating lobby: {str(e)}")
        if 'lobby_id' in locals() and lobby_id in lobbies:
            del lobbies[lobby_id]
        return False

def assign_teams(players):
    if not players:
        return {'team1': [], 'team2': []}

    cap1 = len(players) // 2
    cap2 = len(players) - cap1
    team1 = []
    team2 = []
    group_map = {}
    solo_players = []

    for player in players:
        code = user_to_group.get(player)
        if code and code in groups:
            group_map.setdefault(code, []).append(player)
        else:
            solo_players.append(player)

    clusters = list(group_map.values()) + [[player] for player in solo_players]
    random.shuffle(clusters)

    for cluster in clusters:
        if len(team1) + len(cluster) <= cap1:
            team1.extend(cluster)
        elif len(team2) + len(cluster) <= cap2:
            team2.extend(cluster)
        else:
            # Fallback: put in the team with more remaining space
            if (cap1 - len(team1)) >= (cap2 - len(team2)):
                team1.extend(cluster)
            else:
                team2.extend(cluster)

    random.shuffle(team1)
    random.shuffle(team2)
    return {'team1': team1, 'team2': team2}

def select_captains(teams):
    # Captains are temporarily disabled; keep the shape stable for clients.
    return {'team1': None, 'team2': None}
 
def select_map_from_votes(lobby):
    if lobby.get('map_votes'):
        vote_counts = {}
        for username, map_choice in lobby['map_votes'].items():
            vote_counts[map_choice] = vote_counts.get(map_choice, 0) + 1
        max_votes = max(vote_counts.values())
        winning_maps = [map_name for map_name, votes in vote_counts.items() if votes == max_votes]
        selected_map = random.choice(winning_maps)
        return selected_map, vote_counts
    pool = lobby.get('map_pool') or ALL_SKIRMISH_MAPS
    return random.choice(pool), {}


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
        request=request,
        logger=logger,
        group_lock=group_lock,
        get_user_group=get_user_group,
        user_has_steam_id=user_has_steam_id,
        build_queue_payload=build_queue_payload,
        queue_lock=queue_lock,
        matchmaking_queue=matchmaking_queue,
        max_lobby_players=MAX_LOBBY_PLAYERS,
        upsert_player_activity=upsert_player_activity,
        save_queue=save_queue,
        check_queue_and_start_countdown=check_queue_and_start_countdown
    )

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
                broadcast_queue_update=broadcast_queue_update,
                logger=logger,
                eventlet=eventlet
            ),
            logger=logger
        ),
        save_queue=save_queue,
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        logger=logger
     )
