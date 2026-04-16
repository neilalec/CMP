#IMPORTS AND INITIAL SETUP
import eventlet, json, time, logging, random, asyncio, signal, sys, os, sqlite3
from dotenv import load_dotenv
eventlet.monkey_patch()
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity, verify_jwt_in_request
from flask_socketio import SocketIO, emit, join_room, leave_room
from collections import Counter
from flask_cors import CORS
from threading import Lock, RLock
from functools import wraps
from urllib import request as urllib_request
from urllib import error as urllib_error
from urllib.parse import quote as url_quote

#GLOBAL VARIABLES AND DATA STRUCTURES
queue_lock = RLock()
QUEUE_CHECK_INTERVAL = 5
CLEANUP_INTERVAL = 30
SYNC_INTERVAL = 10
countdown_active = False
countdown_paused = False
countdown_pause_lock = RLock()
MAX_LOBBY_PLAYERS = 2
MATCH_ACCEPT_COUNTDOWN = 30
ALL_SKIRMISH_MAPS = [
    'Al Basrah Skirmish v1',
    'Al Basrah Skirmish v2',
    'Belaya Skirmish v1',
    'Chora Skirmish v1',
    "Fool's Road Skirmish v1",
    "Fool's Road Skirmish v2",
    'Gorodok Skirmish v1',
    'Kamdesh Skirmish v1',
    'Kohat Toi Skirmish v1',
    'Kokan Skirmish v1',
    'Logar Valley Skirmish v1',
    'Mestia Skirmish v1',
    'Narva Skirmish v1',
    'Skorpo Skirmish v1',
    'Sumari Skirmish v1',
    'Tallil Outskirts Skirmish v1',
    'Tallil Outskirts Skirmish v2',
    'Yehorivka Skirmish v1',
    'Yehorivka Skirmish v2'
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))
LEGACY_QUEUE_FILE = os.path.join(BASE_DIR, 'queue.json')
LEGACY_USERS_FILE = os.path.join(BASE_DIR, 'users.json')
DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'app.db'))
DEV_MODE = os.getenv('CMP_DEV_MODE', '0') == '1'
JWT_ACCESS_TOKEN_EXPIRES_HOURS = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_HOURS', '168'))
SQUADJS_BRIDGE_URL = os.getenv('SQUADJS_BRIDGE_URL', 'http://127.0.0.1:3001').rstrip('/')
SQUADJS_BRIDGE_TOKEN = os.getenv('SQUADJS_BRIDGE_TOKEN', '')
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv('FRONTEND_ORIGINS', 'http://localhost:5173').split(',')
    if origin.strip()
]
BACKEND_PUBLIC_URL = os.getenv('BACKEND_PUBLIC_URL', 'http://localhost:5000').rstrip('/')
BACKEND_HOST = os.getenv('BACKEND_HOST', '0.0.0.0')
BACKEND_PORT = int(os.getenv('BACKEND_PORT', '5000'))
BRIDGE_ERROR_LOG_INTERVAL_SECONDS = int(os.getenv('BRIDGE_ERROR_LOG_INTERVAL_SECONDS', '30'))

bridge_status = {
    'available': None,
    'last_error': None,
    'last_logged_error': None,
    'last_logged_at': 0.0
}

class BridgeUnavailable(RuntimeError):
    pass

def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def log_bridge_unavailable(error_message):
    now = time.time()
    should_log = (
        bridge_status['last_logged_error'] != error_message
        or (now - bridge_status['last_logged_at']) >= BRIDGE_ERROR_LOG_INTERVAL_SECONDS
    )
    bridge_status['available'] = False
    bridge_status['last_error'] = error_message
    if should_log:
        logging.getLogger(__name__).warning(error_message)
        bridge_status['last_logged_error'] = error_message
        bridge_status['last_logged_at'] = now

def mark_bridge_available():
    if bridge_status['available'] is False:
        logging.getLogger(__name__).info(f"SquadJS bridge reachable again at {SQUADJS_BRIDGE_URL}")
    bridge_status['available'] = True
    bridge_status['last_error'] = None

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
    """Load users from SQLite"""
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
    """Save users to SQLite"""
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

init_database()
migrate_legacy_json_files()

# Initialize users from file
users = {
    username: normalize_user_record(record)
    for username, record in load_users().items()
}

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
    record = get_user_record(username)
    if not record:
        return None
    return {
        'username': username,
        'steam_id': record.get('steam_id', ''),
        'has_steam_id': bool(record.get('steam_id')),
        'steam_id_locked': username in matchmaking_queue or is_user_in_any_lobby(username)
    }

def is_valid_steam_id(steam_id):
    steam_id = str(steam_id or '').strip()
    return steam_id.isdigit() and len(steam_id) == 17

def squadjs_bridge_request(path, method='GET', payload=None, timeout=5):
    url = f"{SQUADJS_BRIDGE_URL}{path}"
    body = None
    headers = {
        'Accept': 'application/json'
    }

    if SQUADJS_BRIDGE_TOKEN:
        headers['Authorization'] = f"Bearer {SQUADJS_BRIDGE_TOKEN}"

    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = urllib_request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
            mark_bridge_available()
            return json.loads(raw) if raw else {}
    except urllib_error.HTTPError as e:
        mark_bridge_available()
        raw = e.read().decode('utf-8') if e.fp else ''
        try:
            details = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            details = {'error': raw or str(e)}
        raise RuntimeError(details.get('error') or f"Bridge request failed with HTTP {e.code}")
    except urllib_error.URLError as e:
        message = f"Unable to reach SquadJS bridge at {SQUADJS_BRIDGE_URL}: {e.reason}"
        log_bridge_unavailable(message)
        raise BridgeUnavailable(message)
    except json.JSONDecodeError as e:
        mark_bridge_available()
        raise RuntimeError(f"Invalid JSON from SquadJS bridge: {e}")

def get_database_health():
    try:
        with get_db_connection() as conn:
            conn.execute('SELECT 1').fetchone()
        return {'ok': True, 'path': DATABASE_PATH}
    except Exception as e:
        return {'ok': False, 'path': DATABASE_PATH, 'error': str(e)}

def get_bridge_health():
    try:
        response = squadjs_bridge_request('/health', timeout=2)
        return {
            'ok': True,
            'url': SQUADJS_BRIDGE_URL,
            'details': response
        }
    except BridgeUnavailable as e:
        return {
            'ok': False,
            'url': SQUADJS_BRIDGE_URL,
            'error': str(e)
        }
    except Exception as e:
        return {
            'ok': False,
            'url': SQUADJS_BRIDGE_URL,
            'error': str(e)
        }

def build_bridge_unavailable_presence(lobby_id, lobby, error_message):
    team1_players = set(lobby.get('teams', {}).get('team1', []))
    team2_players = set(lobby.get('teams', {}).get('team2', []))
    presence = []

    for username in lobby.get('players', []):
        profile = get_user_profile(username) or {}
        expected_team_id = None
        if username in team1_players:
            expected_team_id = 1
        elif username in team2_players:
            expected_team_id = 2

        presence.append({
            'username': username,
            'steam_id': profile.get('steam_id', ''),
            'expectedTeamId': expected_team_id,
            'connected': False,
            'actualTeamId': None,
            'actualSquadId': None,
            'eosID': None,
            'serverName': None
        })

    return {
        'lobby_id': lobby_id,
        'players': presence,
        'connected': [],
        'missing': [player['username'] for player in presence],
        'bridgeAvailable': False,
        'bridgeError': error_message
    }

def fetch_connected_server_players():
    response = squadjs_bridge_request('/players')
    return response.get('players', [])

def fetch_layers_by_name(name):
    encoded_name = url_quote(str(name or '').strip(), safe='')
    response = squadjs_bridge_request(f'/layers?name={encoded_name}')
    return response.get('layers', [])

def resolve_selected_map_layer_id(selected_map):
    map_aliases = {
        'Kohat Skirmish v1': 'Kohat Toi Skirmish v1'
    }
    resolved_name = map_aliases.get(selected_map, selected_map)
    layers = fetch_layers_by_name(resolved_name)
    if not layers:
        raise RuntimeError(f'Could not resolve selected map "{selected_map}" to a Squad layer id.')
    return layers[0].get('layerId') or layers[0].get('classname')

def change_server_to_selected_map(selected_map):
    layer_id = resolve_selected_map_layer_id(selected_map)
    return squadjs_bridge_request('/layer/change', method='POST', payload={
        'layer': layer_id
    })

