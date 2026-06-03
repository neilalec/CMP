def handle_join_queue_event(
    data,
    *,
    socket_events,
    emit,
    socketio,
    request,
    logger,
    group_lock,
    get_user_group,
    user_has_steam_id,
    build_queue_payload,
    queue_lock,
    matchmaking_queue,
    max_lobby_players,
    upsert_player_activity,
    save_queue,
    check_queue_and_start_countdown
):
    try:
        username = data.get('username')

        if not username:
            emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                'success': False,
                'message': 'Missing username'
            })
            return

        with group_lock:
            if get_user_group(username):
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'You are in a group. Use group queue.',
                    'inQueue': username in matchmaking_queue,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
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
            if len(matchmaking_queue) >= max_lobby_players:
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'Queue is full',
                    'inQueue': False,
                    'playersInQueue': len(matchmaking_queue),
                    'queue': list(matchmaking_queue)
                })
                return
            if username not in matchmaking_queue:
                matchmaking_queue.append(username)
                upsert_player_activity(username, sid=request.sid, status='queued')
                save_queue()

                socketio.emit(socket_events['QUEUE']['UPDATE'], {
                    **build_queue_payload(),
                    'inQueue': username in matchmaking_queue
                })

                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    **build_queue_payload(username=username),
                    'inQueue': True
                })

                check_queue_and_start_countdown()
            else:
                emit(f"{socket_events['QUEUE']['JOIN']}_response", {
                    'success': False,
                    'message': 'Already in queue'
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
        cancel_match = False

        if not queue_lock.acquire(timeout=2.0):
            logger.error("Could not acquire queue lock - timeout")
            emit(f"{socket_events['QUEUE']['LEAVE']}_response", {
                'success': False,
                'message': 'Server busy, please try again',
                'inQueue': True,
                'playersInQueue': len(matchmaking_queue),
                'queue': list(matchmaking_queue)
            })
            return

        try:
            if username in matchmaking_queue:
                matchmaking_queue.remove(username)
                save_queue()
                logger.info(f"Removed {username} from queue")
                cancel_match = bool(
                    pending_match and username in pending_match.get('players', [])
                )

                response = {
                    **build_queue_payload(username=username),
                    'inQueue': False,
                }
                logger.info(f"Sending leave queue response: {response}")
                emit(f"{socket_events['QUEUE']['LEAVE']}_response", response)

                socketio.emit(socket_events['QUEUE']['UPDATE'], build_queue_payload())
            else:
                logger.info(f"{username} not found in queue")
                emit(f"{socket_events['QUEUE']['LEAVE']}_response", {
                    **build_queue_payload(username=username),
                    'inQueue': False,
                })
        finally:
            queue_lock.release()

        if cancel_match:
            cancel_pending_match(
                'A player left the queue during match acceptance.',
                remove_players=[username]
            )
    except Exception as e:
        logger.error(f"Error in handle_leave_queue: {str(e)}", exc_info=True)
        emit(f"{socket_events['QUEUE']['LEAVE']}_response", {
            'success': False,
            'message': str(e),
            'inQueue': username in matchmaking_queue if username else False,
            'playersInQueue': len(matchmaking_queue),
            'queue': list(matchmaking_queue)
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

        logger.info(
            "Accept match request received: sid=%s username=%s pending_players=%s",
            request.sid,
            username,
            list(pending_match.get('players', [])) if pending_match else None
        )
        with queue_lock:
            if not pending_match or username not in pending_match.get('players', []):
                logger.warning(
                    "Rejecting accept match: sid=%s username=%s pending=%s",
                    request.sid,
                    username,
                    bool(pending_match)
                )
                return {'success': False, 'message': 'No pending match to accept'}

            pending_match['accepted'][username] = True
            match_id = pending_match['id']
            all_accepted = all(
                pending_match['accepted'].get(player)
                for player in pending_match['players']
            )
            match_accept = get_match_accept_payload(username)
            logger.info(
                "Match accept updated: id=%s username=%s accepted=%s all_accepted=%s state=%s",
                match_id,
                username,
                pending_match['accepted'].get(username),
                all_accepted,
                match_accept
            )

        broadcast_queue_update()
        logger.info("Broadcasted queue update after accept: username=%s match_id=%s", username, match_id)

        if all_accepted:
            logger.info("Finalizing pending match: match_id=%s", match_id)
            finalize_pending_match(match_id)

        return {
            'success': True,
            'matchAccept': match_accept,
            'allAccepted': all_accepted
        }
    except Exception as e:
        logger.error(f"Error in handle_accept_match: {str(e)}")
        return {'success': False, 'message': 'Failed to accept match'}
