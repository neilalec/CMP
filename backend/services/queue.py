import eventlet


def get_queue_for_mode(matchmaking_queue, queue_mode):
    return matchmaking_queue.setdefault(queue_mode, [])


def get_pending_for_mode(pending_match, queue_mode):
    if isinstance(pending_match, dict):
        return pending_match.get(queue_mode)
    return None


def find_user_queue_mode(matchmaking_queue, username):
    if not username:
        return None
    for queue_mode, queue in matchmaking_queue.items():
        if username in queue:
            return queue_mode
    return None


def iter_all_queued_users(matchmaking_queue):
    for queue in matchmaking_queue.values():
        for username in queue:
            yield username


def has_available_server_capacity(lobbies, pending_match, server_capacity=1):
    capacity = 1 if server_capacity is None else max(0, int(server_capacity or 0))
    active_lobbies = sum(
        1 for lobby in (lobbies or {}).values()
        if not (lobby.get('step') == 5 and lobby.get('server_released_at'))
    )
    active_pending_matches = sum(
        1 for match in (pending_match or {}).values()
        if match
    )
    return (active_lobbies + active_pending_matches) < capacity


def get_server_availability(
    lobbies,
    pending_match,
    server_capacity=1
):
    capacity = 1 if server_capacity is None else max(0, int(server_capacity or 0))
    active_lobbies = sum(
        1 for lobby in (lobbies or {}).values()
        if not (lobby.get('step') == 5 and lobby.get('server_released_at'))
    )
    active_pending_matches = sum(
        1 for match in (pending_match or {}).values()
        if match
    )
    available = (active_lobbies + active_pending_matches) < capacity
    if capacity <= 0:
        reason = 'no_servers'
    elif active_lobbies > 0:
        reason = 'server_in_use'
    elif active_pending_matches > 0:
        reason = 'match_acceptance_active'
    else:
        reason = 'available'

    return {
        'available': available,
        'reason': reason,
        'capacity': capacity,
        'activeLobbyCount': active_lobbies,
        'activePendingMatchCount': active_pending_matches
    }


def build_queue_payload(
    matchmaking_queue,
    user_has_steam_id,
    get_match_accept_payload,
    queue_modes,
    lobbies=None,
    pending_match=None,
    server_capacity=1,
    username=None,
    countdown=None,
    queue_mode=None
):
    current_queue_mode = find_user_queue_mode(matchmaking_queue, username)
    queues_payload = {}
    total_players_in_queue = 0

    for mode_id, config in queue_modes.items():
        queue = list(matchmaking_queue.get(mode_id, []))
        total_players_in_queue += len(queue)
        queues_payload[mode_id] = {
            'id': mode_id,
            'label': config['label'],
            'shortLabel': config['short_label'],
            'teamSize': config['team_size'],
            'maxPlayers': config['max_players'],
            'playersInQueue': len(queue),
            'queue': queue,
            'inQueue': bool(username and username in queue),
        }

    resolved_queue_mode = queue_mode or current_queue_mode
    active_queue = list(matchmaking_queue.get(resolved_queue_mode, [])) if resolved_queue_mode else []
    active_config = queue_modes.get(resolved_queue_mode) if resolved_queue_mode else None
    server_availability = get_server_availability(
        lobbies,
        pending_match,
        server_capacity=server_capacity
    )

    payload = {
        'success': True,
        'inQueue': current_queue_mode is not None,
        'queueMode': current_queue_mode,
        'playersInQueue': len(active_queue),
        'queue': active_queue,
        'maxPlayers': active_config['max_players'] if active_config else None,
        'queueModes': queues_payload,
        'totalPlayersInQueue': total_players_in_queue,
        'hasSteamId': user_has_steam_id(username) if username else False,
        'serverCapacity': server_availability['capacity'],
        'serverAvailable': server_availability['available'],
        'serverAvailabilityReason': server_availability['reason'],
        'activeLobbyCount': server_availability['activeLobbyCount'],
        'activePendingMatchCount': server_availability['activePendingMatchCount'],
    }
    if countdown is not None and countdown > 0:
        payload['countdown'] = countdown
    match_accept = get_match_accept_payload(username)
    if match_accept:
        payload['matchAccept'] = match_accept
    return payload


