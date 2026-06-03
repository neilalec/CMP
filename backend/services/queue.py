import eventlet


def build_queue_payload(matchmaking_queue, user_has_steam_id, get_match_accept_payload, username=None, countdown=None):
    payload = {
        'success': True,
        'inQueue': username in matchmaking_queue if username else False,
        'playersInQueue': len(matchmaking_queue),
        'queue': list(matchmaking_queue),
        'hasSteamId': user_has_steam_id(username) if username else False
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

        participants = list(pending_match.get('players', []))
        removed_players = []
        for username in remove_players or []:
            if username in matchmaking_queue:
                matchmaking_queue.remove(username)
                removed_players.append(username)
                if username in player_activity:
                    player_activity[username]['status'] = 'authenticated'

        save_queue()

    broadcast_queue_update()

    for username in participants:
        socketio.emit(socket_events['QUEUE']['MATCH_ACCEPT_CANCELLED'], {
            'reason': reason,
            'removedPlayers': removed_players
        }, room=get_user_room(username))
    return True, removed_players


def finalize_pending_match(pending_match, match_id, broadcast_queue_update, create_lobby):
    if not pending_match or pending_match.get('id') != match_id:
        return False
    players = list(pending_match.get('players', []))
    if not all(pending_match.get('accepted', {}).get(player) for player in players):
        return False

    broadcast_queue_update()
    return create_lobby(players)


def start_match_acceptance(
    *,
    players,
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
        'players': tracked_players,
        'accepted': {player: False for player in tracked_players},
        'countdown': match_accept_countdown
    }
    match_id = state['id']

    set_pending_match(state)
    import logging
    logging.getLogger(__name__).info(
        "Starting match acceptance: id=%s players=%s countdown=%s",
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
                    "Match acceptance completed early: id=%s players=%s",
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
                "Match acceptance timed out: id=%s missing=%s",
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
                'playersInQueue': len(matchmaking_queue),
                'queue': list(matchmaking_queue)
            }
            socketio.emit(socket_events['QUEUE']['UPDATE'], current_state, broadcast=True)


def check_queue_and_start_countdown(*, queue_lock, pending_match, matchmaking_queue, max_lobby_players, start_match_acceptance):
    players = None

    with queue_lock:
        if pending_match:
            return
        if len(matchmaking_queue) >= max_lobby_players:
            players = list(matchmaking_queue[:max_lobby_players])

    if players:
        start_match_acceptance(players)


def add_to_queue(username, matchmaking_queue, upsert_player_activity, save_queue):
    if username not in matchmaking_queue:
        matchmaking_queue.append(username)
        upsert_player_activity(username, status='queued')
        save_queue()
        return True
    return False
