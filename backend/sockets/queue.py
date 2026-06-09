from services.queue import find_user_queue_mode, get_pending_for_mode, get_queue_for_mode


def handle_join_queue_event(
    data,
    *,
    socket_events,
    emit,
    socketio,
    broadcast_queue_update,
    request,
    logger,
    group_lock,
    get_user_group,
    user_has_steam_id,
    build_queue_payload,
    queue_lock,
    matchmaking_queue,
    queue_modes,
    pending_match,
    lobbies,
    upsert_player_activity,
    save_queue,
    check_queue_and_start_countdown,
    has_available_server_capacity
):
    try:
        username = data.get('username')
        queue_mode = str(data.get('queueMode') or 'skirmish').strip().lower()
        queue_config = queue_modes.get(queue_mode)

        if not username:
            emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                'success': False,
                'message': 'Missing username'
            })
            return

        if not queue_config:
            emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                'success': False,
                'message': 'Unknown queue mode'
            })
            return

        with group_lock:
            if get_user_group(username):
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'You are in a group. Use group queue.',
                    **build_queue_payload(username=username)
                })
                return

        if not user_has_steam_id(username):
            emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                **build_queue_payload(username=username),
                'success': False,
                'message': 'Set your Steam ID in your profile before joining the queue.'
            })
            return

        with queue_lock:
            if not has_available_server_capacity(lobbies, pending_match, server_capacity=1):
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'A match is already using the only available server.',
                    **build_queue_payload(username=username, queue_mode=queue_mode)
                })
                return

            existing_mode = find_user_queue_mode(matchmaking_queue, username)
            if existing_mode and existing_mode != queue_mode:
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    **build_queue_payload(username=username),
                    'success': False,
                    'message': 'You are already queued for another mode.'
                })
                return

            queue = get_queue_for_mode(matchmaking_queue, queue_mode)
            if len(queue) >= queue_config['max_players']:
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'Queue is full',
                    **build_queue_payload(username=username, queue_mode=queue_mode)
                })
                return

            if username not in queue:
                queue.append(username)
                upsert_player_activity(username, sid=request.sid, status='queued')
                save_queue()

                broadcast_queue_update()
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    **build_queue_payload(username=username, queue_mode=queue_mode),
                    'inQueue': True
                })
                check_queue_and_start_countdown()
            else:
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'Already in queue',
                    **build_queue_payload(username=username, queue_mode=queue_mode)
                })
    except Exception as e:
        logger.error(f"Error in handle_join_queue: {str(e)}")
        emit(f"{socket_events['QUEUE']['JOIN']}_response", {
            'success': False,
            'message': str(e)
        })


def handle_leave_queue_event(
    data,
    *,
    socket_events,
    emit,
    socketio,
    broadcast_queue_update,
    logger,
    queue_lock,
    matchmaking_queue,
    save_queue,
    pending_match,
    build_queue_payload,
    cancel_pending_match
):
    username = None
    try:
        logger.info("=== Leave queue handler START ===")
        username = data.get('username')
        queue_mode = str(data.get('queueMode') or '').strip().lower() or None
        cancel_mode = None

        if not queue_lock.acquire(timeout=2.0):
            logger.error("Could not acquire queue lock - timeout")
            emit(f"{socket_events['QUEUE']['LEAVE']}_response", {
                'success': False,
                'message': 'Server busy, please try again',
                **build_queue_payload(username=username, queue_mode=queue_mode)
            })
            return

        try:
            effective_mode = queue_mode or find_user_queue_mode(matchmaking_queue, username)
            queue = get_queue_for_mode(matchmaking_queue, effective_mode) if effective_mode else []
            if username in queue:
                queue.remove(username)
                save_queue()
                logger.info(f"Removed {username} from {effective_mode} queue")
                active_pending = get_pending_for_mode(pending_match, effective_mode)
                cancel_mode = effective_mode if (
                    active_pending and username in active_pending.get('players', [])
                ) else None

                response = {
                    **build_queue_payload(username=username),
                    'inQueue': False,
                }
                emit(f"{socket_events['QUEUE']['LEAVE']}_response", response)
                broadcast_queue_update()
            else:
                emit(f"{socket_events['QUEUE']['LEAVE']}_response", {
                    **build_queue_payload(username=username),
                    'inQueue': False,
                })
        finally:
            queue_lock.release()

        if cancel_mode:
            cancel_pending_match(
                'A player left the queue during match acceptance.',
                remove_players=[username],
                queue_mode=cancel_mode
            )
    except Exception as e:
        logger.error(f"Error in handle_leave_queue: {str(e)}", exc_info=True)
        emit(f"{socket_events['QUEUE']['LEAVE']}_response", {
            'success': False,
            'message': str(e),
            **build_queue_payload(username=username)
        })
        raise