def cancel_pending_match(
    *,
    queue_lock,
    pending_match,
    matchmaking_queue,
    player_activity,
    save_queue,
    broadcast_queue_update,
    socketio,
    socket_events,
    get_user_room,
    reason='Match acceptance cancelled.',
    remove_players=None
):
    with queue_lock:
        if not pending_match:
            return False, None

        queue_mode = pending_match.get('queue_mode')
        queue = get_queue_for_mode(matchmaking_queue, queue_mode)
        participants = list(pending_match.get('players', []))
        removed_players = []
        for username in remove_players or []:
            if username in queue:
                queue.remove(username)
                removed_players.append(username)
                if username in player_activity:
                    player_activity[username]['status'] = 'authenticated'

        save_queue()

    broadcast_queue_update()

    for username in participants:
        socketio.emit(socket_events['QUEUE']['MATCH_ACCEPT_CANCELLED'], {
            'reason': reason,
            'removedPlayers': removed_players,
            'queueMode': queue_mode
        }, room=get_user_room(username))
    return True, removed_players


def finalize_pending_match(pending_match, match_id, broadcast_queue_update, create_lobby):
    if not pending_match or pending_match.get('id') != match_id:
        return False
    players = list(pending_match.get('players', []))
    if not all(pending_match.get('accepted', {}).get(player) for player in players):
        return False

    broadcast_queue_update()
    return create_lobby(players, queue_mode=pending_match.get('queue_mode'))


def start_match_acceptance(
    *,
    players,
    queue_mode,
    max_lobby_players,
    match_accept_countdown,
    pending_match,
    set_pending_match,
    broadcast_queue_update,
    pause_aware_sleep,
    finalize_pending_match,
    cancel_pending_match
):
    if pending_match:
        return False, None

    tracked_players = list(players[:max_lobby_players])
    state = {
        'id': f"match_{int(__import__('time').time() * 1000)}",
        'queue_mode': queue_mode,
        'players': tracked_players,
        'accepted': {player: False for player in tracked_players},
        'countdown': match_accept_countdown
    }
    match_id = state['id']

    set_pending_match(state)
    import logging
    logging.getLogger(__name__).info(
        "Starting match acceptance: mode=%s id=%s players=%s countdown=%s",
        queue_mode,
        match_id,
        tracked_players,
        match_accept_countdown
    )
    broadcast_queue_update()

    def countdown():
        remaining = match_accept_countdown
        while remaining > 0:
            if not state or state.get('id') != match_id:
                return
            if all(state['accepted'].get(player) for player in state['players']):
                logging.getLogger(__name__).info(
                    "Match acceptance completed early: mode=%s id=%s players=%s",
                    queue_mode,
                    match_id,
                    state['players']
                )
                return
            state['countdown'] = remaining

            broadcast_queue_update()
            pause_aware_sleep(1)
            remaining -= 1

        if not state or state.get('id') != match_id:
            return

        all_accepted = all(
            state['accepted'].get(player)
            for player in state['players']
        )
        state['countdown'] = max(remaining, 0)
        not_accepted = [
            player for player in state['players']
            if not state['accepted'].get(player)
        ]

        if not all_accepted:
            logging.getLogger(__name__).warning(
                "Match acceptance timed out: mode=%s id=%s missing=%s",
                queue_mode,
                match_id,
                not_accepted
            )
            cancel_pending_match(
                'Match acceptance timed out.',
                remove_players=not_accepted
            )

    eventlet.spawn(countdown)
    return True, state


def update_queue_state(
    *,
    queue_lock,
    save_queue,
    socketio,
    socket_events,
    matchmaking_queue,
    save=True,
    broadcast=True
):
    with queue_lock:
        if save:
            save_queue()

        if broadcast:
            current_state = {
                'queueModes': {
                    mode_id: {
                        'playersInQueue': len(queue),
                        'queue': list(queue)
                    }
                    for mode_id, queue in matchmaking_queue.items()
                }
            }
            socketio.emit(socket_events['QUEUE']['UPDATE'], current_state, broadcast=True)


def check_queue_and_start_countdown(
    *,
    queue_lock,
    pending_match,
    matchmaking_queue,
    queue_modes,
    lobbies,
    server_capacity,
    start_match_acceptance
):
    queued_modes = []

    with queue_lock:
        if not has_available_server_capacity(lobbies, pending_match, server_capacity=server_capacity):
            return
        for mode_id, config in queue_modes.items():
            queue = get_queue_for_mode(matchmaking_queue, mode_id)
            if get_pending_for_mode(pending_match, mode_id):
                continue
            if len(queue) >= config['max_players']:
                queued_modes.append((mode_id, list(queue[:config['max_players']])))

    for mode_id, players in queued_modes:
        start_match_acceptance(players, queue_mode=mode_id)


def add_to_queue(username, matchmaking_queue, queue_mode, upsert_player_activity, save_queue):
    queue = get_queue_for_mode(matchmaking_queue, queue_mode)
    if username not in queue:
        queue.append(username)
        upsert_player_activity(username, status='queued')
        save_queue()
        return True
    return False
