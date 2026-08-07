import random
import time

from services.queue import find_user_queue_mode, get_queue_for_mode


GROUP_SEED_NAME_PREFIXES = [
    'Alpha', 'Archer', 'Atlas', 'Bandit', 'Blitz', 'Bravo', 'Cinder', 'Comet',
    'Cross', 'Delta', 'Echo', 'Falcon', 'Frost', 'Ghost', 'Havoc', 'Hunter',
    'Jester', 'Knight', 'Maverick', 'Nomad', 'Oracle', 'Phoenix', 'Ranger',
    'Scout', 'Shadow', 'Slate', 'Striker', 'Talon', 'Vector', 'Viper'
]
GROUP_SEED_NAME_SUFFIXES = [
    'Ace', 'Bolt', 'Brick', 'Cobra', 'Drift', 'Hawk', 'Juno', 'Kane', 'Nova',
    'Pike', 'Quinn', 'Reed', 'Riot', 'Rush', 'Sage', 'Stone', 'Storm', 'Ward'
]


def _generate_group_seed_username(users, members, created):
    existing = set(users or {})
    existing.update(members or [])
    existing.update(created or [])
    for _ in range(300):
        username = (
            f"GroupBot_{random.choice(GROUP_SEED_NAME_PREFIXES)}"
            f"{random.choice(GROUP_SEED_NAME_SUFFIXES)}{random.randint(10, 99)}"
        )
        if username not in existing:
            return username

    suffix = len(existing) + 1
    while True:
        username = f'group_seed_{suffix:03d}'
        if username not in existing:
            return username
        suffix += 1


def _find_queued_member(matchmaking_queue, members):
    for member in members:
        if find_user_queue_mode(matchmaking_queue, member):
            return member
    return None


def _find_lobby_member(is_user_in_any_lobby, members):
    for member in members:
        if is_user_in_any_lobby(member):
            return member
    return None


def _remove_user_from_lobbies(
    username,
    *,
    lobbies,
    player_activity=None,
    get_player_sids=None,
    socketio=None,
    broadcast_open_lobbies_update=None,
    emit_active_lobby_sync=None,
    select_captains=None,
    record_lobby_event=None,
    release_server_allocation=None
):
    removed_lobby_ids = []
    for lobby_id, lobby in list((lobbies or {}).items()):
        if username not in lobby.get('players', []):
            lobby.get('player_groups', {}).pop(username, None)
            lobby.get('map_votes', {}).pop(username, None)
            continue

        remaining_players = [
            player for player in lobby.get('players', [])
            if player != username
        ]
        if record_lobby_event:
            record_lobby_event(lobby_id, 'player_left_lobby', {
                'username': username,
                'remaining_players': remaining_players,
                'reason': 'left_group'
            }, created_at=time.time())

        lobby['players'].remove(username)
        for team in ['team1', 'team2']:
            if username in lobby.get('teams', {}).get(team, []):
                lobby['teams'][team].remove(username)

        lobby.get('player_groups', {}).pop(username, None)
        lobby.get('map_votes', {}).pop(username, None)

        if lobby.get('captains') is not None and select_captains:
            lobby['captains'] = select_captains(lobby.get('teams', {}))

        if username in lobby.get('disconnected_players', set()):
            lobby['disconnected_players'].remove(username)

        if player_activity is not None and username in player_activity:
            player_activity[username].pop('lobby_id', None)
            player_activity[username]['status'] = 'authenticated'
            player_activity[username]['last_seen'] = time.time()

        if socketio and get_player_sids:
            for sid in get_player_sids(username):
                socketio.server.leave_room(sid, lobby_id)

        if socketio:
            socketio.emit('player_left', {
                'username': username,
                'lobby_id': lobby_id
            }, room=lobby_id)
            socketio.emit('lobby_update', {
                'lobby_id': lobby_id,
                'players': lobby.get('players', []),
                'teams': lobby.get('teams', {}),
                'captains': lobby.get('captains'),
                'step': lobby.get('step', 1),
                'queue_mode': lobby.get('queue_mode'),
                'queue_label': lobby.get('queue_label'),
                'match_size_label': lobby.get('match_size_label'),
                'max_players': lobby.get('max_players'),
                'map_pool': lobby.get('map_pool', []),
                'map_votes': lobby.get('map_votes', {}),
                'vote_counts': {
                    vote: sum(1 for selected in lobby.get('map_votes', {}).values() if selected == vote)
                    for vote in set(lobby.get('map_votes', {}).values())
                },
                'player_groups': lobby.get('player_groups', {})
            }, room=lobby_id)

        removed_lobby_ids.append(lobby_id)

        if not lobby.get('players'):
            if record_lobby_event:
                record_lobby_event(lobby_id, 'lobby_closed', {
                    'reason': 'empty'
                }, created_at=time.time())
            if release_server_allocation:
                release_server_allocation(lobby_id, reason='lobby_closed')
            lobbies.pop(lobby_id, None)

    if removed_lobby_ids and broadcast_open_lobbies_update:
        broadcast_open_lobbies_update()
    if removed_lobby_ids and emit_active_lobby_sync:
        emit_active_lobby_sync(username, None)
    return removed_lobby_ids


