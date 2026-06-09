def _user_in_queue(matchmaking_queue, username):
    if isinstance(matchmaking_queue, dict):
        return any(username in queue for queue in matchmaking_queue.values())
    return username in matchmaking_queue


def get_user_profile(username, get_user_record, matchmaking_queue, is_user_in_any_lobby, admin_steam_ids=None):
    record = get_user_record(username)
    if not record:
        return None
    steam_id = str(record.get('steam_id', '') or '').strip()
    admin_steam_ids = admin_steam_ids or set()
    return {
        'username': username,
        'steam_id': steam_id,
        'has_steam_id': bool(steam_id),
        'steam_id_locked': _user_in_queue(matchmaking_queue, username) or is_user_in_any_lobby(username),
        'is_admin': bool(steam_id and steam_id in admin_steam_ids)
    }


def is_valid_steam_id(steam_id):
    steam_id = str(steam_id or '').strip()
    return steam_id.isdigit() and len(steam_id) == 17


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