def handle_queue_status_event(data, *, socket_events, emit, logger, build_queue_payload):
    try:
        username = data.get('username') if data else None
        logger.debug(f"Queue status request from: {username}")
        queue_status = {
            **build_queue_payload(username=username)
        }
        logger.debug(f"Queue status for {username}: {queue_status}")
        emit(f"{socket_events['QUEUE']['STATUS']}_response", queue_status)
    except Exception as e:
        logger.error(f"Error in handle_queue_status: {str(e)}")
        emit(f"{socket_events['QUEUE']['STATUS']}_response", {
            'success': False,
            'message': 'Failed to get queue status'
        })


def handle_seed_queue_event(
    data,
    *,
    request,
    socket_events,
    socketio,
    broadcast_queue_update,
    logger,
    dev_mode,
    get_username_by_sid,
    is_admin_user,
    users,
    save_users,
    hash_password,
    queue_lock,
    matchmaking_queue,
    queue_modes,
    upsert_player_activity,
    save_queue,
    build_queue_payload,
    check_queue_and_start_countdown,
    get_pending_match,
    finalize_pending_match
):
    try:
        username = get_username_by_sid(request.sid)
        queue_mode = str((data or {}).get('queueMode') or 'skirmish').strip().lower()
        queue_config = queue_modes.get(queue_mode)
        if not dev_mode:
            return {'success': False, 'message': 'Queue seeding is only available in dev mode'}
        if not is_admin_user(username):
            return {'success': False, 'message': 'Admin access required'}
        if not queue_config:
            return {'success': False, 'message': 'Unknown queue mode'}

        requested_count = int((data or {}).get('count') or queue_config['max_players'])
        requested_count = max(0, min(requested_count, queue_config['max_players']))
        created = []
        queued = []

        with queue_lock:
            queue = get_queue_for_mode(matchmaking_queue, queue_mode)
            available_slots = max(0, queue_config['max_players'] - len(queue))
            seed_count = min(requested_count, available_slots)

            for index in range(1, seed_count + 1):
                bot_username = f'{queue_mode}_bot_{index:02d}'
                suffix = index
                while bot_username in users and bot_username not in queue:
                    suffix += queue_config['max_players']
                    bot_username = f'{queue_mode}_bot_{suffix:02d}'

                if bot_username not in users:
                    users[bot_username] = {
                        'password': hash_password(f'{bot_username}-dev-password'),
                        'steam_id': f'7656119900{suffix:07d}'[-17:]
                    }
                    created.append(bot_username)

                if bot_username not in queue and len(queue) < queue_config['max_players']:
                    queue.append(bot_username)
                    upsert_player_activity(bot_username, status='queued')
                    queued.append(bot_username)

            save_users()
            save_queue()

        check_queue_and_start_countdown()

        pending_match = get_pending_match(queue_mode)
        if pending_match:
            for bot_username in queued:
                if bot_username in pending_match.get('accepted', {}):
                    pending_match['accepted'][bot_username] = True
            if pending_match.get('id') and all(
                pending_match.get('accepted', {}).get(player)
                for player in pending_match.get('players', [])
            ):
                finalize_pending_match(pending_match['id'])

        payload = {
            **build_queue_payload(username=username, queue_mode=queue_mode),
            'seeded': queued,
            'createdUsers': created,
            'success': True,
            'message': f'Seeded {len(queued)} bot players'
        }
        broadcast_queue_update()
        return payload
    except Exception as e:
        logger.error(f"Error in handle_seed_queue: {str(e)}")
        return {'success': False, 'message': 'Failed to seed queue'}