def handle_group_create_event(
    data,
    *,
    request,
    logger,
    group_lock,
    get_user_group,
    queue_lock,
    matchmaking_queue,
    is_user_in_any_lobby,
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
            with queue_lock:
                if find_user_queue_mode(matchmaking_queue, username):
                    return {'success': False, 'message': 'Leave the queue before creating a group'}
            if is_user_in_any_lobby(username):
                return {'success': False, 'message': 'Leave the lobby before creating a group'}
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
    queue_lock,
    matchmaking_queue,
    is_user_in_any_lobby,
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
            with queue_lock:
                if find_user_queue_mode(matchmaking_queue, username):
                    return {'success': False, 'message': 'Leave the queue before joining a group'}
                if _find_queued_member(matchmaking_queue, group['members']):
                    return {
                        'success': False,
                        'message': 'This group is already queued. Ask the leader to leave the queue before new members join.'
                    }
            if is_user_in_any_lobby(username):
                return {'success': False, 'message': 'Leave the lobby before joining a group'}
            if _find_lobby_member(is_user_in_any_lobby, group['members']):
                return {
                    'success': False,
                    'message': 'This group has a member in a lobby. Group changes are locked until everyone leaves the lobby.'
                }
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
    queue_lock,
    matchmaking_queue,
    is_user_in_any_lobby,
    groups,
    user_to_group,
    leave_room,
    get_group_payload,
    broadcast_group_update,
    save_queue=None,
    broadcast_queue_update=None,
    pending_match=None,
    cancel_pending_match=None,
    lobbies=None,
    player_activity=None,
    get_player_sids=None,
    socketio=None,
    broadcast_open_lobbies_update=None,
    emit_active_lobby_sync=None,
    select_captains=None,
    record_lobby_event=None,
    release_server_allocation=None
):
    try:
        username = data.get('username') if data else None
        if not username:
            return {'success': False, 'message': 'Missing username'}

        cancel_queue_modes = []
        removed_from_queue = False
        removed_lobby_ids = []
        payload = None

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': True, 'group': None}
            group = groups.get(code)
            if not group:
                user_to_group.pop(username, None)
                return {'success': True, 'group': None}
            with queue_lock:
                for mode_id, queue in matchmaking_queue.items():
                    active_pending = (pending_match or {}).get(mode_id) if isinstance(pending_match, dict) else None
                    is_pending_player = bool(
                        active_pending
                        and username in active_pending.get('players', [])
                    )
                    if username in queue and is_pending_player:
                        cancel_queue_modes.append(mode_id)
                    elif username in queue:
                        queue.remove(username)
                        removed_from_queue = True
                    elif is_pending_player:
                        cancel_queue_modes.append(mode_id)
                if removed_from_queue and save_queue:
                    save_queue()

            removed_lobby_ids = _remove_user_from_lobbies(
                username,
                lobbies=lobbies,
                player_activity=player_activity,
                get_player_sids=get_player_sids,
                socketio=socketio,
                broadcast_open_lobbies_update=broadcast_open_lobbies_update,
                emit_active_lobby_sync=emit_active_lobby_sync,
                select_captains=select_captains,
                record_lobby_event=record_lobby_event,
                release_server_allocation=release_server_allocation
            )

            if username in group['members']:
                group['members'].remove(username)
            user_to_group.pop(username, None)

            if not group['members']:
                groups.pop(code, None)
            else:
                if group['leader'] == username:
                    group['leader'] = group['members'][0]

                payload = get_group_payload(code)

        broadcast_group_update(code, payload)
        leave_room(code)
        if removed_from_queue and broadcast_queue_update:
            broadcast_queue_update()
        for mode_id in cancel_queue_modes:
            if cancel_pending_match:
                cancel_pending_match(
                    'A player left their group during match acceptance.',
                    remove_players=[username],
                    queue_mode=mode_id
                )
        return {
            'success': True,
            'group': None,
            'leftLobby': bool(removed_lobby_ids),
            'removedFromQueue': bool(removed_from_queue or cancel_queue_modes)
        }
    except Exception as e:
        logger.error(f"Error leaving group: {str(e)}")
        return {'success': False, 'message': 'Failed to leave group'}


