#IMPORTS AND INITIAL SETUP
import eventlet, json, time, logging, random
eventlet.monkey_patch()

from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from flask_socketio import SocketIO, emit, join_room, leave_room
from collections import Counter
from flask_cors import CORS
from threading import Lock



logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('matchmaking.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

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
             "methods": ["GET", "POST", "OPTIONS"],
             "allow_headers": ["*"],
             "supports_credentials": True
         }
     })
logger.info("CORS configured")


#JWT setup
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['JWT_SECRET_KEY'] = 'your-jwt-secret-key-here'
jwt = JWTManager(app)


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
    cors_credentials=True
)
logger.info("SocketIO initialized")


#HELPER FUNCTIONS
def broadcast_queue_update():
    """Broadcast queue status to all connected clients"""
    base_queue_data = {
        'playersInQueue': len(matchmaking_queue),
        'queue': list(matchmaking_queue),  # Convert to list to ensure it's serializable
        'timestamp': time.time(), # Optional: add timestamp for debugging
    }
    logger.info(f"Broadcasting queue update: {base_queue_data}")
    

    try:
        # Get all connected socket IDs
        connected_sids = request.namespace.manager.get_participants('/')
        
        for sid in connected_sids:
            # Find username associated with this socket ID
            username = None
            for player, data in player_activity.items():
                if data.get('sid') == sid:
                    username = player
                    break
            
            # Create personalized queue data for this client
            client_queue_data = {
                **base_queue_data,
                'inQueue': username in matchmaking_queue if username else False
            }
            
            logger.debug(f"Sending queue update to {username} (SID: {sid}): {client_queue_data}")
            socketio.emit('queue_update', client_queue_data, room=sid)

        logger.info(f"Queue update broadcast complete. Active players: {len(connected_sids)}")
        
    except Exception as e:
        logger.error(f"Error broadcasting queue update: {str(e)}")
        logger.exception("Full traceback:")
# Save queue to file
def save_queue():
    """Save queue to file"""

    with queue_lock:
        with open('queue.json', 'w') as f:
            json.dump(matchmaking_queue, f)
# Load queue from file
def load_queue():
    """Load queue from file"""
    with queue_lock:
        try:
            with open('queue.json', 'r') as f:
                return json.load(f)
        except:
            return []

def assign_teams(players):
    random.shuffle(players)
    mid = len(players) // 2
    return {'team1': players[:mid], 'team2': players[mid:]}

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

def cleanup_on_start():
    global matchmaking_queue
    global player_activity
    
    logger.info("Cleaning up stale state...")
    matchmaking_queue = []
    player_activity = {}
    save_queue()
    logger.info("Cleanup complete")

def create_lobby():
    players = [matchmaking_queue.pop(0), matchmaking_queue.pop(0)]
    save_queue(matchmaking_queue)

    lobby_id = f"lobby_{players[0]}_vs_{players[1]}"
    lobbies[lobby_id] = {
        'lobby_id': lobby_id,
        'players': players,
        'teams': assign_teams(players),
        'map_votes': {},
        'selected_map': None,
        'server_ip': '127.0.0.1:12345'
    }

    print(f"Lobby created: {lobby_id}")
    for player in players:
        join_room(lobby_id)
        emit('lobby_assigned', {'lobby_id': lobby_id}, to=request.sid)

    emit('lobby_update', {'lobby_id': lobby_id, 'players': players}, room=lobby_id)

def create_match():
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

def log_event(event_type, data):
    """Structured logging helper"""
    logger.info(json.dumps({
        'event': event_type,
        'data': data,
        'timestamp': time.time()
    }))





#GLOBAL VARIABLES AND DATA STRUCTURES
QUEUE_FILE = 'queue.json'
queue_lock = Lock()
users = {
    'neil': '123', 
    'sam': '123'
}
matchmaking_queue = load_queue()
player_activity = {}
lobbies= {}















@app.route('/health')
def health_check():
    return jsonify({"status": "ok"})

@app.route('/test')
def test():
    logger.info("Test route hit")
    return 'Server is running'

# Add this after SocketIO initialization
@socketio.on_error_default
def default_error_handler(e):
    print(f"SocketIO error: {str(e)}")
    print(f"Error type: {type(e)}")
    print(f"Request SID: {request.sid}")
    print(f"Request event: {request.event}")

    import traceback
    print(f"Traceback: {traceback.format_exc()}")

















