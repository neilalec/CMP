def _app():
    import app as backend_app
    return backend_app


def is_user_in_any_lobby(username):
    app = _app()
    for lobby in app.lobbies.values():
        if username in lobby.get('players', []):
            return True
    return False


def find_active_lobby_for_user(username):
    app = _app()
    if not username:
        return None
    for lobby_id, lobby in app.lobbies.items():
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


def get_open_lobbies():
    app = _app()
    open_lobbies = []
    for lobby_id, lobby in app.lobbies.items():
        players = lobby.get('players', [])
        if len(players) < app.MAX_LOBBY_PLAYERS:
            open_lobbies.append({
                'lobby_id': lobby_id,
                'players': players,
                'open_slots': app.MAX_LOBBY_PLAYERS - len(players),
                'max_players': app.MAX_LOBBY_PLAYERS,
                'step': lobby.get('step', 1),
                'captains': lobby.get('captains'),
                'selected_map': lobby.get('selected_map')
            })
    return open_lobbies


def get_active_lobbies():
    app = _app()
    active = []
    for lobby_id, lobby in app.lobbies.items():
        players = lobby.get('players', [])
        if len(players) < app.MAX_LOBBY_PLAYERS:
            continue
        active.append({
            'lobby_id': lobby_id,
            'players': players,
            'open_slots': max(0, app.MAX_LOBBY_PLAYERS - len(players)),
            'max_players': app.MAX_LOBBY_PLAYERS,
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
    if not app.pending_match:
        return None

    accepted_players = [
        player for player, accepted in app.pending_match.get('accepted', {}).items()
        if accepted
    ]
    return {
        'active': True,
        'players': list(app.pending_match.get('players', [])),
        'acceptedPlayers': accepted_players,
        'acceptedCount': len(accepted_players),
        'requiredCount': len(app.pending_match.get('players', [])),
        'countdown': app.pending_match.get('countdown', app.MATCH_ACCEPT_COUNTDOWN),
        'hasAccepted': bool(username and app.pending_match.get('accepted', {}).get(username))
    }