def handle_group_transfer_event(
    data,
    *,
    logger,
    group_lock,
    get_user_group,
    queue_lock,
    matchmaking_queue,
    is_user_in_any_lobby,
    groups,
    get_group_payload,
    broadcast_group_update
):
    try:
        username = data.get('username') if data else None
        target_username = data.get('targetUsername') if data else None
        if not username or not target_username:
            return {'success': False, 'message': 'Missing username or target username'}

        if username == target_username:
            return {'success': False, 'message': 'You are already the group leader'}

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': False, 'message': 'Not in a group'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}
            if group['leader'] != username:
                return {'success': False, 'message': 'Only the leader can transfer group ownership'}
            if target_username not in group['members']:
                return {'success': False, 'message': 'Target user is not in this group'}
            with queue_lock:
                if _find_queued_member(matchmaking_queue, group['members']):
                    return {'success': False, 'message': 'Leave the queue before transferring group ownership'}
            if _find_lobby_member(is_user_in_any_lobby, group['members']):
                return {'success': False, 'message': 'Leave the lobby before transferring group ownership'}

            group['leader'] = target_username
            payload = get_group_payload(code)

        broadcast_group_update(code, payload)
        return {'success': True, 'group': payload}
    except Exception as e:
        logger.error(f"Error transferring group ownership: {str(e)}")
        return {'success': False, 'message': 'Failed to transfer group ownership'}


def handle_group_kick_event(
    data,
    *,
    logger,
    group_lock,
    get_user_group,
    queue_lock,
    matchmaking_queue,
    is_user_in_any_lobby,
    groups,
    user_to_group,
    get_group_payload,
    broadcast_group_update,
    socketio,
    socket_events,
    get_player_sids,
    leave_room
):
    try:
        username = data.get('username') if data else None
        target_username = data.get('targetUsername') if data else None
        if not username or not target_username:
            return {'success': False, 'message': 'Missing username or target username'}

        if username == target_username:
            return {'success': False, 'message': 'Use leave group instead'}

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': False, 'message': 'Not in a group'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}
            if group['leader'] != username:
                return {'success': False, 'message': 'Only the leader can kick group members'}
            if target_username not in group['members']:
                return {'success': False, 'message': 'Target user is not in this group'}
            with queue_lock:
                if _find_queued_member(matchmaking_queue, group['members']):
                    return {'success': False, 'message': 'Leave the queue before changing group members'}
            if _find_lobby_member(is_user_in_any_lobby, group['members']):
                return {'success': False, 'message': 'Leave the lobby before changing group members'}

            group['members'].remove(target_username)
            user_to_group.pop(target_username, None)
            payload = get_group_payload(code)
            target_sids = list(get_player_sids(target_username))

        broadcast_group_update(code, payload)
        for sid in target_sids:
            socketio.emit(socket_events['GROUP']['UPDATE'], {'success': True, 'group': None}, room=sid)
            leave_room(code, sid=sid)
        return {'success': True, 'group': payload}
    except Exception as e:
        logger.error(f"Error kicking group member: {str(e)}")
        return {'success': False, 'message': 'Failed to kick group member'}


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