def broadcast_server_message(message):
    return squadjs_bridge_request('/broadcast', method='POST', payload={
        'message': message
    })

def build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=False):
    lobby = lobbies.get(lobby_id)
    if not lobby:
        raise ValueError('Lobby not found')

    try:
        connected_players = fetch_connected_server_players()
    except BridgeUnavailable as e:
        if tolerate_bridge_unavailable:
            return build_bridge_unavailable_presence(lobby_id, lobby, str(e))
        raise

    players_by_steam_id = {
        str(player.get('steamID') or '').strip(): player
        for player in connected_players
        if player.get('steamID')
    }

    team1_players = set(lobby.get('teams', {}).get('team1', []))
    team2_players = set(lobby.get('teams', {}).get('team2', []))

    presence = []
    connected_usernames = []
    missing_usernames = []

    for username in lobby.get('players', []):
        profile = get_user_profile(username) or {}
        steam_id = profile.get('steam_id', '')
        connected_player = players_by_steam_id.get(steam_id) if steam_id else None

        expected_team_id = None
        if username in team1_players:
            expected_team_id = 1
        elif username in team2_players:
            expected_team_id = 2

        row = {
            'username': username,
            'steam_id': steam_id,
            'expectedTeamId': expected_team_id,
            'connected': bool(connected_player),
            'actualTeamId': connected_player.get('teamID') if connected_player else None,
            'actualSquadId': connected_player.get('squadID') if connected_player else None,
            'eosID': connected_player.get('eosID') if connected_player else None,
            'serverName': connected_player.get('name') if connected_player else None
        }
        presence.append(row)

        if row['connected']:
            connected_usernames.append(username)
        else:
            missing_usernames.append(username)

    return {
        'lobby_id': lobby_id,
        'players': presence,
        'connected': connected_usernames,
        'missing': missing_usernames,
        'bridgeAvailable': True,
        'bridgeError': None
    }

def start_live_roll_monitor(lobby_id):
    lobby = lobbies.get(lobby_id)
    if not lobby:
        return

    lobby['live_roll_token'] = lobby.get('live_roll_token', 0) + 1
    token = lobby['live_roll_token']

    def monitor():
        while True:
            current_lobby = lobbies.get(lobby_id)
            if not current_lobby:
                return
            if current_lobby.get('live_roll_token') != token:
                return
            if current_lobby.get('step') != 3:
                return
            if current_lobby.get('live_roll_done'):
                return
            if not current_lobby.get('selected_map'):
                return

            try:
                presence = build_lobby_server_presence(lobby_id)
            except BridgeUnavailable:
                waiting_message = 'Waiting for SquadJS bridge to become available.'
                if current_lobby.get('announcement') != waiting_message:
                    current_lobby['announcement'] = waiting_message
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': waiting_message
                    }, room=lobby_id)
                pause_aware_sleep(5)
                continue
            except Exception as e:
                logger.error(f"Error checking server presence for lobby {lobby_id}: {str(e)}")
                pause_aware_sleep(5)
                continue

            if presence.get('missing'):
                pause_aware_sleep(5)
                continue

            selected_map = current_lobby.get('selected_map')
            announcement = f'Server will now roll to live on "{selected_map}"'
            current_lobby['announcement'] = announcement
            socketio.emit('lobby_update', {
                'lobby_id': lobby_id,
                'announcement': announcement
            }, room=lobby_id)

            pause_aware_sleep(2)

            try:
                broadcast_server_message(announcement)
                bridge_response = change_server_to_selected_map(selected_map)
                current_lobby['live_roll_done'] = True
                current_lobby['server_details'] = {
                    'map': selected_map,
                    'bridge_response': bridge_response
                }
                current_lobby['step'] = 4
                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'announcement': announcement,
                    'selected_map': selected_map,
                    'server_details': current_lobby['server_details'],
                    'step': 4
                }, room=lobby_id)
            except BridgeUnavailable:
                waiting_message = 'Waiting for SquadJS bridge to become available.'
                current_lobby['announcement'] = waiting_message
                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'announcement': waiting_message
                }, room=lobby_id)
                pause_aware_sleep(5)
                continue
            except Exception as e:
                error_message = f'Failed to roll server live on "{selected_map}": {str(e)}'
                current_lobby['announcement'] = error_message
                logger.error(error_message)
                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'announcement': error_message
                }, room=lobby_id)
            return

    eventlet.spawn(monitor)

# Load queue from file
def load_queue():
    """Load queue from SQLite"""
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

matchmaking_queue = load_queue()
player_activity = {}
lobbies = {}
pending_match = None
group_lock = RLock()
groups = {}
user_to_group = {}
GROUP_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
GROUP_CODE_LENGTH = 6

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('matchmaking.log'),
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

def get_group_payload(code):
    group = groups.get(code)
    if not group:
        return None
    return {
        'code': group['code'],
        'leader': group['leader'],
        'members': list(group['members'])
    }

def get_user_group(username):
    code = user_to_group.get(username)
    if code and code in groups:
        return code
    if code and code not in groups:
        user_to_group.pop(username, None)
    return None

def get_player_groups(players):
    if not players:
        return {}
    result = {}
    with group_lock:
        for player in players:
            code = user_to_group.get(player)
            if code and code in groups:
                result[player] = code
    return result

def is_user_in_any_lobby(username):
    for lobby in lobbies.values():
        if username in lobby.get('players', []):
            return True
    return False

def broadcast_group_update(code, group_payload=None):
    payload = {
        'success': True,
        'group': group_payload
    }
    socketio.emit(SOCKET_EVENTS['GROUP']['UPDATE'], payload, room=code)

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

