def _app():
    import app as backend_app
    return backend_app


def get_group_payload(code):
    app = _app()
    group = app.groups.get(code)
    if not group:
        return None
    members = list(group['members'])
    return {
        'code': group['code'],
        'leader': group['leader'],
        'members': members,
        'player_profiles': build_player_profile_map(members)
    }


def build_player_profile_map(players):
    app = _app()
    profiles = {}
    get_user_profile = getattr(app, 'get_user_profile', None)
    for username in players or []:
        profile = (get_user_profile(username) if get_user_profile else {}) or {}
        profiles[username] = {
            'display_name': profile.get('display_name') or username,
            'steam_id': profile.get('steam_id') or ''
        }
    return profiles


def get_user_group(username):
    app = _app()
    code = app.user_to_group.get(username)
    if code and code in app.groups:
        return code
    if code and code not in app.groups:
        app.user_to_group.pop(username, None)
    return None


def get_player_groups(players):
    app = _app()
    if not players:
        return {}
    result = {}
    with app.group_lock:
        for player in players:
            code = app.user_to_group.get(player)
            if code and code in app.groups:
                result[player] = code
    return result


def broadcast_group_update(code, group_payload=None):
    app = _app()
    payload = {
        'success': True,
        'group': group_payload
    }
    app.socketio.emit(app.SOCKET_EVENTS['GROUP']['UPDATE'], payload, room=code)
    save_runtime_state = getattr(app, 'save_runtime_state', None)
    if save_runtime_state:
        save_runtime_state()
