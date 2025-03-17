#IMPORTS AND INITIAL SETUP
import eventlet, json, time, logging, random, asyncio, signal, sys, os
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

#GLOBAL VARIABLES AND DATA STRUCTURES
QUEUE_FILE = 'queue.json'
queue_lock = RLock()
USERS_FILE = 'users.json'
QUEUE_CHECK_INTERVAL = 5
CLEANUP_INTERVAL = 30
SYNC_INTERVAL = 10
countdown_active = False
AVAILABLE_MAPS = ['Map 1', 'Map 2', 'Map 3', 'Map 4', 'Map 5']

load_dotenv()

def load_users():
    """Load users from file"""
    try:
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_users():
    """Save users to file"""
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

# Initialize users from file
users = load_users()

# Load queue from file
def load_queue():
    """Load queue from file"""
    with queue_lock:
        try:
            with open('queue.json', 'r') as f:
                return json.load(f)
        except:
            return []

matchmaking_queue = load_queue()
player_activity = {}
lobbies = {}

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

#APP CONFIGURATION
app = Flask(__name__)
logger.info("Starting Flask application")

# CORS setup
logger.info("Configuring CORS")
CORS(app, 
     resources={
         r"/*": {
             "origins": ["http://localhost:5173"],
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
        'MATCH_FOUND': 'match_found'
    },

  
    'LOBBY': {
        'CREATED': 'lobby_created',
        'JOIN': 'join-lobby',
        'LEAVE': 'leave-lobby',
        'UPDATE': 'lobby_update',
        'DATA': 'lobby_data',
        'GET_DATA': 'get-lobby-data',
        'VOTE_MAP': 'vote-map',
        'MAP_SELECTED': 'map_selected',
        'START': 'start-lobby',
        'READY': 'lobby_ready',
        'COUNTDOWN': {
            'TEAMS': 'lobby_countdown_teams',
            'VOTING': 'lobby_countdown_voting'
        },
        'TEAMS_ASSIGNED': 'teams_assigned',
    },

    'MESSAGE': 'message',
}; 

# At the top of your file, after SOCKET_EVENTS definition
logger.info("=== Socket Events Configuration ===")
logger.info(f"Queue Leave Event: {SOCKET_EVENTS['QUEUE']['LEAVE']}")
logger.info(f"Queue Join Event: {SOCKET_EVENTS['QUEUE']['JOIN']}")
logger.info(f"Queue Status Event: {SOCKET_EVENTS['QUEUE']['STATUS']}")
logger.info(f"Queue Update Event: {SOCKET_EVENTS['QUEUE']['UPDATE']}")

# SocketIO setup
logger.info("Initializing SocketIO")
socketio = SocketIO(
    app,
    cors_allowed_origins=["http://localhost:5173"],
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
    return "CMP SocketIO backend running. Frontend handled through Vue.js at http://localhost:5173/"

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
                with open('queue.json', 'w') as f:
                    json.dump(matchmaking_queue, f)
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
    """Check queue size and start countdown if needed"""
    should_start_countdown = False
    
    # Only hold the lock while checking queue size
    with queue_lock:
        if len(matchmaking_queue) >= 2:
            should_start_countdown = True
    
    if should_start_countdown:
        countdown_start = 10
        global countdown_active
        countdown_active = True
        
        def countdown():
            nonlocal countdown_start
            global countdown_active
            
            while countdown_start > 0 and countdown_active:
                try:
                    with queue_lock:
                        if len(matchmaking_queue) < 2:
                            logger.info("Canceling countdown - not enough players")
                            countdown_active = False
                            broadcast_queue_update()  # Send update without countdown
                            return
                        
                        # Only broadcast countdown updates from here
                        broadcast_queue_update(countdown_start)
                    
                    countdown_start -= 1
                    eventlet.sleep(1)
                except Exception as e:
                    logger.error(f"Error in countdown: {e}")
                    countdown_active = False
                    return
            
            if countdown_active:  # Only create lobby if countdown wasn't cancelled
                try:
                    create_lobby()
                except Exception as e:
                    logger.error(f"Error creating lobby after countdown: {e}")
                finally:
                    countdown_active = False

        eventlet.spawn(countdown)

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

def save_queue():
    """Save queue to file"""
    try:
        with open('queue.json', 'w') as f:
            json.dump(matchmaking_queue, f)
    except Exception as e:
        logger.error(f"Failed to save queue: {str(e)}")
        pass

def start_map_voting(lobby_id):
    """Handle map voting countdown and selection"""
    try:
        countdown = 15  # 15 second countdown
        lobby = lobbies.get(lobby_id)
        
        if not lobby:
            logger.error(f"Lobby {lobby_id} not found when starting map vote")
            return
            
        logger.info(f"Starting map voting countdown for lobby {lobby_id}")
        
        # Initialize map_votes if not exists
        if 'map_votes' not in lobby:
            lobby['map_votes'] = {}
            
        # Store the countdown in the lobby state
        lobby['voting_countdown'] = countdown
            
        while countdown > 0:
            # Emit countdown update with specific event
            socketio.emit('lobby_countdown_voting', {
                'countdown': countdown,
                'lobby_id': lobby_id,
                'type': 'voting',
                'map_votes': lobby['map_votes'],
                'vote_counts': {vote: sum(1 for v in lobby['map_votes'].values() if v == vote) 
                              for vote in set(lobby['map_votes'].values())}
            }, room=lobby_id)
            
            logger.debug(f"Map voting countdown: {countdown}, Votes: {lobby['map_votes']}")
            eventlet.sleep(1)
            countdown -= 1
            lobby['voting_countdown'] = countdown
        
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
        
        # Notify clients about selected map
        socketio.emit('lobby_update', {
            'step': 3,
            'selected_map': selected_map,
            'lobby_id': lobby_id,
            'vote_counts': vote_counts if 'vote_counts' in locals() else {}
        }, room=lobby_id)
        
        logger.info(f"Map {selected_map} selected for lobby {lobby_id}")
        
    except Exception as e:
        logger.error(f"Error in map voting countdown: {str(e)}")

@with_retry(max_attempts=3)
def broadcast_queue_update(countdown=None):
    """Broadcast queue status to all connected clients"""
    try:
        logger.debug(f"Queue before broadcast: {list(matchmaking_queue)}")
        
        # Send the same queue status to all clients
        queue_status = {
            'success': True,
            'playersInQueue': len(matchmaking_queue),
            'queue': list(matchmaking_queue)
        }
        # Only add countdown if it's provided and greater than 0
        if countdown is not None and countdown > 0:
            queue_status['countdown'] = countdown

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
def create_lobby():
    """Create a lobby when enough players are in queue"""
    with queue_lock:
        if len(matchmaking_queue) >= 2:
            try:
                # Get first two players
                players = matchmaking_queue[:2]
                
                logger.debug(f"Creating lobby for players: {players}")
                
                # Create new lobby
                lobby_id = f"lobby_{int(time.time())}"
                
                lobby_data = {
                    'lobby_id': lobby_id,
                    'players': players,
                    'teams': {'team1': [], 'team2': []},  # Empty teams initially
                    'step': 1,
                    'selected_map': None,
                    'server_details': None,
                    'countdown_active': True,  # Add countdown flag
                    'map_votes': {},  # Initialize map_votes
                }
                
                lobbies[lobby_id] = lobby_data

                # Update player states and queue
                for player in players:
                    matchmaking_queue.remove(player)
                    if player in player_activity:
                        player_activity[player]['status'] = 'in_lobby'
                
                # Save and broadcast updates
                save_queue()
                broadcast_queue_update()
                
                # Start countdown for team assignment
                eventlet.spawn(start_team_assignment_countdown, lobby_id)
                
                # Notify players about lobby creation
                logger.info(f"Created lobby {lobby_id} with players {players}")
                socketio.emit(SOCKET_EVENTS['LOBBY']['CREATED'], lobby_data)
                
                return True

            except Exception as e:
                logger.error(f"Error creating lobby: {str(e)}")
                if 'lobby_id' in locals() and lobby_id in lobbies:
                    del lobbies[lobby_id]
                return False

        return False

def start_team_assignment_countdown(lobby_id):
    """Handle countdown and team assignment for a lobby"""
    try:
        countdown = 5  # 5 second countdown
        lobby = lobbies.get(lobby_id)
        
        if not lobby:
            return
            
        # Signal start of team assignment
        socketio.emit('lobby_update', {
            'isAssigningTeams': True,
            'lobby_id': lobby_id
        }, room=lobby_id)
            
        while countdown > 0:
            # Emit countdown update with specific event
            socketio.emit('lobby_countdown_teams', {
                'countdown': countdown,
                'lobby_id': lobby_id,
                'type': 'teams'
            }, room=lobby_id)
            
            eventlet.sleep(1)
            countdown -= 1
        
        # Assign teams
        players = lobby['players']
        random.shuffle(players)
        mid = len(players) // 2
        teams = {
            'team1': players[:mid],
            'team2': players[mid:]
        }
        
        # Update lobby with teams
        lobby['teams'] = teams
        lobby['countdown_active'] = False
        
        # First notify about team assignment (step 1)
        socketio.emit('lobby_update', {
            'teams': teams,
            'lobby_id': lobby_id,
            'countdown': None,
            'isAssigningTeams': False,
            'step': 1  # Keep at step 1 to show teams
        }, room=lobby_id)
        
        # Wait 5 seconds to show teams
        eventlet.sleep(5)
        
        # Then move to map voting (step 2) and start voting countdown
        lobby['step'] = 2
        socketio.emit('lobby_update', {
            'step': 2,
            'lobby_id': lobby_id
        }, room=lobby_id)
        
        # Start map voting countdown in a new greenlet
        eventlet.spawn(start_map_voting, lobby_id)
        
        logger.info(f"Teams assigned in lobby {lobby_id}: {teams}")
        
    except Exception as e:
        logger.error(f"Error in team assignment countdown: {str(e)}")

def assign_teams(players):
    random.shuffle(players)
    mid = len(players) // 2
    return {'team1': players[:mid], 'team2': players[mid:]}

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
    
    logger.info("Cleaning up stale state...")
    matchmaking_queue = []
    player_activity = {}
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




@socketio.on('*')  # Add this at the top of your socket handlers
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
        users[username] = password
        save_users()
        
        # Create access token for automatic login
        access_token = create_access_token(identity=username)
        
        logger.info(f"New user registered: {username}")
        return {
            'success': True,
            'message': 'Registration successful',
            'access_token': access_token
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
        if users.get(username) != password:
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
            'active_lobby': active_lobby_id
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

            queue_data = {
                'inQueue': username in matchmaking_queue,
                'playersInQueue': len(matchmaking_queue),
                'queue': list(matchmaking_queue)
            }
            emit('queue_status', queue_data)

            return True
        
        logger.warning(f"Authentication failed for no username provided")  
        return False
    except Exception as e:
        logger.error(f"Error in handle_authenticate: {str(e)}")
        return False

#QUEUE MANAGEMENT
@socketio.on(SOCKET_EVENTS['QUEUE']['JOIN'])
@handle_socket_data
def handle_join_queue(data):
    """Handle join queue request"""
    try:
        username = data.get('username')
        
        with queue_lock:
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
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                })
                
                # Send success response to requester
                emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                    'success': True,
                    'inQueue': True,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
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
                
                # Send immediate response to requesting client
                response = {
                    'success': True,
                    'inQueue': False,   
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                }
                logger.info(f"Sending leave queue response: {response}")
                emit(f"{SOCKET_EVENTS['QUEUE']['LEAVE']}_response", response)
                
                # Broadcast update to ALL clients
                socketio.emit(SOCKET_EVENTS['QUEUE']['UPDATE'], {
                    'success': True,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                })
                
            else:
                logger.info(f"{username} not found in queue")
                emit(f"{SOCKET_EVENTS['QUEUE']['LEAVE']}_response", {
                    'success': True,
                    'inQueue': False,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                })
        finally:
            queue_lock.release()
                
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
            'success': True,  # Add success flag
            'inQueue': username in matchmaking_queue if username else False,
            'playersInQueue': len(matchmaking_queue),
            'queue': list(matchmaking_queue)
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

#LOBBY MANAGEMENT
@socketio.on(SOCKET_EVENTS['LOBBY']['JOIN'])
@handle_socket_data
def handle_join_lobby(data):
    """Handle lobby join request"""
    try:
        lobby_id = data.get('lobby_id')
        username = data.get('username')
        is_rejoin = data.get('rejoin', False)
        
        logger.info(f"Join lobby request from {username} for lobby {lobby_id} (rejoin: {is_rejoin})")
        
        if lobby_id in lobbies:
            lobby = lobbies[lobby_id]
            
            # Check if player is in lobby or was disconnected
            is_lobby_member = username in lobby['players']
            was_disconnected = username in lobby.get('disconnected_players', set())
            
            if not is_lobby_member and not (is_rejoin and was_disconnected):
                logger.warning(f"Unauthorized lobby join attempt by {username}")
                return {
                    'success': False,
                    'message': 'Not authorized to join this lobby'
                }
            
            # Handle reconnection
            if was_disconnected:
                lobby['disconnected_players'].remove(username)
                logger.info(f"Player {username} reconnected to lobby {lobby_id}")
            
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
            lobby_state = {
                'lobby_id': lobby_id,
                'players': lobby['players'],
                'teams': lobby['teams'],
                'step': lobby['step'],
                'selected_map': lobby.get('selected_map'),
                'server_details': lobby.get('server_details')
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
                
                # If lobby is empty, remove it
                if not lobby['players']:
                    del lobbies[lobby_id]
                    logger.info(f"Removed empty lobby {lobby_id}")
                
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
        # Ensure teams are assigned if not already done
        if not lobby['teams'].get('team1') or not lobby['teams'].get('team2'):
            lobby['teams'] = assign_teams(lobby['players'])
        
        # Emit the structured lobby data
        emit(SOCKET_EVENTS['LOBBY']['DATA'], {
            'lobby_id': lobby_id,
            'players': lobby['players'],
            'teams': lobby['teams'],  # Expecting 'team1' and 'team2'
            'selected_map': lobby.get('selected_map'),
            'server_ip': lobby.get('server_ip')
        })
    else:
        emit(SOCKET_EVENTS['ERROR'], {'msg': 'Lobby not found.'})

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
            host='0.0.0.0',
            port=5000,
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