#MISC
def handle_socket_data(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Get the data argument (usually first arg after 'self')
        data = args[0] if args else {}
        
        # Convert list to dict if needed
        if isinstance(data, list):
            data = data[0] if data else {}
            
        # Replace the first argument with our processed data
        args = (data,) + args[1:]
        
        return f(*args, **kwargs)
    return decorated

def log_event(event_type, data):
    """Structured logging helper"""
    logger.info(json.dumps({
        'event': event_type,
        'data': data,
        'timestamp': time.time()
    }))

def get_open_lobbies():
    open_lobbies = []
    for lobby_id, lobby in lobbies.items():
        players = lobby.get('players', [])
        if len(players) < MAX_LOBBY_PLAYERS:
            open_lobbies.append({
                'lobby_id': lobby_id,
                'players': players,
                'open_slots': MAX_LOBBY_PLAYERS - len(players),
                'max_players': MAX_LOBBY_PLAYERS,
                'step': lobby.get('step', 1),
                'captains': lobby.get('captains'),
                'selected_map': lobby.get('selected_map')
            })
    return open_lobbies

def get_active_lobbies():
    active = []
    for lobby_id, lobby in lobbies.items():
        players = lobby.get('players', [])
        if len(players) < MAX_LOBBY_PLAYERS:
            continue
        active.append({
            'lobby_id': lobby_id,
            'players': players,
            'open_slots': max(0, MAX_LOBBY_PLAYERS - len(players)),
            'max_players': MAX_LOBBY_PLAYERS,
            'step': lobby.get('step', 1),
            'captains': lobby.get('captains'),
            'selected_map': lobby.get('selected_map')
        })
    return active

def broadcast_open_lobbies_update():
    """Broadcast open lobbies to all connected clients"""
    try:
        socketio.emit(
            SOCKET_EVENTS['OPEN_LOBBIES']['UPDATE'],
            {
                'openLobbies': get_open_lobbies(),
                'activeLobbies': get_active_lobbies()
            },
            room=None
        )
    except Exception as e:
        logger.error(f"Error in broadcast_open_lobbies_update: {str(e)}")

def is_countdown_paused():
    with countdown_pause_lock:
        return countdown_paused

def set_countdown_paused(value):
    global countdown_paused
    with countdown_pause_lock:
        countdown_paused = bool(value)
        return countdown_paused

def pause_aware_sleep(seconds):
    remaining = seconds
    while remaining > 0:
        if is_countdown_paused():
            eventlet.sleep(0.2)
            continue
        step = 0.2 if remaining > 0.2 else remaining
        eventlet.sleep(step)
        remaining -= step

def with_retry(max_attempts=3):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    logger.error(f"Attempt {attempts} failed: {str(e)}")
                    if attempts == max_attempts:
                        raise
                    time.sleep(0.5)  # Short delay between retries
            return None
        return wrapper
    return decorator

def get_username_by_sid(sid):
    """Helper function to get username from socket ID"""
    logger.debug(f"Looking up username for SID: {sid}")
    logger.debug(f"Current player activity: {player_activity}")
    
    for username, data in player_activity.items():
        if data.get('sid') == sid:
            logger.info(f"Found username {username} for SID {sid}")
            return username
            
    logger.warning(f"No username found for SID: {sid}")
    return None

def get_match_accept_payload(username=None):
    if not pending_match:
        return None

    accepted_players = [
        player for player, accepted in pending_match.get('accepted', {}).items()
        if accepted
    ]
    return {
        'active': True,
        'players': list(pending_match.get('players', [])),
        'acceptedPlayers': accepted_players,
        'acceptedCount': len(accepted_players),
        'requiredCount': len(pending_match.get('players', [])),
        'countdown': pending_match.get('countdown', MATCH_ACCEPT_COUNTDOWN),
        'hasAccepted': bool(username and pending_match.get('accepted', {}).get(username))
    }

def build_queue_payload(username=None, countdown=None):
    payload = {
        'success': True,
        'inQueue': username in matchmaking_queue if username else False,
        'playersInQueue': len(matchmaking_queue),
        'queue': list(matchmaking_queue),
        'hasSteamId': user_has_steam_id(username) if username else False
    }
    if countdown is not None and countdown > 0:
        payload['countdown'] = countdown
    match_accept = get_match_accept_payload(username)
    if match_accept:
        payload['matchAccept'] = match_accept
    return payload

def cancel_pending_match(reason='Match acceptance cancelled.', remove_players=None):
    global pending_match, countdown_active

    with queue_lock:
        if not pending_match:
            return False

        participants = list(pending_match.get('players', []))
        removed_players = []
        for username in remove_players or []:
            if username in matchmaking_queue:
                matchmaking_queue.remove(username)
                removed_players.append(username)
                if username in player_activity:
                    player_activity[username]['status'] = 'authenticated'

        pending_match = None
        countdown_active = False
        save_queue()

    broadcast_queue_update()

    for username in participants:
        sid = player_activity.get(username, {}).get('sid')
        if sid:
            socketio.emit(SOCKET_EVENTS['QUEUE']['MATCH_ACCEPT_CANCELLED'], {
                'reason': reason,
                'removedPlayers': removed_players
            }, room=sid)
    return True

def finalize_pending_match(match_id):
    global pending_match

    with queue_lock:
        if not pending_match or pending_match.get('id') != match_id:
            return False
        players = list(pending_match.get('players', []))
        if not all(pending_match.get('accepted', {}).get(player) for player in players):
            return False
        pending_match = None

    broadcast_queue_update()
    return create_lobby(players)

def start_match_acceptance(players):
    global pending_match, countdown_active

    with queue_lock:
        if pending_match:
            return False

        tracked_players = list(players[:MAX_LOBBY_PLAYERS])
        pending_match = {
            'id': f"match_{int(time.time() * 1000)}",
            'players': tracked_players,
            'accepted': {player: False for player in tracked_players},
            'countdown': MATCH_ACCEPT_COUNTDOWN
        }
        countdown_active = False
        match_id = pending_match['id']

    broadcast_queue_update()

    def countdown():
        remaining = MATCH_ACCEPT_COUNTDOWN
        while remaining > 0:
            with queue_lock:
                if not pending_match or pending_match.get('id') != match_id:
                    return
                if all(pending_match['accepted'].get(player) for player in pending_match['players']):
                    break
                pending_match['countdown'] = remaining

            broadcast_queue_update()
            pause_aware_sleep(1)
            remaining -= 1

        with queue_lock:
            if not pending_match or pending_match.get('id') != match_id:
                return
            all_accepted = all(
                pending_match['accepted'].get(player)
                for player in pending_match['players']
            )
            pending_match['countdown'] = max(remaining, 0)
            not_accepted = [
                player for player in pending_match['players']
                if not pending_match['accepted'].get(player)
            ]

        if all_accepted:
            finalize_pending_match(match_id)
        else:
            cancel_pending_match(
                'Match acceptance timed out.',
                remove_players=not_accepted
            )

    eventlet.spawn(countdown)
    return True

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print('\nShutting down server...')
    
    # Clean up any active connections
    try:
        for sid in socketio.server.sockets:
            try:
                socketio.server.disconnect(sid)
            except:
                pass
    except:
        pass

    # Save current state
    try:
        save_queue()
    except:
        pass

    print('Shutdown complete')
    sys.exit(0)

#check backend is running
@app.route('/')
def index():
    return f"CMP SocketIO backend running. Frontend handled through Vue.js for origins: {', '.join(FRONTEND_ORIGINS)}"

@app.route('/health', methods=['GET'])
def health():
    database = get_database_health()
    bridge = get_bridge_health()
    ok = bool(database.get('ok')) and bool(bridge.get('ok'))
    payload = {
        'ok': ok,
        'status': 'ok' if ok else 'degraded',
        'service': 'backend',
        'database': database,
        'squadjsBridge': bridge,
        'queueSize': len(matchmaking_queue),
        'lobbyCount': len(lobbies)
    }
    return jsonify(payload), (200 if ok else 503)

@app.route('/api/server/players', methods=['GET'])
@jwt_required()
def api_server_players():
    try:
        return jsonify({
            'success': True,
            'players': fetch_connected_server_players()
        })
    except Exception as e:
        logger.error(f"Error fetching server players from SquadJS bridge: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 502

@app.route('/api/lobbies/<lobby_id>/server-presence', methods=['GET'])
@jwt_required()
def api_lobby_server_presence(lobby_id):
    try:
        return jsonify({
            'success': True,
            'presence': build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=True)
        })
    except ValueError as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 404
    except Exception as e:
        logger.error(f"Error building server presence for lobby {lobby_id}: {str(e)}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 502

@socketio.on_error_default
@handle_socket_data
def default_error_handler(e):
    print(f"SocketIO error: {str(e)}")
    print(f"Error type: {type(e)}")
    print(f"Request SID: {request.sid}")
    print(f"Request event: {request.event}")

    import traceback
    print(f"Traceback: {traceback.format_exc()}")

#QUEUE
def update_queue_state(save=True, broadcast=True):
    """Atomic queue state update"""
    with queue_lock:
        if save:
            try:
                save_queue()
            except Exception as e:
                logger.error(f"Failed to save queue: {str(e)}")
        
        if broadcast:
            try:
                current_state = {
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                }
                socketio.emit(SOCKET_EVENTS['QUEUE']['UPDATE'], 
                            current_state,
                            broadcast=True)
            except Exception as e:
                logger.error(f"Failed to broadcast queue update: {str(e)}")

def check_queue_and_start_countdown():
    """Start match acceptance immediately when the queue fills."""
    players = None

    with queue_lock:
        if pending_match:
            return
        if len(matchmaking_queue) >= MAX_LOBBY_PLAYERS:
            players = list(matchmaking_queue[:MAX_LOBBY_PLAYERS])

    if players:
        try:
            start_match_acceptance(players)
        except Exception as e:
            logger.error(f"Error starting match acceptance: {e}")

def add_to_queue(username):
    if username not in matchmaking_queue:
        matchmaking_queue.append(username)
        player_activity[username] = {'status': 'queued'}
        save_queue()
        print(f"Queue updated: {matchmaking_queue}")  # Debug log
        return True
    else:
        print(f"User {username} is already in the queue.")  # Debug log
        return False

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
            selected_map = random.choice(AVAILABLE_MAPS)
            logger.info(f"No votes cast, randomly selected map: {selected_map}")
        
        # Update lobby with selected map
        lobby['selected_map'] = selected_map
        lobby['step'] = 3
        lobby['countdown'] = None
        
        # Notify clients about selected map
        socketio.emit('lobby_update', {
            'step': 3,
            'selected_map': selected_map,
            'lobby_id': lobby_id,
            'vote_counts': vote_counts if 'vote_counts' in locals() else {},
            'announcement': None
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
            if any(player not in matchmaking_queue for player in players):
                logger.warning("Cannot create lobby; one or more accepted players are no longer in queue")
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
                    player_activity[player]['status'] = 'in_lobby'
            save_queue()

        broadcast_queue_update()

        for player in players:
            sid = player_activity.get(player, {}).get('sid')
            if sid:
                socketio.server.enter_room(sid, lobby_id)

        logger.info(f"Created lobby {lobby_id} with players {players}")
        for player in players:
            sid = player_activity.get(player, {}).get('sid')
            if sid:
                socketio.emit(SOCKET_EVENTS['LOBBY']['CREATED'], lobby_data, room=sid)
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

#PERIODIC FUNCTIONS
def cleanup_player(username):
    """Clean up player data when they disconnect"""
    # Remove from queue
    if username in matchmaking_queue:
        matchmaking_queue.remove(username)
        save_queue(matchmaking_queue)
    
    # Remove from player activity
    if username in player_activity:
        del player_activity[username]
    
    # Check and cleanup lobbies
    for lobby_id, lobby in list(lobbies.items()):
        if username in lobby['players']:
            # Notify other players in lobby
            emit('player_disconnected', {
                'username': username,
                'msg': f'Player {username} has disconnected'
            }, room=lobby_id)
            
            # Remove the lobby if it's no longer viable
            del lobbies[lobby_id]  # This is too aggressive - we shouldn't delete the lobby

def cleanup_stale_players():
    while True:
        try:
            current_time = time.time()
            stale_timeout = 300  # 5 minutes
            
            with queue_lock:
                for username, data in list(player_activity.items()):
                    if (data.get('status') == 'disconnected' and 
                        current_time - data.get('last_seen', 0) > stale_timeout):
                        logger.info(f"Removing stale player {username}")
                        if username in matchmaking_queue:
                            matchmaking_queue.remove(username)
                        del player_activity[username]
                        broadcast_queue_update()
                        
        except Exception as e:
            logger.error(f"Error in cleanup_stale_players: {str(e)}")
        finally:
            eventlet.sleep(60)  # Run every minute

def cleanup_on_start():
    global matchmaking_queue
    global player_activity
    global lobbies
    global countdown_active
    global pending_match
    
    logger.info("Cleaning up stale state...")
    matchmaking_queue = []
    player_activity = {}
    lobbies = {}
    countdown_active = False
    pending_match = None
    save_queue()
    logger.info("Cleanup complete")

def start_periodic_tasks():
    def safe_start(task, name):
        try:
            socketio.start_background_task(task)
            logger.info(f"Started {name} task")
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")

    safe_start(periodic_queue_management, "queue management")
    safe_start(cleanup_stale_players, "stale player cleanup")

def start_auth_timeout(sid, username=None):
    """Start authentication timeout for new connections"""
    def check_auth():
        eventlet.sleep(10)  # 10 second timeout
        if not username:
            # For unauthenticated connections
            if any(data.get('sid') == sid and data.get('status') == 'connected' 
                  for data in player_activity.values()):
                logger.warning(f"Authentication timeout for SID: {sid}")
                socketio.disconnect(sid)
        else:
            # For authenticated connections
            user_data = player_activity.get(username)
            if user_data and user_data['sid'] == sid and user_data['status'] == 'connected':
                logger.warning(f"Authentication timeout for user: {username}")
                socketio.disconnect(sid)
    
    eventlet.spawn(check_auth)

def periodic_queue_management():
    while True:
        try:
            with app.app_context():
                global countdown_active
                if not countdown_active:
                    broadcast_queue_update()
        except Exception as e:
            logger.error(f"Error in queue management: {str(e)}")
        eventlet.sleep(5)




@socketio.on('*')  
@handle_socket_data
def catch_all(event, *args):
    """Debug handler to catch all events"""
    logger.info(f"=== Caught unhandled event ===")
    logger.info(f"Event: {event}")
    logger.info(f"Data: {args}")

#SOCKET EVENT HANDLERS
@socketio.on(SOCKET_EVENTS['CONNECTION']['CONNECT'])
def handle_connect(auth):
    """Handle new socket connections"""
    try:
        # Get auth data from handshake
        auth = request.args.get('auth', {})
        if isinstance(auth, str):
            try:
                auth = json.loads(auth)
            except:
                auth = {}
                
        token = auth.get('token')
        username = auth.get('username')
        sid = request.sid
        
        logger.debug(f"Connection attempt - SID: {sid}, Username: {username}, Has token: {bool(token)}")
        
        # Allow unauthenticated connections initially
        if not token:
            logger.debug(f"Allowing unauthenticated connection for initial auth")
            emit(SOCKET_EVENTS['COUNTDOWN']['PAUSE_STATE'], {
                'paused': is_countdown_paused()
            })
            return True
            
        # For authenticated connections, verify token
        try:
            verify_jwt_in_request()
            current_user = get_jwt_identity()
            
            if username and current_user != username:
                logger.warning(f"Token username mismatch: {current_user} != {username}")
                return False

            # Update player activity for authenticated users
            if username:
                player_activity[username] = {
                    'sid': request.sid,
                    'username': username,
                    'status': 'idle',
                    'last_seen': time.time()
                }
            
            logger.info(f"Authenticated connection successful for {username}")
            emit(SOCKET_EVENTS['COUNTDOWN']['PAUSE_STATE'], {
                'paused': is_countdown_paused()
            })
            return True
            
        except Exception as e:
            logger.error(f"JWT verification failed: {str(e)}")
            return False
            
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        return False

@socketio.on(SOCKET_EVENTS['CONNECTION']['DISCONNECT'])
@handle_socket_data
def handle_disconnect(reason=None):
    try:
        sid = request.sid
        username = None
        
        # Find username by sid
        for user, data in player_activity.items():
            if data.get('sid') == sid:
                username = user
                break
        
        if username:
            logger.info(f"User {username} disconnected. Reason: {reason}")
            
            # Update player activity status
            if username in player_activity:
                player_activity[username]['status'] = 'disconnected'
                player_activity[username]['last_seen'] = time.time()
                
                # Check if player was in a lobby
                lobby_id = player_activity[username].get('lobby_id')
                if lobby_id and lobby_id in lobbies:
                    lobby = lobbies[lobby_id]
                    # Add to disconnected players set
                    if 'disconnected_players' not in lobby:
                        lobby['disconnected_players'] = set()
                    lobby['disconnected_players'].add(username)
                    logger.info(f"Added {username} to disconnected players in lobby {lobby_id}")
                    
                    # Notify other players in lobby
                    emit('player_disconnected', {
                        'username': username,
                        'temporary': True
                    }, room=lobby_id)
            
            # Handle queue state if needed
            if username in matchmaking_queue:
                if pending_match and username in pending_match.get('players', []):
                    cancel_pending_match(
                        'A player disconnected during match acceptance.',
                        remove_players=[username]
                    )
                broadcast_queue_update()
                
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {str(e)}")

#AUTHENTICATION HANDLERS
@socketio.on(SOCKET_EVENTS['AUTH']['REGISTER'])
@handle_socket_data
def register_socket(data):
    try:
        username = data.get('username')
        password = data.get('password')
        
        if not username or not password:
            return {'success': False, 'message': 'Missing credentials'}
            
        if username in users:
            return {'success': False, 'message': 'Username already exists'}
            
        # Store the new user
        users[username] = {
            'password': password,
            'steam_id': ''
        }
        save_users()
        
        # Create access token for automatic login
        access_token = create_access_token(identity=username)
        
        logger.info(f"New user registered: {username}")
        return {
            'success': True,
            'message': 'Registration successful',
            'access_token': access_token,
            'profile': get_user_profile(username)
        }
        
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return {'success': False, 'message': 'Registration failed'}
        
@socketio.on(SOCKET_EVENTS['AUTH']['LOGIN'])
@handle_socket_data
def login_socket(data):
    try:
        logger.debug("=== Starting login handler ===")
        logger.debug(f"Login attempt from: {data}")

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            logger.debug("Missing credentials")
            return {
                'success': False,
                'message': 'Missing credentials'
            }

        logger.debug(f"Checking credentials for {username}")
        user_record = get_user_record(username)
        if not user_record or user_record.get('password') != password:
            logger.debug(f"Login failed for user: {username}")
            return {
                'success': False,
                'message': 'Invalid credentials'
            }
        
        logger.debug(f"Login successful for user: {username}")
        access_token = create_access_token(identity=username)
        
        # Check if user was in a lobby before
        active_lobby_id = None
        for lobby_id, lobby in lobbies.items():
            if username in lobby['players']:
                # Only set active lobby if player was disconnected
                if 'disconnected_players' in lobby and username in lobby['disconnected_players']:
                    active_lobby_id = lobby_id
                    lobby['disconnected_players'].remove(username)
                    logger.info(f"Reconnecting {username} to lobby {lobby_id}")
                break
        
        # Update player activity with lobby info if applicable
        player_activity[username] = {
            'sid': request.sid,
            'status': 'in_lobby' if active_lobby_id else 'authenticated',
            'lobby_id': active_lobby_id,
            'last_seen': time.time()
        }
        
        # Join the socket room if user was in a lobby
        if active_lobby_id:
            join_room(active_lobby_id)
            logger.info(f"User {username} rejoined lobby {active_lobby_id} after login")
            
            # Notify other players in lobby
            emit('player_reconnected', {
                'username': username
            }, room=active_lobby_id)
        
        response = {
            'success': True,
            'message': 'Login successful',
            'access_token': access_token,
            'active_lobby': active_lobby_id,
            'profile': get_user_profile(username)
        }
        
        logger.info(f"Sending login response for {username}: {response}")
        return response
            
    except Exception as e:
        logger.error(f"Error in login handler: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': 'Server error occurred'
        }

@socketio.on(SOCKET_EVENTS['AUTH']['AUTHENTICATE'])
@handle_socket_data
def handle_authenticate(data):
    username = data.get('username')
    token = data.get('token')
    logger.info(f"Authentication attempt for {username}, {request.sid}")
    
    try:
        if username:
            player_activity[username] = {
                'status': 'in_queue' if username in matchmaking_queue else 'connected',
                'sid': request.sid,
                'timestamp': time.time()
            }
            
            logger.info(f"Authentication successful for {username}")

            queue_data = build_queue_payload(username=username)
            emit('queue_status', queue_data)

            return True
        
        logger.warning(f"Authentication failed for no username provided")  
        return False
    except Exception as e:
        logger.error(f"Error in handle_authenticate: {str(e)}")
        return False

@socketio.on(SOCKET_EVENTS['PROFILE']['STATUS'])
@handle_socket_data
def handle_profile_status(data=None):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        profile = get_user_profile(username)
        if not profile:
            return {'success': False, 'message': 'User not found'}

        return {'success': True, 'profile': profile}
    except Exception as e:
        logger.error(f"Error in handle_profile_status: {str(e)}")
        return {'success': False, 'message': 'Failed to get profile'}

@socketio.on(SOCKET_EVENTS['PROFILE']['UPDATE_STEAM_ID'])
@handle_socket_data
def handle_update_steam_id(data=None):
    try:
        username = data.get('username') if data else None
        steam_id = data.get('steam_id') if data else None

        if not username:
            return {'success': False, 'message': 'Missing username'}

        record = get_user_record(username)
        if not record:
            return {'success': False, 'message': 'User not found'}

        if username in matchmaking_queue or is_user_in_any_lobby(username):
            return {'success': False, 'message': 'Leave the queue or lobby before changing your Steam ID.'}

        if not is_valid_steam_id(steam_id):
            return {'success': False, 'message': 'Steam ID must be a 17-digit SteamID64.'}

        record['steam_id'] = str(steam_id).strip()
        users[username] = record
        save_users()

        return {
            'success': True,
            'message': 'Steam ID updated.',
            'profile': get_user_profile(username)
        }
    except Exception as e:
        logger.error(f"Error in handle_update_steam_id: {str(e)}")
        return {'success': False, 'message': 'Failed to update Steam ID'}

#QUEUE MANAGEMENT
@socketio.on(SOCKET_EVENTS['QUEUE']['JOIN'])
@handle_socket_data
def handle_join_queue(data):
    """Handle join queue request"""
    try:
        username = data.get('username')

        if not username:
            emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                'success': False,
                'message': 'Missing username'
            })
            return

        with group_lock:
            if get_user_group(username):
                emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'You are in a group. Use group queue.',
                    'inQueue': username in matchmaking_queue,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                })
                return

        if not user_has_steam_id(username):
            emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                **build_queue_payload(username=username),
                'success': False,
                'message': 'Set your Steam ID in your profile before joining the queue.'
            })
            return
        
        with queue_lock:
            if len(matchmaking_queue) >= MAX_LOBBY_PLAYERS:
                emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'Queue is full',
                    'inQueue': False,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                })
                return
            if username not in matchmaking_queue:
                # Add to queue
                matchmaking_queue.append(username)
                player_activity[username] = {
                    'status': 'queued',
                    'sid': request.sid
                }
                save_queue()
                
                # Broadcast update to all clients
                socketio.emit(SOCKET_EVENTS['QUEUE']['UPDATE'], {
                    **build_queue_payload(),
                    'inQueue': username in matchmaking_queue
                })
                
                # Send success response to requester
                emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                    **build_queue_payload(username=username),
                    'inQueue': True
                })
                
                check_queue_and_start_countdown()
            else:
                emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'Already in queue'
                })

    except Exception as e:
        logger.error(f"Error in handle_join_queue: {str(e)}")
        emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
            'success': False,
            'message': str(e)
        })