def handle_group_seed_event(
    data,
    *,
    request,
    logger,
    group_lock,
    get_user_group,
    queue_lock,
    matchmaking_queue,
    is_user_in_any_lobby,
    groups,
    user_to_group,
    users,
    save_users,
    hash_password,
    upsert_player_activity,
    get_group_payload,
    broadcast_group_update,
    get_username_by_sid,
    is_admin_user,
    max_group_members
):
    try:
        username = get_username_by_sid(request.sid)
        if not is_admin_user(username):
            return {'success': False, 'message': 'Admin only'}

        requested_count = int((data or {}).get('count') or 0)
        if requested_count < 1:
            return {'success': False, 'message': 'Enter at least 1 bot'}

        seeded = []
        payload = None

        with group_lock:
            code = get_user_group(username)
            if not code:
                return {'success': False, 'message': 'Create or join a group first'}
            group = groups.get(code)
            if not group:
                return {'success': False, 'message': 'Group not found'}

            with queue_lock:
                if _find_queued_member(matchmaking_queue, group['members']):
                    return {'success': False, 'message': 'Leave the queue before changing group members'}
            if _find_lobby_member(is_user_in_any_lobby, group['members']):
                return {'success': False, 'message': 'Leave the lobby before changing group members'}

            available_slots = max(0, int(max_group_members or 0) - len(group['members']))
            if available_slots < 1:
                return {'success': False, 'message': 'Group is full'}

            seed_count = min(requested_count, available_slots)
            seed_password_hash = hash_password('seed-player-dev-password')
            for _index in range(seed_count):
                seed_username = _generate_group_seed_username(users, group['members'], seeded)
                steam_suffix = len(users) + len(seeded) + 1
                users[seed_username] = {
                    'password': seed_password_hash,
                    'steam_id': str(76561199050000000 + steam_suffix)
                }
                group['members'].append(seed_username)
                user_to_group[seed_username] = code
                upsert_player_activity(seed_username, status='authenticated')
                seeded.append(seed_username)

            if seeded:
                save_users()
            payload = get_group_payload(code)

        broadcast_group_update(code, payload)
        return {'success': True, 'group': payload, 'seeded': seeded}
    except (TypeError, ValueError):
        return {'success': False, 'message': 'Enter a valid bot count'}
    except Exception as e:
        logger.error(f"Error seeding group: {str(e)}")
        return {'success': False, 'message': 'Failed to seed group'}


def handle_group_queue_event(
    data,
    *,
    logger,
    group_lock,
    get_user_group,
    groups,
    queue_modes,
    user_has_steam_id,
    is_user_in_any_lobby,
    queue_lock,
    matchmaking_queue,
    pending_match,
    lobbies,
    upsert_player_activity,
    save_queue,
    broadcast_queue_update,
    check_queue_and_start_countdown,
    build_queue_payload,
    has_available_server_capacity,
    disabled_queue_modes=None
):
    try:
        username = data.get('username') if data else None
        queue_mode = str((data or {}).get('queueMode') or 'skirmish').strip().lower()
        queue_config = queue_modes.get(queue_mode)
        if not username:
            return {'success': False, 'message': 'Missing username'}
        if not queue_config:
            return {'success': False, 'message': 'Unknown queue mode'}
        disabled_queue_modes = set(disabled_queue_modes or [])
        if queue_mode in disabled_queue_modes:
            return {
                'success': False,
                'message': 'This queue is temporarily disabled.',
                **build_queue_payload(username=username, queue_mode=queue_mode)
            }

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
            if len(members) > queue_config['team_size']:
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
            if not has_available_server_capacity(lobbies, pending_match, server_capacity=1):
                return {
                    'success': False,
                    'message': 'A match is already using the only available server.',
                    **build_queue_payload(username=username, queue_mode=queue_mode)
                }
            if any(find_user_queue_mode(matchmaking_queue, member) for member in members):
                return {'success': False, 'message': 'A group member is already in the queue'}
            queue = get_queue_for_mode(matchmaking_queue, queue_mode)
            if len(queue) + len(members) > queue_config['max_players']:
                return {'success': False, 'message': 'Queue does not have enough slots'}

            for member in members:
                queue.append(member)
                upsert_player_activity(member, status='queued')

            save_queue()

        broadcast_queue_update()
        check_queue_and_start_countdown()

        return build_queue_payload(username=username, queue_mode=queue_mode)
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
    broadcast_queue_update,
    build_queue_payload
):
    try:
        username = data.get('username') if data else None
        queue_mode = str((data or {}).get('queueMode') or '').strip().lower() or None
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
            effective_mode = queue_mode
            for member in members:
                member_mode = find_user_queue_mode(matchmaking_queue, member)
                if not effective_mode and member_mode:
                    effective_mode = member_mode
                queue = get_queue_for_mode(matchmaking_queue, member_mode) if member_mode else []
                if member in queue:
                    queue.remove(member)
                    removed = True
                if member in player_activity:
                    player_activity[member]['status'] = 'authenticated'
            if removed:
                save_queue()

        if removed:
            broadcast_queue_update()

        return {
            'success': True,
            **build_queue_payload(username=username, queue_mode=effective_mode)
        }
    except Exception as e:
        logger.error(f"Error unqueueing group: {str(e)}")
        return {'success': False, 'message': 'Failed to leave queue'}