def handle_clear_queue_event(
    data,
    *,
    request,
    socket_events,
    socketio,
    broadcast_queue_update,
    logger,
    dev_mode,
    get_username_by_sid,
    is_admin_user,
    queue_lock,
    matchmaking_queue,
    player_activity,
    save_queue,
    build_queue_payload,
    cancel_pending_match
):
    try:
        username = get_username_by_sid(request.sid)
        queue_mode = str((data or {}).get('queueMode') or '').strip().lower() or None
        if not dev_mode:
            return {'success': False, 'message': 'Queue clearing is only available in dev mode'}
        if not is_admin_user(username):
            return {'success': False, 'message': 'Admin access required'}

        if queue_mode:
            queue = list(get_queue_for_mode(matchmaking_queue, queue_mode))
            cancel_pending_match('Queue cleared by admin.', remove_players=queue, queue_mode=queue_mode)
            with queue_lock:
                cleared = list(get_queue_for_mode(matchmaking_queue, queue_mode))
                matchmaking_queue[queue_mode].clear()
                for player in cleared:
                    if player in player_activity:
                        player_activity[player]['status'] = 'authenticated'
                save_queue()
        else:
            cleared = []
            for mode_id, queue in matchmaking_queue.items():
                mode_players = list(queue)
                if mode_players:
                    cancel_pending_match('Queue cleared by admin.', remove_players=mode_players, queue_mode=mode_id)
                cleared.extend(mode_players)
            with queue_lock:
                for mode_id in matchmaking_queue:
                    matchmaking_queue[mode_id].clear()
                for player in cleared:
                    if player in player_activity:
                        player_activity[player]['status'] = 'authenticated'
                save_queue()

        payload = {
            **build_queue_payload(username=username, queue_mode=queue_mode),
            'success': True,
            'message': f'Cleared {len(cleared)} queued players'
        }
        broadcast_queue_update()
        return payload
    except Exception as e:
        logger.error(f"Error in handle_clear_queue: {str(e)}")
        return {'success': False, 'message': 'Failed to clear queue'}


def handle_accept_match_event(
    data,
    *,
    request,
    logger,
    queue_lock,
    pending_match,
    get_username_by_sid,
    get_match_accept_payload,
    broadcast_queue_update,
    finalize_pending_match
):
    try:
        username = data.get('username') if data else None
        if not username:
            username = get_username_by_sid(request.sid)
        if not username:
            return {'success': False, 'message': 'Missing username'}

        current_pending_match = next(
            (match for match in pending_match.values() if match and username in match.get('players', [])),
            None
        )
        logger.info(
            "Accept match request received: sid=%s username=%s pending_players=%s",
            request.sid,
            username,
            list(current_pending_match.get('players', [])) if current_pending_match else None
        )
        with queue_lock:
            if not current_pending_match or username not in current_pending_match.get('players', []):
                logger.warning(
                    "Rejecting accept match: sid=%s username=%s pending=%s",
                    request.sid,
                    username,
                    bool(current_pending_match)
                )
                return {'success': False, 'message': 'No pending match to accept'}

            current_pending_match['accepted'][username] = True
            match_id = current_pending_match['id']
            all_accepted = all(
                current_pending_match['accepted'].get(player)
                for player in current_pending_match['players']
            )
            match_accept = get_match_accept_payload(username)

        broadcast_queue_update()

        if all_accepted:
            finalize_pending_match(match_id)

        return {
            'success': True,
            'matchAccept': match_accept,
            'allAccepted': all_accepted
        }
    except Exception as e:
        logger.error(f"Error in handle_accept_match: {str(e)}")
        return {'success': False, 'message': 'Failed to accept match'}