@socketio.on(SOCKET_EVENTS['QUEUE']['LEAVE'])
@handle_socket_data
def handle_leave_queue(data):
    """Handle leave queue request"""
    try:
        logger.info(f"=== Leave queue handler START ===")
        username = data.get('username')
        cancel_match = False

        # Try to acquire lock with timeout
        if not queue_lock.acquire(timeout=2.0):  # 2 second timeout
            logger.error("Could not acquire queue lock - timeout")
            emit(f"{SOCKET_EVENTS['QUEUE']['LEAVE']}_response", {
                'success': False,
                'message': 'Server busy, please try again',
                'inQueue': True,
                'playersInQueue': len(matchmaking_queue),
                'queue': list(matchmaking_queue)
            })
            return
            
        try:
            if username in matchmaking_queue:
                matchmaking_queue.remove(username)
                save_queue()
                logger.info(f"Removed {username} from queue")
                cancel_match = bool(
                    pending_match and username in pending_match.get('players', [])
                )
                
                # Send immediate response to requesting client
                response = {
                    **build_queue_payload(username=username),
                    'inQueue': False,
                }
                logger.info(f"Sending leave queue response: {response}")
                emit(f"{SOCKET_EVENTS['QUEUE']['LEAVE']}_response", response)
                
                # Broadcast update to ALL clients
                socketio.emit(SOCKET_EVENTS['QUEUE']['UPDATE'], build_queue_payload())
                
            else:
                logger.info(f"{username} not found in queue")
                emit(f"{SOCKET_EVENTS['QUEUE']['LEAVE']}_response", {
                    **build_queue_payload(username=username),
                    'inQueue': False,
                })
        finally:
            queue_lock.release()

        if cancel_match:
            cancel_pending_match(
                'A player left the queue during match acceptance.',
                remove_players=[username]
            )
                
    except Exception as e:
        logger.error(f"Error in handle_leave_queue: {str(e)}", exc_info=True)
        emit(f"{SOCKET_EVENTS['QUEUE']['LEAVE']}_response", {
            'success': False,
            'message': str(e),
            'inQueue': username in matchmaking_queue if username else False,
            'playersInQueue': len(matchmaking_queue),
            'queue': list(matchmaking_queue)
        })
        raise
  
