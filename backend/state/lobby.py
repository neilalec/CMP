from app_state import MATCH_ACCEPT_COUNTDOWN


def _app():
    import app as backend_app
    return backend_app


def is_user_in_any_lobby(username):
    app = _app()
    for lobby in app.lobbies.values():
        if lobby.get('step') == 5:
            continue
        if username in lobby.get('players', []):
            return True
    return False


def find_active_lobby_for_user(username):
    app = _app()
    if not username:
        return None
    for lobby_id, lobby in app.lobbies.items():
        if lobby.get('step') == 5:
            continue
        if username in lobby.get('players', []):
            return lobby_id
    return None


def get_user_room(username):
    return f"user:{username}"


def get_player_sids(username):
    app = _app()
    data = app.player_activity.get(username, {})
    sessions = data.get('sids')
    if not isinstance(sessions, set):
        sessions = set()
    legacy_sid = data.get('sid')
    if legacy_sid:
        sessions.add(legacy_sid)
    return sessions


def upsert_player_activity(username, sid=None, **updates):
    import time

    app = _app()
    existing = app.player_activity.get(username, {})
    sessions = get_player_sids(username)
    if sid:
        sessions.add(sid)

    entry = {
        **existing,
        **updates,
        'sids': sessions,
        'last_seen': updates.get('last_seen', time.time())
    }

    if sid:
        entry['sid'] = sid
    elif sessions and not entry.get('sid'):
        entry['sid'] = next(iter(sessions))

    app.player_activity[username] = entry
    return entry


def remove_player_session(username, sid):
    app = _app()
    if username not in app.player_activity:
        return 0
    entry = app.player_activity[username]
    sessions = get_player_sids(username)
    sessions.discard(sid)
    entry['sids'] = sessions
    if entry.get('sid') == sid:
        entry['sid'] = next(iter(sessions), None)
    app.player_activity[username] = entry
    return len(sessions)


def emit_active_lobby_sync(username, lobby_id):
    app = _app()
    if not username:
        return
    app.socketio.emit('active_lobby_sync', {
        'lobby_id': lobby_id
    }, room=get_user_room(username))


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


def get_open_lobbies():
    app = _app()
    open_lobbies = []
    for lobby_id, lobby in app.lobbies.items():
        if lobby.get('step') == 5:
            continue
        players = lobby.get('players', [])
        max_players = int(lobby.get('max_players') or app.MAX_LOBBY_PLAYERS)
        if len(players) < max_players:
            open_lobbies.append({
                'lobby_id': lobby_id,
                'players': players,
                'player_profiles': build_player_profile_map(players),
                'open_slots': max_players - len(players),
                'max_players': max_players,
                'queue_mode': lobby.get('queue_mode'),
                'queue_label': lobby.get('queue_label'),
                'step': lobby.get('step', 1),
                'captains': lobby.get('captains'),
                'selected_map': lobby.get('selected_map')
            })
    return open_lobbies


def get_active_lobbies():
    app = _app()
    active = []
    for lobby_id, lobby in app.lobbies.items():
        if lobby.get('step') == 5:
            continue
        players = lobby.get('players', [])
        max_players = int(lobby.get('max_players') or app.MAX_LOBBY_PLAYERS)
        if len(players) < max_players:
            continue
        active.append({
            'lobby_id': lobby_id,
            'players': players,
            'player_profiles': build_player_profile_map(players),
            'open_slots': max(0, max_players - len(players)),
            'max_players': max_players,
            'queue_mode': lobby.get('queue_mode'),
            'queue_label': lobby.get('queue_label'),
            'step': lobby.get('step', 1),
            'captains': lobby.get('captains'),
            'selected_map': lobby.get('selected_map')
        })
    return active


def broadcast_open_lobbies_update():
    app = _app()
    try:
        app.socketio.emit(
            app.SOCKET_EVENTS['OPEN_LOBBIES']['UPDATE'],
            {
                'openLobbies': get_open_lobbies(),
                'activeLobbies': get_active_lobbies()
            },
            room=None
        )
        save_runtime_state = getattr(app, 'save_runtime_state', None)
        if save_runtime_state:
            save_runtime_state()
    except Exception as e:
        app.logger.error(f"Error in broadcast_open_lobbies_update: {str(e)}")


def get_username_by_sid(sid):
    app = _app()
    app.logger.debug(f"Looking up username for SID: {sid}")
    app.logger.debug(f"Current player activity: {app.player_activity}")

    for username, data in app.player_activity.items():
        if data.get('sid') == sid or sid in get_player_sids(username):
            app.logger.info(f"Found username {username} for SID {sid}")
            return username

    app.logger.warning(f"No username found for SID: {sid}")
    return None


def get_match_accept_payload(username=None):
    app = _app()
    for queue_mode, pending in app.pending_match.items():
        if not pending:
            continue
        if username and username not in pending.get('players', []):
            continue
        accepted_players = [
            player for player, accepted in pending.get('accepted', {}).items()
            if accepted
        ]
        return {
            'active': True,
            'queueMode': queue_mode,
            'players': list(pending.get('players', [])),
            'playerProfiles': build_player_profile_map(pending.get('players', [])),
            'acceptedPlayers': accepted_players,
            'acceptedCount': len(accepted_players),
            'requiredCount': len(pending.get('players', [])),
            'countdown': pending.get('countdown', MATCH_ACCEPT_COUNTDOWN),
            'hasAccepted': bool(username and pending.get('accepted', {}).get(username))
        }
    return None
