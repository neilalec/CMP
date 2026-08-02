import re


DISPLAY_NAME_MAX_LENGTH = 32
DISPLAY_NAME_SAFE_RE = re.compile(r'^[A-Za-z0-9 _.\-]+$')


def _user_in_queue(matchmaking_queue, username):
    if isinstance(matchmaking_queue, dict):
        return any(username in queue for queue in matchmaking_queue.values())
    return username in matchmaking_queue


def _profile_display_name(username, record):
    display_name = str(record.get('display_name') or '').strip()
    steam_persona_name = str(record.get('steam_persona_name') or '').strip()
    return display_name or steam_persona_name or username


def get_user_profile(username, get_user_record, matchmaking_queue, is_user_in_any_lobby, admin_steam_ids=None):
    record = get_user_record(username)
    if not record:
        return None
    steam_id = str(record.get('steam_id', '') or '').strip()
    admin_steam_ids = admin_steam_ids or set()
    is_base_admin = bool(steam_id and steam_id in admin_steam_ids) or bool(record.get('is_admin'))
    admin_test_mode_disabled = bool(record.get('admin_test_mode_disabled'))
    return {
        'username': username,
        'display_name': _profile_display_name(username, record),
        'steam_persona_name': str(record.get('steam_persona_name') or '').strip(),
        'display_name_source': str(record.get('display_name_source') or 'legacy').strip(),
        'steam_id': steam_id,
        'has_steam_id': bool(steam_id),
        'steam_id_locked': _user_in_queue(matchmaking_queue, username) or is_user_in_any_lobby(username),
        'is_admin': bool(is_base_admin and not admin_test_mode_disabled),
        'can_toggle_admin': bool(is_base_admin),
        'admin_test_mode_disabled': admin_test_mode_disabled
    }


def is_valid_steam_id(steam_id):
    steam_id = str(steam_id or '').strip()
    return steam_id.isdigit() and len(steam_id) == 17


def normalize_display_name(display_name):
    display_name = re.sub(r'\s+', ' ', str(display_name or '').strip())
    if not display_name:
        raise ValueError('Display name cannot be empty.')
    if len(display_name) > DISPLAY_NAME_MAX_LENGTH:
        raise ValueError(f'Display name must be {DISPLAY_NAME_MAX_LENGTH} characters or fewer.')
    if not DISPLAY_NAME_SAFE_RE.match(display_name):
        raise ValueError('Display name can only use letters, numbers, spaces, underscores, hyphens, and periods.')
    return display_name


def build_profile_status(username, get_user_profile_fn, find_active_lobby_for_user):
    if not username:
        return {'success': False, 'message': 'Missing username'}

    profile = get_user_profile_fn(username)
    if not profile:
        return {'success': False, 'message': 'User not found'}

    active_lobby_id = find_active_lobby_for_user(username)
    return {
        'success': True,
        'profile': {
            **profile,
            'active_lobby': active_lobby_id
        }
    }


def update_steam_id(
    username,
    steam_id,
    get_user_record,
    matchmaking_queue,
    is_user_in_any_lobby,
    save_users,
    users,
    get_user_profile_fn
):
    if not username:
        return {'success': False, 'message': 'Missing username'}

    record = get_user_record(username)
    if not record:
        return {'success': False, 'message': 'User not found'}

    if _user_in_queue(matchmaking_queue, username) or is_user_in_any_lobby(username):
        return {'success': False, 'message': 'Leave the queue or lobby before changing your Steam ID.'}

    if not is_valid_steam_id(steam_id):
        return {'success': False, 'message': 'Steam ID must be a 17-digit SteamID64.'}

    record['steam_id'] = str(steam_id).strip()
    users[username] = record
    save_users()

    return {
        'success': True,
        'message': 'Steam ID updated.',
        'profile': get_user_profile_fn(username)
    }


def update_display_name(
    username,
    display_name,
    get_user_record,
    save_users,
    users,
    get_user_profile_fn
):
    if not username:
        return {'success': False, 'message': 'Missing username'}

    record = get_user_record(username)
    if not record:
        return {'success': False, 'message': 'User not found'}

    try:
        normalized_display_name = normalize_display_name(display_name)
    except ValueError as e:
        return {'success': False, 'message': str(e)}

    record['display_name'] = normalized_display_name
    record['display_name_source'] = 'manual'
    users[username] = record
    save_users()

    return {
        'success': True,
        'message': 'Display name updated.',
        'profile': get_user_profile_fn(username)
    }