@socketio.on(SOCKET_EVENTS['QUEUE']['STATUS']) #test
@handle_socket_data
def handle_queue_status(data=None):
    """Handle queue status request"""
    try:
        username = data.get('username') if data else None
        logger.debug(f"Queue status request from: {username}")
        
        queue_status = {
            **build_queue_payload(username=username)
        }
        
        logger.debug(f"Queue status for {username}: {queue_status}")
        # Change to emit with _response suffix
        emit(f"{SOCKET_EVENTS['QUEUE']['STATUS']}_response", queue_status)
        
    except Exception as e:
        logger.error(f"Error in handle_queue_status: {str(e)}")
        emit(f"{SOCKET_EVENTS['QUEUE']['STATUS']}_response", {
            'success': False,
            'message': 'Failed to get queue status'
        })

@socketio.on(SOCKET_EVENTS['QUEUE']['ACCEPT_MATCH'])
@handle_socket_data
def handle_accept_match(data=None):
    try:
        username = data.get('username') if data else None
        if not username:
            username = get_username_by_sid(request.sid)
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with queue_lock:
            if not pending_match or username not in pending_match.get('players', []):
                return {'success': False, 'message': 'No pending match to accept'}

            pending_match['accepted'][username] = True
            match_id = pending_match['id']
            all_accepted = all(
                pending_match['accepted'].get(player)
                for player in pending_match['players']
            )
            match_accept = get_match_accept_payload(username)

        broadcast_queue_update()

        if all_accepted:
            finalize_pending_match(match_id)

        return {
            'success': True,
            'matchAccept': match_accept,
            'allAccepted': all_accepted
        }
    except Exception as e:
        logger.error(f"Error in handle_accept_match: {str(e)}")
        return {'success': False, 'message': 'Failed to accept match'}

