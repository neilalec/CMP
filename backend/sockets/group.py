import time


def handle_group_create_event(
    data,
    *,
    request,
    logger,
    group_lock,
    get_user_group,
    generate_group_code,
    groups,
    user_to_group,
    upsert_player_activity,
    join_room,
    get_group_payload,
    broadcast_group_update
):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            if get_user_group(username):
                return {'success': False, 'message': 'Already in a group'}
            code = generate_group_code()
            groups[code] = {
                'code': code,
                'leader': username,
                'members': [username]
            }
            user_to_group[username] = code
            upsert_player_activity(username, sid=request.sid, last_seen=time.time())

        join_room(code)
        payload = get_group_payload(code)
        broadcast_group_update(code, payload)
        return {'success': True, 'group': payload}
    except Exception as e:
        logger.error(f"Error creating group: {str(e)}")
        return {'success': False, 'message': 'Failed to create group'}


def handle_group_join_event(
    data,
    *,
    request,
    logger,
    group_lock,
    get_user_group,
    groups,
    max_lobby_players,
    user_to_group,
    upsert_player_activity,
    join_room,
    get_group_payload,
    broadcast_group_update
):
    try:
        username = data.get('username') if data else None
        code = data.get('code') if data else None
        if not username or not code:
            return {'success': False, 'message': 'Missing username or code'}

        code = str(code).strip().upper()

        with group_lock:
            if get_user_group(username):
                return {'success': False, 'message': 'Already in a group'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}
            if len(group['members']) >= max_lobby_players:
                return {'success': False, 'message': 'Group is full'}
            if username not in group['members']:
                group['members'].append(username)
            user_to_group[username] = code
            upsert_player_activity(username, sid=request.sid, last_seen=time.time())

        join_room(code)
        payload = get_group_payload(code)
        broadcast_group_update(code, payload)
        return {'success': True, 'group': payload}
    except Exception as e:
        logger.error(f"Error joining group: {str(e)}")
        return {'success': False, 'message': 'Failed to join group'}


def handle_group_leave_event(
    data,
    *,
    logger,
    group_lock,
    get_user_group,
    groups,
    user_to_group,
    leave_room,
    get_group_payload,
    broadcast_group_update
):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': True, 'group': None}
            group = groups.get(code)
            if not group:
                user_to_group.pop(username, None)
                return {'success': True, 'group': None}

            if username in group['members']:
                group['members'].remove(username)
            user_to_group.pop(username, None)

            if not group['members']:
                broadcast_group_update(code, None)
                groups.pop(code, None)
                leave_room(code)
                return {'success': True, 'group': None}

            if group['leader'] == username:
                group['leader'] = group['members'][0]

            payload = get_group_payload(code)

        broadcast_group_update(code, payload)
        leave_room(code)
        return {'success': True, 'group': None}
    except Exception as e:
        logger.error(f"Error leaving group: {str(e)}")
        return {'success': False, 'message': 'Failed to leave group'}


def handle_group_status_event(data, *, logger, group_lock, get_user_group, get_group_payload):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            code = get_user_group(username)
            payload = get_group_payload(code) if code else None

        return {'success': True, 'group': payload}
    except Exception as e:
        logger.error(f"Error getting group status: {str(e)}")
        return {'success': False, 'message': 'Failed to get group status'}


def handle_group_queue_event(
    data,
    *,
    logger,
    group_lock,
    get_user_group,
    groups,
    max_lobby_players,
    user_has_steam_id,
    is_user_in_any_lobby,
    queue_lock,
    matchmaking_queue,
    upsert_player_activity,
    save_queue,
    broadcast_queue_update,
    check_queue_and_start_countdown,
    build_queue_payload
):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': False, 'message': 'Not in a group'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}
            if group['leader'] != username:
                return {'success': False, 'message': 'Only the leader can queue the group'}
            members = list(group['members'])
            if len(members) > (max_lobby_players // 2):
                return {'success': False, 'message': 'Group is too large to stay on one team'}

        missing_steam_ids = [member for member in members if not user_has_steam_id(member)]
        if missing_steam_ids:
            return {
                'success': False,
                'message': f"These group members need a Steam ID before queueing: {', '.join(missing_steam_ids)}"
            }

        if any(is_user_in_any_lobby(member) for member in members):
            return {'success': False, 'message': 'A group member is already in a lobby'}

        with queue_lock:
            if any(member in matchmaking_queue for member in members):
                return {'success': False, 'message': 'A group member is already in the queue'}
            if len(matchmaking_queue) + len(members) > max_lobby_players:
                return {'success': False, 'message': 'Queue does not have enough slots'}

            for member in members:
                matchmaking_queue.append(member)
                upsert_player_activity(member, status='queued')

            save_queue()

        broadcast_queue_update()
        check_queue_and_start_countdown()

        return build_queue_payload(username=username)
    except Exception as e:
        logger.error(f"Error queueing group: {str(e)}")
        return {'success': False, 'message': 'Failed to queue group'}


def handle_group_unqueue_event(
    data,
    *,
    logger,
    group_lock,
    get_user_group,
    groups,
    queue_lock,
    matchmaking_queue,
    player_activity,
    save_queue,
    broadcast_queue_update
):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': False, 'message': 'Not in a group'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}
            if group['leader'] != username:
                return {'success': False, 'message': 'Only the leader can leave the queue'}
            members = list(group['members'])

        with queue_lock:
            removed = False
            for member in members:
                if member in matchmaking_queue:
                    matchmaking_queue.remove(member)
                    removed = True
                if member in player_activity:
                    player_activity[member]['status'] = 'authenticated'
            if removed:
                save_queue()

        if removed:
            broadcast_queue_update()

        return {
            'success': True,
            'playersInQueue': len(matchmaking_queue),
            'queue': list(matchmaking_queue)
        }
    except Exception as e:
        logger.error(f"Error unqueueing group: {str(e)}")
        return {'success': False, 'message': 'Failed to leave queue'}
