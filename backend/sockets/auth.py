import json
import time


def handle_connect_event(
    auth,
    *,
    request,
    logger,
    emit,
    socket_events,
    decode_token,
    is_countdown_paused,
    find_active_lobby_for_user,
    upsert_player_activity,
    join_room,
    get_user_room
):
    try:
        auth = auth or {}
        if isinstance(auth, str):
            try:
                auth = json.loads(auth)
            except Exception:
                auth = {}

        token = auth.get('token')
        username = auth.get('username')
        sid = request.sid

        logger.debug(f"Connection attempt - SID: {sid}, Username: {username}, Has token: {bool(token)}")

        if not token:
            logger.debug("Allowing unauthenticated connection for initial auth")
            emit(socket_events['COUNTDOWN']['PAUSE_STATE'], {
                'paused': is_countdown_paused()
            })
            return True

        try:
            current_user = decode_token(token).get('sub')

            if username and current_user != username:
                logger.warning(f"Token username mismatch: {current_user} != {username}")
                return False

            username = username or current_user
            if username:
                active_lobby_id = find_active_lobby_for_user(username)
                upsert_player_activity(
                    username,
                    sid=request.sid,
                    status='in_lobby' if active_lobby_id else 'idle',
                    lobby_id=active_lobby_id,
                    last_seen=time.time()
                )
                join_room(get_user_room(username))
                if active_lobby_id:
                    join_room(active_lobby_id)

            logger.info(f"Authenticated connection successful for {username}")
            emit(socket_events['COUNTDOWN']['PAUSE_STATE'], {
                'paused': is_countdown_paused()
            })
            return True
        except Exception as e:
            logger.error(f"JWT verification failed: {str(e)}")
            return False
    except Exception as e:
        logger.error(f"Connection error: {str(e)}")
        return False


def handle_disconnect_event(
    reason,
    *,
    request,
    logger,
    get_username_by_sid,
    remove_player_session,
    player_activity,
    lobbies,
    emit,
    matchmaking_queue,
    pending_match,
    cancel_pending_match,
    broadcast_queue_update
):
    try:
        sid = request.sid
        username = get_username_by_sid(sid)

        if username:
            logger.info(f"User {username} disconnected. Reason: {reason}")

            remaining_sessions = remove_player_session(username, sid)
            if remaining_sessions == 0 and username in player_activity:
                player_activity[username]['status'] = 'disconnected'
                player_activity[username]['last_seen'] = time.time()

                lobby_id = player_activity[username].get('lobby_id')
                if lobby_id and lobby_id in lobbies:
                    lobby = lobbies[lobby_id]
                    if 'disconnected_players' not in lobby:
                        lobby['disconnected_players'] = set()
                    lobby['disconnected_players'].add(username)
                    logger.info(f"Added {username} to disconnected players in lobby {lobby_id}")

                    emit('player_disconnected', {
                        'username': username,
                        'temporary': True
                    }, room=lobby_id)

            if username in matchmaking_queue:
                broadcast_queue_update()
    except Exception as e:
        logger.error(f"Error in handle_disconnect: {str(e)}")


def register_socket_event(
    data,
    *,
    users,
    save_users,
    create_access_token,
    get_user_profile,
    logger
):
    try:
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return {'success': False, 'message': 'Missing credentials'}

        if username in users:
            return {'success': False, 'message': 'Username already exists'}

        users[username] = {
            'password': password,
            'steam_id': ''
        }
        save_users()

        access_token = create_access_token(identity=username)

        logger.info(f"New user registered: {username}")
        return {
            'success': True,
            'message': 'Registration successful',
            'access_token': access_token,
            'profile': get_user_profile(username)
        }
    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return {'success': False, 'message': 'Registration failed'}


def login_socket_event(
    data,
    *,
    logger,
    get_user_record,
    create_access_token,
    find_active_lobby_for_user,
    lobbies,
    upsert_player_activity,
    request,
    join_room,
    get_user_room,
    emit,
    get_user_profile
):
    try:
        logger.debug("=== Starting login handler ===")
        logger.debug(f"Login attempt from: {data}")

        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            logger.debug("Missing credentials")
            return {
                'success': False,
                'message': 'Missing credentials'
            }

        logger.debug(f"Checking credentials for {username}")
        user_record = get_user_record(username)
        if not user_record or user_record.get('password') != password:
            logger.debug(f"Login failed for user: {username}")
            return {
                'success': False,
                'message': 'Invalid credentials'
            }

        logger.debug(f"Login successful for user: {username}")
        access_token = create_access_token(identity=username)

        active_lobby_id = find_active_lobby_for_user(username)
        if active_lobby_id:
            lobby = lobbies.get(active_lobby_id)
            if lobby and 'disconnected_players' in lobby and username in lobby['disconnected_players']:
                lobby['disconnected_players'].remove(username)
                logger.info(f"Reconnecting {username} to lobby {active_lobby_id}")

        upsert_player_activity(
            username,
            sid=request.sid,
            status='in_lobby' if active_lobby_id else 'authenticated',
            lobby_id=active_lobby_id,
            last_seen=time.time()
        )
        join_room(get_user_room(username))

        if active_lobby_id:
            join_room(active_lobby_id)
            logger.info(f"User {username} rejoined lobby {active_lobby_id} after login")

            emit('player_reconnected', {
                'username': username
            }, room=active_lobby_id)

        response = {
            'success': True,
            'message': 'Login successful',
            'access_token': access_token,
            'active_lobby': active_lobby_id,
            'profile': get_user_profile(username)
        }

        logger.info(f"Sending login response for {username}: {response}")
        return response
    except Exception as e:
        logger.error(f"Error in login handler: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': 'Server error occurred'
        }


def handle_authenticate_event(
    data,
    *,
    request,
    logger,
    upsert_player_activity,
    matchmaking_queue,
    join_room,
    get_user_room,
    build_queue_payload,
    emit
):
    username = data.get('username')
    logger.info(f"Authentication attempt for {username}, {request.sid}")

    try:
        if username:
            upsert_player_activity(
                username,
                sid=request.sid,
                status='in_queue' if username in matchmaking_queue else 'connected',
                timestamp=time.time()
            )
            join_room(get_user_room(username))

            logger.info(f"Authentication successful for {username}")

            queue_data = build_queue_payload(username=username)
            emit('queue_status', queue_data)

            return True

        logger.warning("Authentication failed for no username provided")
        return False
    except Exception as e:
        logger.error(f"Error in handle_authenticate: {str(e)}")
        return False