@socketio.on(SOCKET_EVENTS['QUEUE']['SEED'])
@handle_socket_data
def handle_seed_queue(data=None):
    """Dev-only: seed queue with fake players for testing."""
    if not DEV_MODE:
        return {'success': False, 'message': 'Dev mode disabled'}

    try:
        count = 0
        if isinstance(data, dict):
            count = int(data.get('count', 0))
        if count <= 0:
            return {'success': False, 'message': 'Provide a positive count'}

        bot_names = [
            'Alex', 'Avery', 'Bailey', 'Blake', 'Casey', 'Cameron', 'Drew', 'Eden',
            'Elliot', 'Emerson', 'Finley', 'Finn', 'Frankie', 'Gabe', 'Gray', 'Hayden',
            'Jesse', 'Jordan', 'Kai', 'Lane', 'Logan', 'Luca', 'Morgan', 'Noah',
            'Parker', 'Payton', 'Quinn', 'Reese', 'Riley', 'River', 'Rowan', 'Sam',
            'Sawyer', 'Skyler', 'Spencer', 'Sydney', 'Taylor', 'Toby', 'Wren', 'Zane'
        ]
        added = []
        with queue_lock:
            available = MAX_LOBBY_PLAYERS - len(matchmaking_queue)
            if available <= 0:
                return {'success': False, 'message': 'Queue is full'}
            count = min(count, available)
            existing_bot_names = set()
            for username in matchmaking_queue:
                if username.lower().startswith('bot '):
                    existing_bot_names.add(username[4:].strip())
            available_names = [name for name in bot_names if name not in existing_bot_names]
            if not available_names:
                return {'success': False, 'message': 'No available bot names'}
            random.shuffle(available_names)
            count = min(count, len(available_names))
            for i in range(count):
                name = available_names[i]
                username = f"bot {name}"
                if username in matchmaking_queue:
                    continue
                matchmaking_queue.append(username)
                player_activity[username] = {'status': 'queued'}
                added.append(username)
            save_queue()

        broadcast_queue_update()
        check_queue_and_start_countdown()

        logger.info(f"Seeded queue with {len(added)} fake players")
        return {'success': True, 'added': len(added), 'players': added}
    except Exception as e:
        logger.error(f"Error seeding queue: {str(e)}")
        return {'success': False, 'message': 'Failed to seed queue'}

@socketio.on(SOCKET_EVENTS['QUEUE']['CLEAR'])
@handle_socket_data
def handle_clear_queue(data=None):
    """Dev-only: clear queue and reset lobby/countdown state for testing."""
    if not DEV_MODE:
        return {'success': False, 'message': 'Dev mode disabled'}
    try:
        global countdown_active, pending_match

        logger.info("Dev clear: resetting queue, lobbies, and countdown state")

        # Stop queue countdowns immediately
        countdown_active = False
        pending_match = None
        set_countdown_paused(False)

        # Cancel any lobby countdown loops by bumping tokens
        lobby_players = set()
        for lobby in list(lobbies.values()):
            lobby['countdown_token'] = lobby.get('countdown_token', 0) + 1
            lobby['countdown'] = None
            lobby['voting_countdown'] = None
            lobby_players.update(lobby.get('players', []))

        # Clear lobbies entirely
        lobbies.clear()

        # Clear queue and reset player statuses
        with queue_lock:
            matchmaking_queue.clear()
            save_queue()

        for username, data in player_activity.items():
            data['status'] = 'authenticated'
            data.pop('lobby_id', None)

        broadcast_queue_update()
        broadcast_open_lobbies_update()
        socketio.emit(SOCKET_EVENTS['COUNTDOWN']['PAUSE_STATE'], {
            'paused': False
        })
        return {'success': True}
    except Exception as e:
        logger.error(f"Error clearing queue: {str(e)}")
        return {'success': False, 'message': 'Failed to clear queue'}

@socketio.on(SOCKET_EVENTS['GROUP']['CREATE'])
@handle_socket_data
def handle_group_create(data=None):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            if get_user_group(username):
                return {'success': False, 'message': 'Already in a group'}
            code = generate_group_code()
            groups[code] = {
                'code': code,
                'leader': username,
                'members': [username]
            }
            user_to_group[username] = code
            existing = player_activity.get(username, {})
            player_activity[username] = {
                **existing,
                'sid': request.sid,
                'last_seen': time.time()
            }

        join_room(code)
        payload = get_group_payload(code)
        broadcast_group_update(code, payload)
        return {'success': True, 'group': payload}
    except Exception as e:
        logger.error(f"Error creating group: {str(e)}")
        return {'success': False, 'message': 'Failed to create group'}

@socketio.on(SOCKET_EVENTS['GROUP']['JOIN'])
@handle_socket_data
def handle_group_join(data=None):
    try:
        username = data.get('username') if data else None
        code = data.get('code') if data else None
        if not username or not code:
            return {'success': False, 'message': 'Missing username or code'}

        code = str(code).strip().upper()

        with group_lock:
            if get_user_group(username):
                return {'success': False, 'message': 'Already in a group'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}
            if len(group['members']) >= MAX_LOBBY_PLAYERS:
                return {'success': False, 'message': 'Group is full'}
            if username not in group['members']:
                group['members'].append(username)
            user_to_group[username] = code
            existing = player_activity.get(username, {})
            player_activity[username] = {
                **existing,
                'sid': request.sid,
                'last_seen': time.time()
            }

        join_room(code)
        payload = get_group_payload(code)
        broadcast_group_update(code, payload)
        return {'success': True, 'group': payload}
    except Exception as e:
        logger.error(f"Error joining group: {str(e)}")
        return {'success': False, 'message': 'Failed to join group'}

@socketio.on(SOCKET_EVENTS['GROUP']['LEAVE'])
@handle_socket_data
def handle_group_leave(data=None):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': True, 'group': None}
            group = groups.get(code)
            if not group:
                user_to_group.pop(username, None)
                return {'success': True, 'group': None}

            if username in group['members']:
                group['members'].remove(username)
            user_to_group.pop(username, None)

            if not group['members']:
                broadcast_group_update(code, None)
                groups.pop(code, None)
                leave_room(code)
                return {'success': True, 'group': None}

            if group['leader'] == username:
                group['leader'] = group['members'][0]

            payload = get_group_payload(code)

        broadcast_group_update(code, payload)
        leave_room(code)
        return {'success': True, 'group': None}
    except Exception as e:
        logger.error(f"Error leaving group: {str(e)}")
        return {'success': False, 'message': 'Failed to leave group'}

@socketio.on(SOCKET_EVENTS['GROUP']['STATUS'])
@handle_socket_data
def handle_group_status(data=None):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            code = get_user_group(username)
            payload = get_group_payload(code) if code else None

        return {'success': True, 'group': payload}
    except Exception as e:
        logger.error(f"Error getting group status: {str(e)}")
        return {'success': False, 'message': 'Failed to get group status'}

