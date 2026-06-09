import os
from threading import Lock, RLock

QUEUE_CHECK_INTERVAL = 5
CLEANUP_INTERVAL = 30
SYNC_INTERVAL = 10
countdown_active = False
countdown_paused = False
countdown_pause_lock = RLock()
MATCH_ACCEPT_COUNTDOWN = int(os.getenv('MATCH_ACCEPT_COUNTDOWN', '30'))
LIVE_ROLL_READY_RATIO = float(os.getenv('LIVE_ROLL_READY_RATIO', '0.9'))
LIVE_ROLL_READY_GRACE_SECONDS = int(os.getenv('LIVE_ROLL_READY_GRACE_SECONDS', '600'))
LIVE_ROLL_POLL_SECONDS = int(os.getenv('LIVE_ROLL_POLL_SECONDS', '5'))
LIVE_ROLL_RETRY_SECONDS = int(os.getenv('LIVE_ROLL_RETRY_SECONDS', '15'))
LIVE_ROLL_TEAM_SWAP_RETRY_SECONDS = int(os.getenv('LIVE_ROLL_TEAM_SWAP_RETRY_SECONDS', '10'))
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
ALL_HOTDROP_MAPS = [
    'HotDrop_SumariBala',
    'HotDrop_Narva',
    'HotDrop_Harju',
    'HotDrop_Goose_Bay',
    'HotDrop_BlackCoast',
    'HotDrop_Fallujah',
    'HotDrop_Mutaha',
    'HotDrop_Chora',
    'HotDrop_Yehorivka',
    'HotDrop_Skorpo'
]
QUEUE_MODES = {
    'skirmish': {
        'id': 'skirmish',
        'label': '20v20 Skirmish',
        'short_label': 'Skirmish',
        'max_players': 40,
        'team_size': 20,
        'map_pool': ALL_SKIRMISH_MAPS,
    },
    'hotdrop': {
        'id': 'hotdrop',
        'label': '30v30 Hotdrop',
        'short_label': 'Hotdrop',
        'max_players': 60,
        'team_size': 30,
        'map_pool': ALL_HOTDROP_MAPS,
    }
}
DEFAULT_QUEUE_MODE = 'skirmish'
MAX_LOBBY_PLAYERS = max(mode['max_players'] for mode in QUEUE_MODES.values())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_QUEUE_FILE = os.path.join(BASE_DIR, 'queue.json')
LEGACY_USERS_FILE = os.path.join(BASE_DIR, 'users.json')
DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'app.db'))
DEV_MODE = os.getenv('CMP_DEV_MODE', '0') == '1'
DEV_LIVE_ROLL_OVERRIDE_USERNAME = os.getenv('DEV_LIVE_ROLL_OVERRIDE_USERNAME', 'neil').strip().lower()
PASSWORD_AUTH_ENABLED = os.getenv(
    'CMP_PASSWORD_AUTH_ENABLED',
    '1' if DEV_MODE else '0'
) == '1'
JWT_ACCESS_TOKEN_EXPIRES_HOURS = int(os.getenv('JWT_ACCESS_TOKEN_EXPIRES_HOURS', '168'))
AUTH_RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('AUTH_RATE_LIMIT_WINDOW_SECONDS', '300'))
AUTH_LOGIN_MAX_ATTEMPTS = int(os.getenv('AUTH_LOGIN_MAX_ATTEMPTS', '10'))
AUTH_REGISTER_MAX_ATTEMPTS = int(os.getenv('AUTH_REGISTER_MAX_ATTEMPTS', '5'))
SQUADJS_BRIDGE_URL = os.getenv('SQUADJS_BRIDGE_URL', 'http://127.0.0.1:3001').rstrip('/')
SQUADJS_BRIDGE_TOKEN = os.getenv('SQUADJS_BRIDGE_TOKEN', '')
SQUAD_SERVER_NAME = os.getenv('SQUAD_SERVER_NAME', '').strip()
SQUAD_SERVER_PASSWORD = os.getenv('SQUAD_SERVER_PASSWORD', '').strip()
SQUAD_SERVER_CONNECT_ADDRESS = os.getenv('SQUAD_SERVER_CONNECT_ADDRESS', '').strip()
FRONTEND_ORIGINS = [
    origin.strip()
    for origin in os.getenv('FRONTEND_ORIGINS', 'http://localhost:5173').split(',')
    if origin.strip()
]
BACKEND_PUBLIC_URL = os.getenv('BACKEND_PUBLIC_URL', 'http://localhost:5000').rstrip('/')
BACKEND_HOST = os.getenv('BACKEND_HOST', '0.0.0.0')
BACKEND_PORT = int(os.getenv('BACKEND_PORT', '5000'))
BRIDGE_ERROR_LOG_INTERVAL_SECONDS = int(os.getenv('BRIDGE_ERROR_LOG_INTERVAL_SECONDS', '30'))
ADMIN_STEAM_IDS = {
    steam_id.strip()
    for steam_id in os.getenv('ADMIN_STEAM_IDS', '').split(',')
    if steam_id.strip()
}

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
matchmaking_queue = {
    mode_id: []
    for mode_id in QUEUE_MODES
}
player_activity = {}
lobbies = {}
pending_match = {
    mode_id: None
    for mode_id in QUEUE_MODES
}
groups = {}
user_to_group = {}
GROUP_CODE_ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
GROUP_CODE_LENGTH = 6