#AUTHENTICATION HANDLERS
@socketio.on('register')
def register_socket(data):
    username = data.get('username')
    password = data.get('password')
    if username in users:
        emit('registration_error', {'msg': 'User already exists!'})
    else:
        users[username] = password
        emit('registration_success', {'msg': 'User registered successfully!'})

@socketio.on('login')
def login_socket(data):
    print(f"Login attempt from: {data}")
    username = data.get('username')
    password = data.get('password')

    print(f"Checking credentials for {username}")
    if users.get(username) != password:
        print(f"Login failed for user: {username}")
        emit('login_error', {'msg': 'Bad username or password!'})
    else:
        print(f"Login successful for user: {username}")
        access_token = create_access_token(identity=username)
        # Track the session ID with the username
        player_activity[username] = {'sid': request.sid, 'status': 'idle'}
        emit('login_success', {'access_token': access_token})

@socketio.on('protected')
@jwt_required()
def protected_socket(data):
    current_user = get_jwt_identity()
    emit('protected_response', {'logged_in_as': current_user})

@socketio.on('test')
def test_socket(data):
    emit('test_response', {'message': 'Hello from Flask WebSocket!'})

@socketio.on('message')
def handle_message(data):
    print(f'Received message: {data}')
    socketio.send('Hello from Flask WebSocket!')
    emit('message', {'data': f'Hello from Flask! You said: {data}'})  # Send a response back to the client          

@socketio.on('authenticate')
def handle_authenticate(data):
    username = data.get('username')
    token = data.get('token')
    
    logger.info(f"Authentication attempt for {username}, {request.sid}")
    
    if username:
        player_activity[username] = {
            'status': 'in_queue' if username in matchmaking_queue else 'connected',
            'sid': request.sid,
            'timestamp': time.time()
        }
        
        logger.info(f"Authentication successful for {username}")
        emit('queue_status', {
            'inQueue': username in matchmaking_queue,
            'playersInQueue': len(matchmaking_queue),
            'queue': matchmaking_queue
        })
        return True
    return False







#QUEUE MANAGEMENT
@socketio.on('join-queue')
def handle_join_queue(data):
    username = data.get('username')
    print(f"Join queue request from: {username} (SID: {request.sid})")
    
    if not username:
        print("Join queue failed - No username provided")
        emit('queue_joined', {
            'success': False,
            'message': 'No username provided',
            'inQueue': False
        })
        return

    with queue_lock:  # Thread safety
        try:
            print(f"Current queue before join: {matchmaking_queue}")
            
            if username in matchmaking_queue:
                print(f"Join queue failed - Already in queue: {username}")
                emit('queue_joined', {
                    'success': False,
                    'message': 'Already in queue',
                    'inQueue': True,
                    'playersInQueue': len(matchmaking_queue)
                })
                return
                
            # Add to persistent queue
            matchmaking_queue.append(username)
            save_queue()
            
            # Update player status
            player_activity[username] = {
                 'status': 'in_queue',
                'sid': request.sid,
                'timestamp': time.time()
            }
            
            print(f"Queue after join: {matchmaking_queue}")
            print(f"Player activity after join: {player_activity}")
            
            # Send immediate confirmation to the joining player
            print(f"Sending queue_joined confirmation to {username} (SID: {request.sid})")
            emit('queue_joined', {
                'success': True,
                'playersInQueue': len(matchmaking_queue),
                'inQueue': True
            })
            
            # Broadcast queue update to all players
            print("Broadcasting queue update to all players")
            broadcast_queue_update()
            
            # Check for match
            if len(matchmaking_queue) >= 2:
                print("Sufficient players for match, attempting to create")
                create_match()
                
        except Exception as e:
            print(f"Error in handle_join_queue: {str(e)}")
            emit('queue_joined', {
                'success': False,
                'message': 'Server error occurred',
                'inQueue': username in matchmaking_queue
            })

@socketio.on('find-match')
def find_match_socket(data):
    username = data.get('username')
    if add_to_queue(username):
        emit('queue_update', {'playersInQueue': len(matchmaking_queue)}, broadcast=True)

    with queue_lock:
        # Attempt to create matches
        while len(matchmaking_queue) >= 2:
            create_lobby()