@socketio.on(SOCKET_EVENTS['GROUP']['QUEUE'])
@handle_socket_data
def handle_group_queue(data=None):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': False, 'message': 'Not in a group'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}
            if group['leader'] != username:
                return {'success': False, 'message': 'Only the leader can queue the group'}
            members = list(group['members'])
            if len(members) > (MAX_LOBBY_PLAYERS // 2):
                return {'success': False, 'message': 'Group is too large to stay on one team'}

        missing_steam_ids = [member for member in members if not user_has_steam_id(member)]
        if missing_steam_ids:
            return {
                'success': False,
                'message': f"These group members need a Steam ID before queueing: {', '.join(missing_steam_ids)}"
            }

        if any(is_user_in_any_lobby(member) for member in members):
            return {'success': False, 'message': 'A group member is already in a lobby'}

        with queue_lock:
            if any(member in matchmaking_queue for member in members):
                return {'success': False, 'message': 'A group member is already in the queue'}
            if len(matchmaking_queue) + len(members) > MAX_LOBBY_PLAYERS:
                return {'success': False, 'message': 'Queue does not have enough slots'}

            for member in members:
                matchmaking_queue.append(member)
                existing = player_activity.get(member, {})
                player_activity[member] = {
                    **existing,
                    'status': 'queued'
                }

            save_queue()

        broadcast_queue_update()
        check_queue_and_start_countdown()

        return build_queue_payload(username=username)
    except Exception as e:
        logger.error(f"Error queueing group: {str(e)}")
        return {'success': False, 'message': 'Failed to queue group'}

@socketio.on(SOCKET_EVENTS['GROUP']['UNQUEUE'])
@handle_socket_data
def handle_group_unqueue(data=None):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': False, 'message': 'Not in a group'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}
            if group['leader'] != username:
                return {'success': False, 'message': 'Only the leader can leave the queue'}
            members = list(group['members'])

        with queue_lock:
            removed = False
            for member in members:
                if member in matchmaking_queue:
                    matchmaking_queue.remove(member)
                    removed = True
                if member in player_activity:
                    player_activity[member]['status'] = 'authenticated'
            if removed:
                save_queue()

        if removed:
            broadcast_queue_update()

        return {
            'success': True,
            'playersInQueue': len(matchmaking_queue),
            'queue': list(matchmaking_queue)
        }
    except Exception as e:
        logger.error(f"Error unqueueing group: {str(e)}")
        return {'success': False, 'message': 'Failed to leave queue'}

@socketio.on(SOCKET_EVENTS['COUNTDOWN']['TOGGLE_PAUSE'])
@handle_socket_data
def handle_toggle_countdown_pause(data=None):
    """Toggle or set countdown pause state"""
    try:
        desired_state = None
        if isinstance(data, dict) and 'paused' in data:
            desired_state = bool(data.get('paused'))

        if desired_state is None:
            new_state = set_countdown_paused(not is_countdown_paused())
        else:
            new_state = set_countdown_paused(desired_state)

        socketio.emit(SOCKET_EVENTS['COUNTDOWN']['PAUSE_STATE'], {
            'paused': new_state
        })

        return {'success': True, 'paused': new_state}
    except Exception as e:
        logger.error(f"Error in handle_toggle_countdown_pause: {str(e)}")
        return {'success': False, 'message': 'Failed to toggle countdown pause'}

@socketio.on(SOCKET_EVENTS['COUNTDOWN']['STATUS'])
@handle_socket_data
def handle_countdown_status(data=None):
    """Return current countdown pause state"""
    try:
        return {'success': True, 'paused': is_countdown_paused()}
    except Exception as e:
        logger.error(f"Error in handle_countdown_status: {str(e)}")
        return {'success': False, 'message': 'Failed to get countdown status'}

@socketio.on(SOCKET_EVENTS['OPEN_LOBBIES']['STATUS'])
@handle_socket_data
def handle_open_lobbies_status(data=None):
    """Return current open lobbies"""
    try:
        return {
            'success': True,
            'openLobbies': get_open_lobbies(),
            'activeLobbies': get_active_lobbies()
        }
    except Exception as e:
        logger.error(f"Error in handle_open_lobbies_status: {str(e)}")
        return {'success': False, 'message': 'Failed to get open lobbies'}

#LOBBY MANAGEMENT
@socketio.on(SOCKET_EVENTS['LOBBY']['JOIN'])
@handle_socket_data
def handle_join_lobby(data):
    """Handle lobby join request"""
    try:
        lobby_id = data.get('lobby_id')
        username = data.get('username')
        is_rejoin = data.get('rejoin', False)
        allow_new = data.get('allow_new', False)
        
        logger.info(f"Join lobby request from {username} for lobby {lobby_id} (rejoin: {is_rejoin})")
        
        if lobby_id in lobbies:
            lobby = lobbies[lobby_id]
            
            # Check if player is in lobby or was disconnected
            is_lobby_member = username in lobby['players']
            was_disconnected = username in lobby.get('disconnected_players', set())
            has_open_slot = len(lobby['players']) < MAX_LOBBY_PLAYERS
            
            if not is_lobby_member and not (is_rejoin and was_disconnected) and not (allow_new and has_open_slot):
                logger.warning(f"Unauthorized lobby join attempt by {username}")
                return {
                    'success': False,
                    'message': 'Not authorized to join this lobby'
                }
            
            # Handle reconnection
            if was_disconnected:
                lobby['disconnected_players'].remove(username)
                logger.info(f"Player {username} reconnected to lobby {lobby_id}")

            # Allow new player to fill an open lobby
            if allow_new and not is_lobby_member and not was_disconnected:
                lobby['players'].append(username)
                if username in matchmaking_queue:
                    matchmaking_queue.remove(username)
                    save_queue()
                    broadcast_queue_update()
                if 'player_groups' in lobby and username not in lobby['player_groups']:
                    code = user_to_group.get(username)
                    if code and code in groups:
                        lobby['player_groups'][username] = code

                if lobby['teams'].get('team1') or lobby['teams'].get('team2'):
                    # Add to the smaller team
                    if len(lobby['teams']['team1']) <= len(lobby['teams']['team2']):
                        lobby['teams']['team1'].append(username)
                    else:
                        lobby['teams']['team2'].append(username)
                    lobby['captains'] = select_captains(lobby['teams'])
                elif lobby.get('step', 1) >= 2 and len(lobby['players']) >= 2:
                    lobby['teams'] = assign_teams(lobby['players'])
                    lobby['captains'] = select_captains(lobby['teams'])

            # Keep captain data disabled while preserving response shape.
            has_teams = lobby.get('teams') and (
                lobby['teams'].get('team1') or lobby['teams'].get('team2')
            )
            if has_teams:
                lobby['captains'] = select_captains(lobby['teams'])

                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'players': lobby['players'],
                    'teams': lobby['teams'],
                    'captains': lobby.get('captains'),
                    'step': lobby['step']
                }, room=lobby_id)

            broadcast_queue_update()
            broadcast_open_lobbies_update()

            # Join the socket room
            join_room(lobby_id)
            
            # Update player status
            player_activity[username] = {
                'status': 'in_lobby',
                'sid': request.sid,
                'lobby_id': lobby_id,
                'last_seen': time.time()
            }
            
            # Prepare lobby state response
            if 'player_groups' not in lobby:
                lobby['player_groups'] = get_player_groups(lobby.get('players', []))
            lobby_state = {
                'lobby_id': lobby_id,
                'players': lobby['players'],
                'teams': lobby['teams'],
                'captains': lobby.get('captains'),
                'step': lobby['step'],
                'countdown': lobby.get('countdown'),
                'voting_countdown': lobby.get('voting_countdown'),
                'selected_map': lobby.get('selected_map'),
                'server_details': lobby.get('server_details'),
                'map_pool': lobby.get('map_pool', []),
                'map_votes': lobby.get('map_votes', {}),
                'vote_counts': lobby.get('vote_counts', {}),
                'player_groups': lobby.get('player_groups', {}),
                'announcement': lobby.get('announcement')
            }
            
            # Notify other players about reconnection if applicable
            if was_disconnected:
                emit('player_reconnected', {'username': username}, room=lobby_id)
            
            # Send success response with lobby state
            return {
                'success': True,
                'data': lobby_state,
                'message': 'Rejoined lobby successfully' if was_disconnected else 'Joined lobby successfully'
            }
            
        else:
            logger.warning(f"Attempted to join non-existent lobby: {lobby_id}")
            return {
                'success': False,
                'message': 'Lobby not found'
            }
            
    except Exception as e:
        logger.error(f"Error in handle_join_lobby: {str(e)}")
        return {
            'success': False,
            'message': 'Failed to join lobby'
        }

@socketio.on(SOCKET_EVENTS['LOBBY']['LEAVE'])
@handle_socket_data
def handle_leave_lobby(data):
    """Handle lobby leave request"""
    try:
        lobby_id = data.get('lobby_id')
        username = data.get('username', get_username_by_sid(request.sid))
        
        logger.info(f"Leave lobby request from {username} for lobby {lobby_id}")
        
        if not lobby_id or not username:
            return {
                'success': False,
                'message': 'Missing lobby_id or username'
            }
            
        if lobby_id in lobbies:
            lobby = lobbies[lobby_id]
            
            # Remove player from lobby
            if username in lobby['players']:
                lobby['players'].remove(username)
                
                # Remove from teams
                for team in ['team1', 'team2']:
                    if username in lobby['teams'][team]:
                        lobby['teams'][team].remove(username)

                if lobby.get('captains') is not None:
                    lobby['captains'] = select_captains(lobby['teams'])
                
                # Remove from disconnected players if present
                if 'disconnected_players' in lobby and username in lobby['disconnected_players']:
                    lobby['disconnected_players'].remove(username)
                
                # Update player activity
                if username in player_activity:
                    player_activity[username].pop('lobby_id', None)
                    player_activity[username]['status'] = 'authenticated'
                
                # Leave the socket room
                leave_room(lobby_id)
                
                # Notify other players
                emit('player_left', {
                    'username': username,
                    'lobby_id': lobby_id
                }, room=lobby_id)

                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'players': lobby['players'],
                    'teams': lobby['teams'],
                    'captains': lobby.get('captains'),
                    'step': lobby.get('step', 1)
                }, room=lobby_id)
                
                # If lobby is empty, remove it
                if not lobby['players']:
                    del lobbies[lobby_id]
                    logger.info(f"Removed empty lobby {lobby_id}")
                broadcast_queue_update()
                broadcast_open_lobbies_update()
                
                logger.info(f"Player {username} left lobby {lobby_id}")
                return {
                    'success': True,
                    'message': 'Successfully left lobby'
                }
            
        return {
            'success': False,
            'message': 'Lobby not found or player not in lobby'
        }
        
    except Exception as e:
        logger.error(f"Error in handle_leave_lobby: {str(e)}")
        return {
            'success': False,
            'message': 'Failed to leave lobby'
        }

