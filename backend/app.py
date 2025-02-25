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
users = {
    'neil': '123', 
    'sam': '123'
}
QUEUE_CHECK_INTERVAL = 5
CLEANUP_INTERVAL = 30
SYNC_INTERVAL = 10

load_dotenv()

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
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('matchmaking.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Reduce engineio/socketio logging
logging.getLogger('engineio').setLevel(logging.INFO)
logging.getLogger('socketio').setLevel(logging.INFO)
logging.getLogger('werkzeug').setLevel(logging.INFO)

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
        'READY': 'lobby_ready'
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
    logger=True,
    engineio_logger=True,
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
    for sid_key, username in player_activity.items():
        if sid_key == sid:
            return username
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
        
        def countdown():
            nonlocal countdown_start
            while countdown_start > 0:
                # Check if we should continue countdown
                with queue_lock:
                    if len(matchmaking_queue) < 2:
                        logger.info("Canceling countdown - not enough players")
                        return
                    
                    # Broadcast countdown to all clients
                    socketio.emit(SOCKET_EVENTS['QUEUE']['UPDATE'], {
                        'success': True,
                        'playersInQueue': len(matchmaking_queue),
                        'queue': list(matchmaking_queue),
                        'countdown': countdown_start
                    })
                
                countdown_start -= 1
                eventlet.sleep(1)
            
            # Create lobby when countdown ends
            # Double check we still have enough players
            with queue_lock:
                if len(matchmaking_queue) >= 2:
                    create_lobby()
        
        # Start countdown in background
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
        if countdown is not None:
            queue_status['countdown'] = countdown

        # Broadcast to all clients without specifying a room
        socketio.emit(
            SOCKET_EVENTS['QUEUE']['UPDATE'], 
            queue_status,
            room=None
        )
        
        logger.debug(f"Broadcasting queue update to all clients: {queue_status}")
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
                
                # Create new lobby with unique ID
                lobby_id = f"lobby_{int(time.time())}"
                teams = assign_teams(players)
                
                lobbies[lobby_id] = {
                    'lobby_id': lobby_id,
                    'players': players,
                    'teams': teams,
                    'step': 1,
                    'map_votes': {},
                    'selected_map': None,
                    'server_ip':None
                }

                # Remove players from queue BEFORE notifying them
                for player in players:
                    if player in matchmaking_queue:
                        matchmaking_queue.remove(player)
                    if player in player_activity:
                        player_activity[player]['status'] = 'in_lobby'
                
                save_queue()
                broadcast_queue_update()
                
                for player in players:
                    if player in player_activity:
                        sid = player_activity[player].get('sid')
                        if sid:
                            socketio.emit(SOCKET_EVENTS['LOBBY']['CREATED'], {  # CREATED not CREATE
                                    'lobby_id': lobby_id,
                                    'players': players,
                                    'teams': teams,
                                    'step': 1
                                }, room=sid)
                return True
            except Exception as e:
                logger.error(f"Error creating lobby: {str(e)}")
                return False


    """Create a match when enough players are in queue"""
    with queue_lock:
        if len(matchmaking_queue) >= 2:
            # Get first two players
            players = matchmaking_queue[:2]
            
            # Create new lobby
            lobby_id = f"lobby_{time.time()}"
            lobbies[lobby_id] = {
                'lobby_id': lobby_id,
                'players': players,
                'teams': {'team1': [], 'team2': []},
                'map_votes': {},
                'selected_map': None,
                'server_ip': '127.0.0.1:12345',
            }
            
            # Remove players from queue
            for player in players:
                matchmaking_queue.remove(player)
            save_queue()
            
            # Notify players
            for player in players:
                if player in player_activity:
                    sid = player_activity[player].get('sid')
                    if sid:
                        socketio.emit('match_found', {
                            'lobby_id': lobby_id,
                            'players': players
                        }, room=sid)
            broadcast_queue_update()  

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
            del lobbies[lobby_id]
            emit('lobby_closed', {
                'msg': 'Lobby closed due to player disconnection'
            }, room=lobby_id)

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
                with queue_lock:
                    # Check for lobby creation
                    if len(matchmaking_queue) >= 2:
                        create_lobby()
                    # Broadcast updates
                    broadcast_queue_update()
        except Exception as e:
            logger.error(f"Error in queue management: {str(e)}")
        eventlet.sleep(5)  # Every 5 seconds

@socketio.on('*')  # Add this at the top of your socket handlers
@handle_socket_data
def catch_all(event, *args):
    """Debug handler to catch all events"""
    logger.info(f"=== Caught unhandled event ===")
    logger.info(f"Event: {event}")
    logger.info(f"Data: {args}")

#SOCKET EVENT HANDLERS
@socketio.on(SOCKET_EVENTS['CONNECTION']['CONNECT'])
@handle_socket_data
def handle_connect(auth):
    """Handle new socket connections"""
    try:
        token = auth.get('token') or request.args.get('token')
        username = auth.get('username') or request.args.get('username')
        sid = request.sid
        logger.debug(f"Connection attempt from {username}")
        
        if not token or not username:
            logger.debug("No credentials provided, allowing anonymous connection")
            return True
            
        try:
            # Verify JWT token
            decoded = verify_jwt_in_request()
            current_user = get_jwt_identity()
            
            if current_user != username:
                logger.warning(f"Token username mismatch: {current_user} != {username}")
                return False

            # Update player activity
            player_activity[username] = {
                'sid': request.sid,
                'username': username,
                'status': 'idle',
                'last_seen': time.time()
            }
            
            # Broadcast current queue status to all clients
            queue_status = {
                'inQueue': username in matchmaking_queue,
                'playersInQueue': len(matchmaking_queue),
                'queue': list(matchmaking_queue)
            }
            socketio.emit(SOCKET_EVENTS['QUEUE']['UPDATE'], queue_status)
            
            logger.info(f"User {username} authenticated successfully")
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
            
            # Only remove from queue if it's an explicit disconnect, not a refresh
            if reason != 'transport close' and username in matchmaking_queue:
                matchmaking_queue.remove(username)
                broadcast_queue_update()
            
            if username in player_activity:
                # Don't delete, just mark as disconnected
                player_activity[username]['status'] = 'disconnected'
                player_activity[username]['last_seen'] = time.time()
                
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {str(e)}")

#AUTHENTICATION HANDLERS
@socketio.on(SOCKET_EVENTS['AUTH']['REGISTER'])
@handle_socket_data
def register_socket(data):
    username = data.get('username')
    password = data.get('password')
    if username in users:
        emit('registration_error', {'msg': 'User already exists!'})
    else:
        users[username] = password
        emit('registration_success', {'msg': 'User registered successfully!'})

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
            emit(f"{SOCKET_EVENTS['AUTH']['LOGIN']}_response", {
                'success': False,
                'message': 'Missing credentials'
            })
            return

        logger.debug(f"Checking credentials for {username}")
        if users.get(username) != password:
            logger.debug(f"Login failed for user: {username}")
            emit(f"{SOCKET_EVENTS['AUTH']['LOGIN']}_response", {
                'success': False,
                'message': 'Invalid credentials'
            })
        else:
            logger.debug(f"Login successful for user: {username}")
            access_token = create_access_token(identity=username)
            emit(f"{SOCKET_EVENTS['AUTH']['LOGIN']}_response", {
                'success': True,
                'message': 'Login successful',
                'access_token': access_token
            })
    except Exception as e:
        logger.error(f"Error in login handler: {str(e)}", exc_info=True)
        emit(f"{SOCKET_EVENTS['AUTH']['LOGIN']}_response", {
            'success': False,
            'message': 'Server error occurred'
        })
    
    logger.debug("=== Finished login handler ===")

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
        logger.info(f"Join queue request from: {username}")
        
        with queue_lock:
            if username not in matchmaking_queue:
                matchmaking_queue.append(username)
                save_queue()
                
                # Send immediate response to requesting client
                emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                    'success': True,
                    'inQueue': True,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                })

                
                # Broadcast update to ALL clients including sender
                socketio.emit(SOCKET_EVENTS['QUEUE']['UPDATE'], {
                    'success': True,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                }, room=None)  # This ensures ALL clients get the update

                check_queue_and_start_countdown()
                
            else:
                emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'Already in queue',
                    'inQueue': True,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                })

    except Exception as e:
        logger.error(f"Error in handle_join_queue: {str(e)}")
        emit(f"{SOCKET_EVENTS['QUEUE']['JOIN']}_response", {
            'success': False,
            'message': 'Failed to join queue',
            'inQueue': False,
            'playersInQueue': len(matchmaking_queue),
            'queue': list(matchmaking_queue)
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
        logger.info(f"Join lobby request from {username} for lobby {lobby_id}")
        
        if lobby_id in lobbies:
            lobby = lobbies[lobby_id]
            
            # Verify player is supposed to be in this lobby
            if username not in lobby['players']:
                logger.warning(f"Unauthorized lobby join attempt by {username}")
                emit('error', {'message': 'Not authorized to join this lobby'})
                return
            
            # Join the socket room
            join_room(lobby_id)
            
            # Update player status
            if username in player_activity:
                player_activity[username]['status'] = 'in_lobby'
            
            # Send current lobby state
            emit(SOCKET_EVENTS['LOBBY']['UPDATE'], {
                'lobby_id': lobby_id,
                'players': lobby['players'],
                'teams': lobby['teams'],
                'step': lobby['step'],
                'selected_map': lobby.get('selected_map'),
                'server_ip': lobby.get('server_ip')
            }, room=lobby_id)
            
            logger.info(f"Player {username} joined lobby {lobby_id}")
        else:
            logger.warning(f"Attempted to join non-existent lobby: {lobby_id}")
            emit('error', {'message': 'Lobby not found'})
            
    except Exception as e:
        logger.error(f"Error in handle_join_lobby: {str(e)}")
        emit('error', {'message': 'Failed to join lobby'})

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
    lobby_id = data.get('lobby_id')
    player = data.get('player')
    vote = data.get('vote')

    lobby = lobbies.get(lobby_id)
    if lobby:
        lobby['map_votes'][player] = vote

        # Check if all players have voted
        if len(lobby['map_votes']) == len(lobby['players']):
            vote_counts = Counter(lobby['map_votes'].values())
            max_votes = max(vote_counts.values())
            tied_maps = [m for m, v in vote_counts.items() if v == max_votes]
            lobby['selected_map'] = random.choice(tied_maps) if len(tied_maps) > 1 else tied_maps[0]

            emit(SOCKET_EVENTS['LOBBY']['MAP_SELECTED'], {'map': lobby['selected_map']}, room=lobby_id)

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




