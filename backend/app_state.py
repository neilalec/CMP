import os
from threading import Lock, RLock

QUEUE_CHECK_INTERVAL = 5
CLEANUP_INTERVAL = 30
SYNC_INTERVAL = 10
countdown_active = False
countdown_paused = False
countdown_pause_lock = RLock()
MATCH_ACCEPT_COUNTDOWN = int(os.getenv('MATCH_ACCEPT_COUNTDOWN', '90'))
MAP_VOTE_COUNTDOWN = int(os.getenv('MAP_VOTE_COUNTDOWN', '60'))
OCBT_1V1_MAP_VOTE_COUNTDOWN = int(os.getenv('OCBT_1V1_MAP_VOTE_COUNTDOWN', '15'))
LIVE_ROLL_READY_RATIO = float(os.getenv('LIVE_ROLL_READY_RATIO', '0.95'))
LIVE_ROLL_THRESHOLD_GRACE_SECONDS = int(os.getenv('LIVE_ROLL_THRESHOLD_GRACE_SECONDS', '300'))
LIVE_ROLL_READY_GRACE_SECONDS = int(os.getenv('LIVE_ROLL_READY_GRACE_SECONDS', '600'))
S3O_SMALL_LIVE_ROLL_READY_GRACE_SECONDS = int(os.getenv('S3O_SMALL_LIVE_ROLL_READY_GRACE_SECONDS', '300'))
LIVE_ROLL_POLL_SECONDS = int(os.getenv('LIVE_ROLL_POLL_SECONDS', '5'))
LIVE_ROLL_RETRY_SECONDS = int(os.getenv('LIVE_ROLL_RETRY_SECONDS', '15'))
LIVE_ROLL_TEAM_SWAP_RETRY_SECONDS = int(os.getenv('LIVE_ROLL_TEAM_SWAP_RETRY_SECONDS', '10'))
FINALIZED_LOBBY_CLEANUP_SECONDS = int(os.getenv('FINALIZED_LOBBY_CLEANUP_SECONDS', '300'))
LIVE_MATCH_MAX_SECONDS = int(os.getenv('LIVE_MATCH_MAX_SECONDS', '3600'))
LOBBY_DISCONNECT_GRACE_SECONDS = int(os.getenv('LOBBY_DISCONNECT_GRACE_SECONDS', '600'))
WEB_LOBBY_DISCONNECT_TRACKING_ENABLED = os.getenv('WEB_LOBBY_DISCONNECT_TRACKING_ENABLED', '0') == '1'
ALL_SKIRMISH_MAPS = [
    'CSL_AlBasrahSkirmishv1',
    'CSL_AlBasrahSkirmishv2',
    'CSL_AlBasrahSkirmishv3',
    'CSL_AnvilSkirmishv1',
    'CSL_BlackCoastSkirmishv1',
    'CSL_ChoraSkirmishv1',
    'CSL_FallujahSkirmishv1',
    'CSL_FallujahSkirmishv2',
    'CSL_FoolsRoadSkirmishv1',
    'CSL_FoolsRoadSkirmishv2',
    'CSL_GooseBaySkirmishv1',
    'CSL_GorodokSkirmishv1',
    'CSL_HarjuSkirmishv1',
    'CSL_HarjuSkirmishv2',
    'CSL_KamdeshSkirmishv1',
    'CSL_KohatSkirmishv1',
    'CSL_KokanSkirmishv1',
    'CSL_LashkarSkirmishv1',
    'CSL_LogarSkirmishv1',
    'CSL_ManicouaganSkirmishv1',
    'CSL_ManicouaganSkirmishv2',
    'CSL_ManicouaganSkirmishv3',
    'CSL_MestiaSkirmishv1',
    'CSL_MutahaSkirmishv1',
    'CSL_NarvaSkirmishv1',
    'CSL_SkorpoSkirmishv1',
    'CSL_SumariSkirmishv1',
    'CSL_TallilSkirmishv1',
    'CSL_TallilSkirmishv2',
    'CSL_TallilSkirmishv3',
    'CSL_YehorivkaSkirmishv1',
    'CSL_YehorivkaSkirmishv2',
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
ALL_SEC_26_MAPS = [
    'SEC_26_Mutaha_TC',
    'SEC_26_AlBasrah_AAS_v1',
    'SEC_26_Narva_AAS_v1',
    'SEC_26_Sumari_AAS_v1',
    'SEC_26_Logar_AAS_v1',
    'SEC_26_Harju_AAS_v1',
    'SEC_26_Yehorivka_AAS_v1',
    'SEC_26_Chora_AAS_v1',
    'SEC_26_Fallujah_AAS_v1',
    'SEC_26_BlackCoast_RAAS_v1',
    'SEC_26_Gorodok_RAAS_v1',
]
ALL_SEC_36_MAPS = [
    'SEC_36_Narva_TC',
    'SEC_36_Mutaha_TC_v1',
    'SEC_36_FoolsRoad_AAS_v1',
    'SEC_36_Chora_AAS_v1',
    'SEC_36_Manicouagan_AAS_v1',
    'SEC_36_Logar_AAS_v1',
    'SEC_36_Gorodok_AAS_v2',
    'SEC_36_Mestia_AAS_v1',
    'SEC_36_Kohat_AAS_v1',
    'SEC_36_Yehorivka_RAAS_v1',
]
ALL_SEC_46_MAPS = [
    'SEC_46_Narva_TC',
    'SEC_46_Mutaha_TC_v1',
    'SEC_46_FoolsRoad_AAS_v1',
    'SEC_46_Chora_AAS_v1',
    'SEC_46_Manicouagan_AAS_v1',
    'SEC_46_Logar_AAS_v1',
    'SEC_46_Gorodok_AAS_v2',
    'SEC_46_Mestia_AAS_v1',
    'SEC_46_Kohat_AAS_v1',
    'SEC_46_Yehorivka_RAAS_v1',
]
ALL_RIVALS_36_MAPS = [
    'Rivals_W1_FoolsRoad',
    'Rivals_W2_BlackCoast',
    'Rivals_W3_Kokan',
    'Rivals_W4_Narva',
    'Rivals_W5_AlBasrah',
]
ALL_OSI_40_MAPS = [
    'OSI_W1_Chora',
    'OSI_W2_Mutaha',
    'OSI_W3_Harju',
    'OSI_W4_Yehorivka',
    'OSI_W5_BlackCoast',
    'OSI_W6_AlBasrah',
]
ALL_S3O_MAPS = [
    'S3O_36_Fallujah_AAS_v2',
    'S3O_36_Harju_AAS_v3',
    'S3O_36_Sanxian_AAS_v4',
]
ALL_S3O_SMALL_MAPS = [
    'S3O_Sumari_Tournament_v1',
    'S3O_BlackCoast_Tournament_v1',
    'S3O_Fallujah_Tournament_v1',
    'S3O_FoolsRoad_Tournament_v1',
    'S3O_Kokan_Tournament_v1',
    'S3O_Mutaha_Tournament_v1',
    'S3O_Narva_Tournament_v1',
]
ALL_OCBT_MAPS = [
    'OCBT_UrbanQuarter_AAS_v1',
    'OCBT_UrbanQuarter_AAS_v2',
    'OCBT_UrbanQuarter_AAS_v3',
    'OCBT_Oasis_AAS_v1',
    'OCBT_Oasis_AAS_v2',
    'OCBT_Oasis_AAS_v3',
    'OCBT_Kalinovo_AAS_v1',
    'OCBT_Kalinovo_AAS_v2',
    'OCBT_Kalinovo_AAS_v3',
    'OCBT_AzureIsland_AAS_v1',
    'OCBT_AzureIsland_AAS_v2',
    'OCBT_AzureIsland_AAS_v4',
    'OCBT_Shchyhliivka_AAS_v1',
    'OCBT_Shchyhliivka_AAS_v2',
    'OCBT_Shchyhliivka_AAS_v3',
    'OCBT_Shchyhliivka_AAS_v4',
]
ALL_OCBT_VOTE_MAPS = [
    'OCBT_UrbanQuarter',
    'OCBT_Oasis',
    'OCBT_Kalinovo',
    'OCBT_AzureIsland',
    'OCBT_Shchyhliivka',
]
OCBT_MAP_VARIANTS = {
    'OCBT_UrbanQuarter': [
        'OCBT_UrbanQuarter_AAS_v1',
        'OCBT_UrbanQuarter_AAS_v2',
        'OCBT_UrbanQuarter_AAS_v3',
    ],
    'OCBT_Oasis': [
        'OCBT_Oasis_AAS_v1',
        'OCBT_Oasis_AAS_v2',
        'OCBT_Oasis_AAS_v3',
    ],
    'OCBT_Kalinovo': [
        'OCBT_Kalinovo_AAS_v1',
        'OCBT_Kalinovo_AAS_v2',
        'OCBT_Kalinovo_AAS_v3',
    ],
    'OCBT_AzureIsland': [
        'OCBT_AzureIsland_AAS_v1',
        'OCBT_AzureIsland_AAS_v2',
        'OCBT_AzureIsland_AAS_v4',
    ],
    'OCBT_Shchyhliivka': [
        'OCBT_Shchyhliivka_AAS_v1',
        'OCBT_Shchyhliivka_AAS_v2',
        'OCBT_Shchyhliivka_AAS_v3',
        'OCBT_Shchyhliivka_AAS_v4',
    ],
}
ALL_BALT_26_MAPS = [
    'BALT_26_AlBasrah_AAS_v1',
    'BALT_26_SANXIAN_PAAS_v1',
]
ALL_OUT_OF_THE_BOX_40_MAPS = [
    'OutoftheBox_Tallil',
    'OutoftheBox_Skorpo',
    'OutoftheBox_Sanxian',
    'OutoftheBox_PacificProvingGrounds',
    'OutoftheBox_Mestia',
    'OutoftheBox_Lashkar',
    'OutoftheBox_Kohat',
    'OutoftheBox_AlBasrah',
]
QUEUE_MODES = {
    'skirmish': {
        'id': 'skirmish',
        'label': '20v20 Skirmish Layers',
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
    },
    'sec26': {
        'id': 'sec26',
        'label': '26v26 Squad Esports Cup',
        'short_label': 'SEC 26',
        'max_players': 52,
        'team_size': 26,
        'map_pool': ALL_SEC_26_MAPS,
    },
    'sec36': {
        'id': 'sec36',
        'label': '36v36 Squad Esports Cup',
        'short_label': 'SEC 36',
        'max_players': 72,
        'team_size': 36,
        'map_pool': ALL_SEC_36_MAPS,
    },
    'sec46': {
        'id': 'sec46',
        'label': '46v46 Squad Esports Cup',
        'short_label': 'SEC 46',
        'max_players': 92,
        'team_size': 46,
        'map_pool': ALL_SEC_46_MAPS,
    },
    's30': {
        'id': 's30',
        'label': '36v36 S3O Layers',
        'short_label': 'S3O',
        'max_players': 72,
        'team_size': 36,
        'map_pool': ALL_S3O_MAPS,
    },
    'rivals36': {
        'id': 'rivals36',
        'label': '36v36 Squad Rivals',
        'short_label': 'Rivals',
        'max_players': 72,
        'team_size': 36,
        'map_pool': ALL_RIVALS_36_MAPS,
    },
    'osi40': {
        'id': 'osi40',
        'label': '40v40 Offworld Squad Invitational',
        'short_label': 'OSI',
        'max_players': 80,
        'team_size': 40,
        'map_pool': ALL_OSI_40_MAPS,
    },
    'ocbt15': {
        'id': 'ocbt15',
        'label': '10v10 Open Clan Battle',
        'short_label': 'OCBT',
        'max_players': 20,
        'team_size': 10,
        'map_pool': ALL_OCBT_MAPS,
        'vote_pool': ALL_OCBT_VOTE_MAPS,
        'map_variants': OCBT_MAP_VARIANTS,
    },
    'ocbt5': {
        'id': 'ocbt5',
        'label': '5v5 Open Clan Battle',
        'short_label': 'OCBT 5v5',
        'max_players': 10,
        'team_size': 5,
        'map_pool': ALL_OCBT_MAPS,
        'vote_pool': ALL_OCBT_VOTE_MAPS,
        'map_variants': OCBT_MAP_VARIANTS,
    },
    's3osmall1': {
        'id': 's3osmall1',
        'label': '1v1 S3O Small Format',
        'short_label': 'S3O 1v1',
        'max_players': 2,
        'team_size': 1,
        'map_pool': ALL_S3O_SMALL_MAPS,
    },
    's3osmall2': {
        'id': 's3osmall2',
        'label': '2v2 S3O Small Format',
        'short_label': 'S3O 2v2',
        'max_players': 4,
        'team_size': 2,
        'map_pool': ALL_S3O_SMALL_MAPS,
    },
    's3osmall3': {
        'id': 's3osmall3',
        'label': '3v3 S3O Small Format',
        'short_label': 'S3O 3v3',
        'max_players': 6,
        'team_size': 3,
        'map_pool': ALL_S3O_SMALL_MAPS,
    },
    's3osmall4': {
        'id': 's3osmall4',
        'label': '4v4 S3O Small Format',
        'short_label': 'S3O 4v4',
        'max_players': 8,
        'team_size': 4,
        'map_pool': ALL_S3O_SMALL_MAPS,
    },
    's3osmall5': {
        'id': 's3osmall5',
        'label': '5v5 S3O Layers',
        'short_label': 'S3O 5v5',
        'max_players': 10,
        'team_size': 5,
        'map_pool': ALL_S3O_SMALL_MAPS,
    },
    'balt26': {
        'id': 'balt26',
        'label': '26v26 Balt Layers',
        'short_label': 'BALT',
        'max_players': 52,
        'team_size': 26,
        'map_pool': ALL_BALT_26_MAPS,
    },
    'outofthebox10': {
        'id': 'outofthebox10',
        'label': '10v10 Out of The Box Layers',
        'short_label': 'OOTB 10v10',
        'max_players': 20,
        'team_size': 10,
        'map_pool': ALL_OUT_OF_THE_BOX_40_MAPS,
    },
    'outofthebox15': {
        'id': 'outofthebox15',
        'label': '15v15 Out of The Box Layers',
        'short_label': 'OOTB 15v15',
        'max_players': 30,
        'team_size': 15,
        'map_pool': ALL_OUT_OF_THE_BOX_40_MAPS,
    },
    'outofthebox20': {
        'id': 'outofthebox20',
        'label': '20v20 Out of The Box Layers',
        'short_label': 'OOTB 20v20',
        'max_players': 40,
        'team_size': 20,
        'map_pool': ALL_OUT_OF_THE_BOX_40_MAPS,
    },
    'outofthebox40': {
        'id': 'outofthebox40',
        'label': '30v30 Out of The Box Layers',
        'short_label': 'OOTB 30v30',
        'max_players': 60,
        'team_size': 30,
        'map_pool': ALL_OUT_OF_THE_BOX_40_MAPS,
    }
}
DEFAULT_QUEUE_MODE = 'skirmish'
MAX_LOBBY_PLAYERS = max(mode['max_players'] for mode in QUEUE_MODES.values())

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LEGACY_QUEUE_FILE = os.path.join(BASE_DIR, 'queue.json')
LEGACY_USERS_FILE = os.path.join(BASE_DIR, 'users.json')
DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'app.db'))
DEV_MODE = os.getenv('CMP_DEV_MODE', '0') == '1'
ADMIN_TEAM_ENFORCEMENT_BYPASS_ENABLED = os.getenv('ADMIN_TEAM_ENFORCEMENT_BYPASS_ENABLED', '1') == '1'
LIVE_ROLL_READY_OVERRIDE_ENABLED = os.getenv('LIVE_ROLL_READY_OVERRIDE_ENABLED', '0') == '1'
DEV_LIVE_ROLL_OVERRIDE_USERNAME = os.getenv('DEV_LIVE_ROLL_OVERRIDE_USERNAME', '').strip().lower()
DEV_LIVE_ROLL_OVERRIDE_STEAM_ID = os.getenv('DEV_LIVE_ROLL_OVERRIDE_STEAM_ID', '').strip()
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
STEAM_WEB_API_KEY = os.getenv('STEAM_WEB_API_KEY', '').strip()
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
AUTOMATION_MODES = {'on', 'monitor', 'off'}
AUTOMATION_CONTROL = {
    'mode': os.getenv('AUTOMATION_MODE', 'on').strip().lower()
}
if AUTOMATION_CONTROL['mode'] not in AUTOMATION_MODES:
    AUTOMATION_CONTROL['mode'] = 'on'


def get_map_vote_countdown(queue_mode=None):
    if str(queue_mode or '').strip().lower() == 's3osmall1':
        return OCBT_1V1_MAP_VOTE_COUNTDOWN
    return MAP_VOTE_COUNTDOWN


def is_s3o_small_queue_mode(queue_mode=None):
    return str(queue_mode or '').strip().lower().startswith('s3osmall')


def get_live_roll_ready_grace_seconds(queue_mode=None, default_grace_seconds=None):
    if is_s3o_small_queue_mode(queue_mode):
        return S3O_SMALL_LIVE_ROLL_READY_GRACE_SECONDS
    if default_grace_seconds is not None:
        return default_grace_seconds
    return LIVE_ROLL_READY_GRACE_SECONDS

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
disabled_queue_modes = set()
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