@socketio.on(SOCKET_EVENTS['LOBBY']['SKIP_PHASE'])
@handle_socket_data
def handle_skip_phase(data):
    """Skip current lobby phase and advance to the next one."""
    try:
        lobby_id = data.get('lobby_id')
        lobby = lobbies.get(lobby_id)
        if not lobby:
            return {'success': False, 'message': 'Lobby not found'}

        lobby['skip_phase'] = True
        lobby['countdown_token'] = lobby.get('countdown_token', 0) + 1
        step = lobby.get('step', 1)

        if step == 2:
            selected_map, vote_counts = select_map_from_votes(lobby)
            lobby['selected_map'] = selected_map
            lobby['step'] = 3
            lobby['announcement'] = None
            socketio.emit('lobby_update', {
                'lobby_id': lobby_id,
                'selected_map': selected_map,
                'step': 3,
                'vote_counts': vote_counts,
                'announcement': None
            }, room=lobby_id)
            start_live_roll_monitor(lobby_id)
            lobby['skip_phase'] = False
            return {'success': True, 'step': 3}

        lobby['skip_phase'] = False
        return {'success': False, 'message': 'No skippable phase'}

    except Exception as e:
        logger.error(f"Error in handle_skip_phase: {str(e)}")
        return {'success': False, 'message': 'Failed to skip phase'}

@socketio.on(SOCKET_EVENTS['LOBBY']['PREV_PHASE'])
@handle_socket_data
def handle_prev_phase(data):
    """Dev-only: move lobby back one phase for UI inspection."""
    if not DEV_MODE:
        return {'success': False, 'message': 'Dev mode disabled'}
    try:
        lobby_id = data.get('lobby_id')
        lobby = lobbies.get(lobby_id)
        if not lobby:
            return {'success': False, 'message': 'Lobby not found'}

        # Stop any running countdown loops
        lobby['countdown_token'] = lobby.get('countdown_token', 0) + 1
        lobby['countdown'] = None
        lobby['voting_countdown'] = None
        lobby['skip_phase'] = False

        current_step = lobby.get('step', 2)
        lobby['step'] = max(2, current_step - 1)

        if lobby['step'] == 2:
            lobby['selected_map'] = None
            lobby['map_votes'] = {}
            lobby['vote_counts'] = {}
            lobby['voting_countdown'] = 30

        socketio.emit('lobby_update', {
            'lobby_id': lobby_id,
            'step': lobby['step'],
            'players': lobby.get('players'),
            'teams': lobby.get('teams'),
            'captains': lobby.get('captains'),
            'selected_map': lobby.get('selected_map'),
            'server_details': lobby.get('server_details'),
            'countdown': lobby.get('countdown')
        }, room=lobby_id)

        return {'success': True, 'step': lobby['step']}
    except Exception as e:
        logger.error(f"Error in handle_prev_phase: {str(e)}")
        return {'success': False, 'message': 'Failed to go back a phase'}

@socketio.on(SOCKET_EVENTS['LOBBY']['START'])
@handle_socket_data
def start_lobby(data):
    lobby_id = data.get('lobby_id')
    lobby = lobbies.get(lobby_id)
    if lobby:
        emit(SOCKET_EVENTS['LOBBY']['READY'], {
            'teams': lobby['teams'],
            'map': lobby['selected_map'],
            'server_ip': lobby['server_ip']
        }, room=lobby_id)

@socketio.on(SOCKET_EVENTS['LOBBY']['GET_DATA'])
@handle_socket_data
def get_lobby_data(data):
    lobby_id = data.get('lobby_id')
    lobby = lobbies.get(lobby_id)

    if lobby:
        # Emit the structured lobby data
        emit(SOCKET_EVENTS['LOBBY']['DATA'], {
            'lobby_id': lobby_id,
            'players': lobby['players'],
            'teams': lobby['teams'],
            'captains': lobby.get('captains'),
            'map_pool': lobby.get('map_pool', []),
            'selected_map': lobby.get('selected_map'),
            'server_ip': lobby.get('server_ip'),
            'step': lobby.get('step'),
            'voting_countdown': lobby.get('voting_countdown'),
            'player_groups': lobby.get('player_groups', {}),
            'map_votes': lobby.get('map_votes', {}),
            'vote_counts': lobby.get('vote_counts', {}),
            'announcement': lobby.get('announcement')
        })
    else:
        emit(SOCKET_EVENTS['ERROR'], {'msg': 'Lobby not found.'})

@socketio.on(SOCKET_EVENTS['LOBBY']['SERVER_PRESENCE'])
@handle_socket_data
def get_lobby_server_presence(data):
    try:
        lobby_id = data.get('lobby_id') if data else None
        if not lobby_id:
            return {'success': False, 'message': 'Missing lobby_id'}

        return {
            'success': True,
            'presence': build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=True)
        }
    except ValueError as e:
        return {'success': False, 'message': str(e)}
    except Exception as e:
        logger.error(f"Error in get_lobby_server_presence: {str(e)}")
        return {'success': False, 'message': 'Failed to get lobby server presence'}

@socketio.on(SOCKET_EVENTS['LOBBY']['VOTE_MAP'])
@handle_socket_data
def vote_map(data):
    """Handle map vote from player"""
    try:
        lobby_id = data.get('lobby_id')
        map_choice = data.get('map')
        
        logger.info(f"Received vote request - Lobby: {lobby_id}, Map: {map_choice}")
        
        if not lobby_id or not map_choice:
            logger.error("Missing required data for vote")
            return {'success': False, 'message': 'Missing required data'}
            
        lobby = lobbies.get(lobby_id)
        if not lobby:
            logger.error(f"Lobby {lobby_id} not found")
            return {'success': False, 'message': 'Lobby not found'}
            
        # Get username from request
        username = get_username_by_sid(request.sid)
        if not username:
            logger.error(f"User not found for SID: {request.sid}")
            return {'success': False, 'message': 'User not found'}
            
        logger.info(f"Processing vote for {username} in lobby {lobby_id}")
            
        # Initialize map_votes if not exists
        if 'map_votes' not in lobby:
            lobby['map_votes'] = {}
            
        # Record the vote
        lobby['map_votes'][username] = map_choice
        
        # Count votes for each map
        vote_counts = {}
        for user, vote in lobby['map_votes'].items():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1
        
        logger.info(f"Current votes in lobby {lobby_id}:")
        logger.info(f"Map votes: {lobby['map_votes']}")
        logger.info(f"Vote counts: {vote_counts}")
        
        # Get current countdown from lobby state
        current_countdown = lobby.get('voting_countdown', 15)
        
        # Broadcast updated votes to all players in lobby
        socketio.emit('lobby_countdown_voting', {
            'countdown': current_countdown,
            'lobby_id': lobby_id,
            'type': 'voting',
            'map_votes': lobby['map_votes'],
            'vote_counts': vote_counts
        }, room=lobby_id)
        
        return {'success': True}
        
    except Exception as e:
        logger.error(f"Error in vote_map: {str(e)}")
        return {'success': False, 'message': str(e)}
        
# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler) # Termination signal

#MAIN ENTRY POINT
if __name__ == '__main__':
     cleanup_on_start()
     start_periodic_tasks()
     logger.info("Starting server...")
     try:
         socketio.run(
            app,
            debug=False,
            host=BACKEND_HOST,
            port=BACKEND_PORT,
            use_reloader=False,
            log_output=True,
            allow_unsafe_werkzeug=True,
         )
     except KeyboardInterrupt:
         signal_handler(signal.SIGINT, None)
     except Exception as e:
         logger.error(f"Server error: {e}")
         signal_handler(signal.SIGINT, None)
     finally:
         logger.info("Server stopped")




