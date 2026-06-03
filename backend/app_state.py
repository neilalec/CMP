import os
from threading import Lock, RLock

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

queue_lock = RLock()
countdown_pause_lock = RLock()
group_lock = RLock()
users = {}
matchmaking_queue = []
player_activity = {}
lobbies = {}
pending_match = None
groups = {}
user_to_group = {}
GROUP_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
GROUP_CODE_LENGTH = 6