@socketio.on('leave-queue')
def handle_leave_queue(data):
    username = data.get('username')
    print(f"Leave queue request from: {username}")
    
    with queue_lock:  # Thread safety
        if username in matchmaking_queue:
            # Remove from persistent queue
            matchmaking_queue.remove(username)
            save_queue()
            
            # Update player status
            if username in player_activity:
                player_activity[username]['status'] = 'connected'
            
            print(f"Queue after leave: {matchmaking_queue}")
            broadcast_queue_update()

@socketio.on('get-queue-status')
def handle_queue_status(data):
    username = data.get('username')
    with queue_lock:
        status = {
            'inQueue': username in matchmaking_queue,
            'playersInQueue': len(matchmaking_queue),
            'queue': matchmaking_queue
        }
        emit('queue_status', status)
        logger.debug(f"Queue status for {username}: {status}")



#LOBBY MANAGEMENT
@socketio.on('get-lobby-data')
def get_lobby_data(data):
    lobby_id = data.get('lobby_id')
    lobby = lobbies.get(lobby_id)

    if lobby:
        # Ensure teams are assigned if not already done
        if not lobby['teams'].get('team1') or not lobby['teams'].get('team2'):
            lobby['teams'] = assign_teams(lobby['players'])
        
        # Emit the structured lobby data
        emit('lobby_data', {
            'lobby_id': lobby_id,
            'players': lobby['players'],
            'teams': lobby['teams'],  # Expecting 'team1' and 'team2'
            'selected_map': lobby.get('selected_map'),
            'server_ip': lobby.get('server_ip')
        })
    else:
        emit('error', {'msg': 'Lobby not found.'})

@socketio.on('vote-map')
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

            emit('map_selected', {'map': lobby['selected_map']}, room=lobby_id)

@socketio.on('start-lobby')
def start_lobby(data):
    lobby_id = data.get('lobby_id')
    lobbies = lobbies.get(lobby_id)
    if lobbies:
        emit('lobby_ready', {
            'teams': lobbies['teams'],
            'map': lobbies['selected_map'],
            'server_ip': lobbies['server_ip']
        }, room=lobby_id)





#SOCKET EVENT HANDLERS
@socketio.on('connect')
def handle_connect():
    logger.info(f"New connection attempt from SID: {request.sid}")


    # Try to get auth data from connection
    auth = None
    try:
        auth = request.args.get('auth', {})
        if isinstance(auth, str):
            auth = json.loads(auth)
    except Exception as e:
        logger.error(f"Error parsing auth: {e}")
        auth = {}
    
    logger.info(f"Auth data received: {auth}")
    username = auth.get('username')
    
    # Clean up any existing connections for this SID
    for existing_username, data in player_activity.items():
        if data.get('sid') == request.sid:
            logger.info(f"Cleaning up existing connection for {existing_username}")
            # Don't remove from queue, just update connection status
            data['status'] = 'disconnected'
            data['timestamp'] = time.time()
            break
    
    # If we have a username in auth, set up their connection
    if username:
        logger.info(f"User {username} connected with SID: {request.sid}")
        player_activity[username] = {
            'status': 'in_queue' if username in matchmaking_queue else 'connected',
            'sid': request.sid,
            'timestamp': time.time()
        }
    else:
        logger.info("Awaiting authentication...")
    
    return True  # Allow connection in all cases

@socketio.on('disconnect')
def handle_disconnect(reason):
    logger.info(f"Client disconnected: {request.sid} (Reason: {reason})")
    
    # Find the disconnected user
    for username, data in player_activity.items():
        if data.get('sid') == request.sid:
            logger.info(f"User {username} disconnected")
            
            # Update their status but don't remove from queue
            data['status'] = 'disconnected'
            data['timestamp'] = time.time()
            
            # If they've been disconnected too long, remove them from queue
            # This cleanup can be done in a separate periodic task
            if time.time() - data['timestamp'] > 300:  # 5 minutes
                logger.info(f"Removing {username} from queue due to long disconnect")
                player_activity.pop(username)
                if username in matchmaking_queue:
                    matchmaking_queue.remove(username)
                save_queue()
                broadcast_queue_update()
            break










#MAIN ENTRY POINT
if __name__ == '__main__':
     cleanup_on_start()
     logger.info("Starting server...")
     socketio.run(
        app,
        debug=False,
        host='0.0.0.0',
        port=5000,
        use_reloader=False,
        log_output=True,
     )
     logger.info("Server started")
