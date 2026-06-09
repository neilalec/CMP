import random
import time


def select_map_from_votes(lobby, all_skirmish_maps):
    if lobby.get('map_votes'):
        vote_counts = {}
        for username, map_choice in lobby['map_votes'].items():
            vote_counts[map_choice] = vote_counts.get(map_choice, 0) + 1
        max_votes = max(vote_counts.values())
        winning_maps = [map_name for map_name, votes in vote_counts.items() if votes == max_votes]
        selected_map = random.choice(winning_maps)
        return selected_map, vote_counts
    pool = lobby.get('map_pool') or all_skirmish_maps
    return random.choice(pool), {}


def handle_toggle_countdown_pause_event(
    data,
    *,
    request,
    socketio,
    socket_events,
    is_countdown_paused,
    set_countdown_paused,
    get_username_by_sid,
    is_admin_user,
    logger
):
    try:
        username = get_username_by_sid(request.sid)
        if not is_admin_user(username):
            return {'success': False, 'message': 'Admin access required'}

        desired_state = None
        if isinstance(data, dict) and 'paused' in data:
            desired_state = bool(data.get('paused'))

        if desired_state is None:
            new_state = set_countdown_paused(not is_countdown_paused())
        else:
            new_state = set_countdown_paused(desired_state)

        socketio.emit(socket_events['COUNTDOWN']['PAUSE_STATE'], {
            'paused': new_state
        })

        return {'success': True, 'paused': new_state}
    except Exception as e:
        logger.error(f"Error in handle_toggle_countdown_pause: {str(e)}")
        return {'success': False, 'message': 'Failed to toggle countdown pause'}


def handle_countdown_status_event(is_countdown_paused, logger):
    try:
        return {'success': True, 'paused': is_countdown_paused()}
    except Exception as e:
        logger.error(f"Error in handle_countdown_status: {str(e)}")
        return {'success': False, 'message': 'Failed to get countdown status'}


def handle_open_lobbies_status_event(get_open_lobbies, get_active_lobbies, logger):
    try:
        return {
            'success': True,
            'openLobbies': get_open_lobbies(),
            'activeLobbies': get_active_lobbies()
        }
    except Exception as e:
        logger.error(f"Error in handle_open_lobbies_status: {str(e)}")
        return {'success': False, 'message': 'Failed to get open lobbies'}


def handle_join_lobby_event(
    data,
    *,
    request,
    logger,
    lobbies,
    matchmaking_queue,
    queue_lock,
    MAX_LOBBY_PLAYERS,
    get_user_group,
    groups,
    user_to_group,
    save_queue,
    broadcast_queue_update,
    broadcast_open_lobbies_update,
    join_room,
    upsert_player_activity,
    get_user_room,
    get_player_groups,
        emit,
    emit_active_lobby_sync,
    assign_teams,
    select_captains
):
    try:
        lobby_id = data.get('lobby_id')
        username = data.get('username')
        is_rejoin = data.get('rejoin', False)
        allow_new = data.get('allow_new', False)

        logger.info(f"Join lobby request from {username} for lobby {lobby_id} (rejoin: {is_rejoin})")

        if lobby_id in lobbies:
            lobby = lobbies[lobby_id]
            max_players = int(lobby.get('max_players') or MAX_LOBBY_PLAYERS)

            is_lobby_member = username in lobby['players']
            was_disconnected = username in lobby.get('disconnected_players', set())
            has_open_slot = len(lobby['players']) < max_players

            if not is_lobby_member and not (is_rejoin and was_disconnected) and not (allow_new and has_open_slot):
                logger.warning(f"Unauthorized lobby join attempt by {username}")
                return {
                    'success': False,
                    'message': 'Not authorized to join this lobby'
                }

            if was_disconnected:
                lobby['disconnected_players'].remove(username)
                logger.info(f"Player {username} reconnected to lobby {lobby_id}")

            if allow_new and not is_lobby_member and not was_disconnected:
                lobby['players'].append(username)
                removed_from_queue = False
                for mode_id, queue in matchmaking_queue.items():
                    if username in queue:
                        queue.remove(username)
                        removed_from_queue = True
                if removed_from_queue:
                    save_queue()
                    broadcast_queue_update()
                if 'player_groups' in lobby and username not in lobby['player_groups']:
                    code = user_to_group.get(username)
                    if code and code in groups:
                        lobby['player_groups'][username] = code

                if lobby['teams'].get('team1') or lobby['teams'].get('team2'):
                    if len(lobby['teams']['team1']) <= len(lobby['teams']['team2']):
                        lobby['teams']['team1'].append(username)
                    else:
                        lobby['teams']['team2'].append(username)
                    lobby['captains'] = select_captains(lobby['teams'])
                elif lobby.get('step', 1) >= 2 and len(lobby['players']) >= 2:
                    lobby['teams'] = assign_teams(lobby['players'])
                    lobby['captains'] = select_captains(lobby['teams'])

            has_teams = lobby.get('teams') and (
                lobby['teams'].get('team1') or lobby['teams'].get('team2')
            )
            if has_teams:
                lobby['captains'] = select_captains(lobby['teams'])
                emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'players': lobby['players'],
                    'teams': lobby['teams'],
                    'captains': lobby.get('captains'),
                    'step': lobby['step'],
                    'queue_mode': lobby.get('queue_mode'),
                    'queue_label': lobby.get('queue_label'),
                    'match_size_label': lobby.get('match_size_label'),
                    'max_players': lobby.get('max_players'),
                    'map_pool': lobby.get('map_pool', [])
                }, room=lobby_id)

            broadcast_queue_update()
            broadcast_open_lobbies_update()

            join_room(lobby_id)

            upsert_player_activity(
                username,
                sid=request.sid,
                status='in_lobby',
                lobby_id=lobby_id,
                last_seen=time.time()
            )
            join_room(get_user_room(username))

            if 'player_groups' not in lobby:
                lobby['player_groups'] = get_player_groups(lobby.get('players', []))
            lobby_state = {
                'lobby_id': lobby_id,
                'players': lobby['players'],
                'teams': lobby['teams'],
                'captains': lobby.get('captains'),
                'step': lobby['step'],
                'countdown': lobby.get('countdown'),
                'voting_countdown': lobby.get('voting_countdown'),
                'selected_map': lobby.get('selected_map'),
                'queue_mode': lobby.get('queue_mode'),
                'queue_label': lobby.get('queue_label'),
                'match_size_label': lobby.get('match_size_label'),
                'max_players': max_players,
                'server_details': lobby.get('server_details'),
                'server_details_provided_at': lobby.get('server_details_provided_at'),
                'live_roll_ready_at': lobby.get('live_roll_ready_at'),
                'live_roll_countdown': lobby.get('live_roll_countdown'),
                'map_pool': lobby.get('map_pool', []),
                'map_votes': lobby.get('map_votes', {}),
                'vote_counts': lobby.get('vote_counts', {}),
                'player_groups': lobby.get('player_groups', {}),
                'announcement': lobby.get('announcement')
            }

            if was_disconnected:
                emit('player_reconnected', {'username': username}, room=lobby_id)
            emit_active_lobby_sync(username, lobby_id)

            return {
                'success': True,
                'data': lobby_state,
                'message': 'Rejoined lobby successfully' if was_disconnected else 'Joined lobby successfully'
            }

        logger.warning(f"Attempted to join non-existent lobby: {lobby_id}")
        return {
            'success': False,
            'message': 'Lobby not found'
        }
    except Exception as e:
        logger.error(f"Error in handle_join_lobby: {str(e)}")
        return {
            'success': False,
            'message': 'Failed to join lobby'
        }


def handle_leave_lobby_event(
    data,
    *,
    request,
    logger,
    lobbies,
    get_username_by_sid,
    player_activity,
    get_player_sids,
    socketio,
    emit,
    broadcast_queue_update,
    broadcast_open_lobbies_update,
    emit_active_lobby_sync,
    select_captains,
    record_lobby_event=None,
    release_server_allocation=None
):
    try:
        lobby_id = data.get('lobby_id')
        username = data.get('username', get_username_by_sid(request.sid))

        logger.info(f"Leave lobby request from {username} for lobby {lobby_id}")

        if not lobby_id or not username:
            return {
                'success': False,
                'message': 'Missing lobby_id or username'
            }

        if lobby_id in lobbies:
            lobby = lobbies[lobby_id]

            if username in lobby['players']:
                if record_lobby_event:
                    record_lobby_event(lobby_id, 'player_left_lobby', {
                        'username': username,
                        'remaining_players': [player for player in lobby['players'] if player != username]
                    }, created_at=time.time())
                lobby['players'].remove(username)
                for team in ['team1', 'team2']:
                    if username in lobby['teams'][team]:
                        lobby['teams'][team].remove(username)

                if lobby.get('captains') is not None:
                    lobby['captains'] = select_captains(lobby['teams'])

                if 'disconnected_players' in lobby and username in lobby['disconnected_players']:
                    lobby['disconnected_players'].remove(username)

                if username in player_activity:
                    player_activity[username].pop('lobby_id', None)
                    player_activity[username]['status'] = 'authenticated'
                    player_activity[username]['last_seen'] = time.time()

                for sid in get_player_sids(username):
                    socketio.server.leave_room(sid, lobby_id)

                emit('player_left', {
                    'username': username,
                    'lobby_id': lobby_id
                }, room=lobby_id)

                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'players': lobby['players'],
                    'teams': lobby['teams'],
                    'captains': lobby.get('captains'),
                    'step': lobby.get('step', 1),
                    'queue_mode': lobby.get('queue_mode'),
                    'queue_label': lobby.get('queue_label'),
                    'match_size_label': lobby.get('match_size_label'),
                    'max_players': lobby.get('max_players'),
                    'map_pool': lobby.get('map_pool', [])
                }, room=lobby_id)

                if not lobby['players']:
                    logger.info(f"Removed empty lobby {lobby_id}")
                    if record_lobby_event:
                        record_lobby_event(lobby_id, 'lobby_closed', {
                            'reason': 'empty'
                        }, created_at=time.time())
                    if release_server_allocation:
                        release_server_allocation(lobby_id, reason='lobby_closed')
                    del lobbies[lobby_id]
                broadcast_queue_update()
                broadcast_open_lobbies_update()

                logger.info(f"Player {username} left lobby {lobby_id}")
                emit_active_lobby_sync(username, None)
                return {
                    'success': True,
                    'message': 'Successfully left lobby'
                }

        return {
            'success': False,
            'message': 'Lobby not found or player not in lobby'
        }
    except Exception as e:
        logger.error(f"Error in handle_leave_lobby: {str(e)}")
        return {
            'success': False,
            'message': 'Failed to leave lobby'
        }


def handle_delete_lobby_event(
    data,
    *,
    request,
    logger,
    lobbies,
    socketio,
    get_username_by_sid,
    is_admin_user,
    player_activity,
    get_player_sids,
    emit_active_lobby_sync,
    broadcast_queue_update,
    broadcast_open_lobbies_update,
    record_lobby_event=None,
    release_server_allocation=None
):
    try:
        username = get_username_by_sid(request.sid)
        if not is_admin_user(username):
            return {'success': False, 'message': 'Admin access required'}

        lobby_id = data.get('lobby_id') if data else None
        if not lobby_id:
            return {'success': False, 'message': 'Missing lobby_id'}

        lobby = lobbies.get(lobby_id)
        if not lobby:
            return {'success': False, 'message': 'Lobby not found'}

        players = list(lobby.get('players', []))

        if record_lobby_event:
            record_lobby_event(lobby_id, 'lobby_deleted', {
                'deleted_by': username,
                'players': players
            }, created_at=time.time())

        for player in players:
            if player in player_activity:
                player_activity[player].pop('lobby_id', None)
                player_activity[player]['status'] = 'authenticated'
                player_activity[player]['last_seen'] = time.time()
            for sid in get_player_sids(player):
                socketio.server.leave_room(sid, lobby_id)
            emit_active_lobby_sync(player, None)

        if release_server_allocation:
            release_server_allocation(lobby_id, reason='admin_deleted')

        del lobbies[lobby_id]

        broadcast_queue_update()
        broadcast_open_lobbies_update()

        return {
            'success': True,
            'message': 'Lobby deleted'
        }
    except Exception as e:
        logger.error(f"Error in handle_delete_lobby: {str(e)}")
        return {
            'success': False,
            'message': 'Failed to delete lobby'
        }


def handle_skip_phase_event(
    data,
    *,
    request,
    logger,
    lobbies,
    select_map_from_votes_fn,
    socketio,
    start_live_roll_monitor,
    get_server_connection_details,
    ready_grace_seconds,
    get_username_by_sid,
    is_admin_user,
    record_lobby_event=None
):
    try:
        username = get_username_by_sid(request.sid)
        if not is_admin_user(username):
            return {'success': False, 'message': 'Admin access required'}

        lobby_id = data.get('lobby_id')
        lobby = lobbies.get(lobby_id)
        if not lobby:
            return {'success': False, 'message': 'Lobby not found'}

        lobby['skip_phase'] = True
        lobby['countdown_token'] = lobby.get('countdown_token', 0) + 1
        step = lobby.get('step', 1)

        if step == 2:
            selected_map, vote_counts = select_map_from_votes_fn(lobby)
            lobby['selected_map'] = selected_map
            lobby['server_details'] = get_server_connection_details(server_id=lobby.get('server_id'))
            lobby['server_details_provided_at'] = time.time()
            lobby['live_roll_ready_at'] = lobby['server_details_provided_at'] + ready_grace_seconds
            lobby['live_roll_countdown'] = ready_grace_seconds
            lobby['live_roll_command_sent'] = False
            lobby['live_roll_next_layer_sent'] = False
            lobby['live_roll_change_attempts'] = 0
            lobby['live_roll_last_change_attempt_at'] = None
            lobby['live_roll_team_swap_attempts'] = {}
            lobby['live_roll_done'] = False
            lobby['live_broadcast_sent'] = False
            lobby['live_broadcast_attempts'] = 0
            lobby['live_broadcast_last_attempt_at'] = None
            lobby['live_broadcast_ready_at'] = None
            lobby['live_broadcast_error'] = None
            lobby['round_result'] = None
            lobby['step'] = 3
            lobby['announcement'] = None
            if record_lobby_event:
                record_lobby_event(lobby_id, 'phase_skipped_to_server', {
                    'selected_map': selected_map,
                    'vote_counts': vote_counts,
                    'server_details': lobby.get('server_details')
                }, created_at=lobby['server_details_provided_at'])
            socketio.emit('lobby_update', {
                'lobby_id': lobby_id,
                'selected_map': selected_map,
                'step': 3,
                'vote_counts': vote_counts,
                'server_details': lobby.get('server_details'),
                'server_details_provided_at': lobby.get('server_details_provided_at'),
                'live_roll_ready_at': lobby.get('live_roll_ready_at'),
                'live_roll_countdown': lobby.get('live_roll_countdown'),
                'announcement': None,
                'queue_mode': lobby.get('queue_mode'),
                'queue_label': lobby.get('queue_label'),
                'match_size_label': lobby.get('match_size_label'),
                'max_players': lobby.get('max_players'),
                'map_pool': lobby.get('map_pool', [])
            }, room=lobby_id)
            start_live_roll_monitor(lobby_id)
            lobby['skip_phase'] = False
            return {'success': True, 'step': 3}

        lobby['skip_phase'] = False
        return {'success': False, 'message': 'No skippable phase'}
    except Exception as e:
        logger.error(f"Error in handle_skip_phase: {str(e)}")
        return {'success': False, 'message': 'Failed to skip phase'}


def handle_prev_phase_event(
    data,
    *,
    request,
    logger,
    dev_mode,
    lobbies,
    socketio,
    get_username_by_sid,
    is_admin_user,
    record_lobby_event=None
):
    if not dev_mode:
        return {'success': False, 'message': 'Dev mode disabled'}
    try:
        username = get_username_by_sid(request.sid)
        if not is_admin_user(username):
            return {'success': False, 'message': 'Admin access required'}

        lobby_id = data.get('lobby_id')
        lobby = lobbies.get(lobby_id)
        if not lobby:
            return {'success': False, 'message': 'Lobby not found'}

        lobby['countdown_token'] = lobby.get('countdown_token', 0) + 1
        lobby['live_roll_token'] = lobby.get('live_roll_token', 0) + 1
        lobby['countdown'] = None
        lobby['voting_countdown'] = None
        lobby['skip_phase'] = False
        lobby['live_roll_done'] = False
        lobby['live_roll_command_sent'] = False
        lobby['live_roll_next_layer_sent'] = False
        lobby['live_roll_change_attempts'] = 0
        lobby['live_roll_last_change_attempt_at'] = None
        lobby['live_roll_team_swap_attempts'] = {}
        lobby['live_broadcast_sent'] = False
        lobby['live_broadcast_attempts'] = 0
        lobby['live_broadcast_last_attempt_at'] = None
        lobby['live_broadcast_ready_at'] = None
        lobby['live_broadcast_error'] = None
        lobby['round_result'] = None

        current_step = lobby.get('step', 2)
        lobby['step'] = max(2, current_step - 1)

        if lobby['step'] == 2:
            lobby['selected_map'] = None
            lobby['server_details'] = None
            lobby['server_details_provided_at'] = None
            lobby['live_roll_ready_at'] = None
            lobby['live_roll_countdown'] = None
            lobby['announcement'] = None
            lobby['map_votes'] = {}
            lobby['vote_counts'] = {}
            lobby['voting_countdown'] = 30

        if record_lobby_event:
            record_lobby_event(lobby_id, 'phase_reverted', {
                'step': lobby['step'],
                'selected_map': lobby.get('selected_map')
            }, created_at=time.time())

        socketio.emit('lobby_update', {
            'lobby_id': lobby_id,
            'step': lobby['step'],
            'players': lobby.get('players'),
            'teams': lobby.get('teams'),
            'captains': lobby.get('captains'),
            'selected_map': lobby.get('selected_map'),
            'server_details': lobby.get('server_details'),
            'server_details_provided_at': lobby.get('server_details_provided_at'),
            'live_roll_ready_at': lobby.get('live_roll_ready_at'),
            'live_roll_countdown': lobby.get('live_roll_countdown'),
            'announcement': lobby.get('announcement'),
            'countdown': lobby.get('countdown'),
            'queue_mode': lobby.get('queue_mode'),
            'queue_label': lobby.get('queue_label'),
            'match_size_label': lobby.get('match_size_label'),
            'max_players': lobby.get('max_players'),
            'map_pool': lobby.get('map_pool', [])
        }, room=lobby_id)

        return {'success': True, 'step': lobby['step']}
    except Exception as e:
        logger.error(f"Error in handle_prev_phase: {str(e)}")
        return {'success': False, 'message': 'Failed to go back a phase'}


def handle_start_lobby_event(data, *, lobbies, emit, socket_events):
    lobby_id = data.get('lobby_id')
    lobby = lobbies.get(lobby_id)
    if lobby:
        emit(socket_events['LOBBY']['READY'], {
            'teams': lobby['teams'],
            'map': lobby['selected_map'],
            'server_ip': lobby['server_ip']
        }, room=lobby_id)


def handle_get_lobby_data_event(data, *, lobbies, emit, socket_events):
    lobby_id = data.get('lobby_id')
    lobby = lobbies.get(lobby_id)
    if lobby:
        emit(socket_events['LOBBY']['DATA'], {
            'lobby_id': lobby_id,
            'players': lobby['players'],
            'teams': lobby['teams'],
            'captains': lobby.get('captains'),
            'map_pool': lobby.get('map_pool', []),
            'selected_map': lobby.get('selected_map'),
            'queue_mode': lobby.get('queue_mode'),
            'queue_label': lobby.get('queue_label'),
            'match_size_label': lobby.get('match_size_label'),
            'max_players': lobby.get('max_players'),
            'server_ip': lobby.get('server_ip'),
            'step': lobby.get('step'),
            'voting_countdown': lobby.get('voting_countdown'),
            'player_groups': lobby.get('player_groups', {}),
            'map_votes': lobby.get('map_votes', {}),
            'vote_counts': lobby.get('vote_counts', {}),
            'server_details': lobby.get('server_details'),
            'server_details_provided_at': lobby.get('server_details_provided_at'),
            'live_roll_ready_at': lobby.get('live_roll_ready_at'),
            'live_roll_countdown': lobby.get('live_roll_countdown'),
            'announcement': lobby.get('announcement')
        })
    else:
        emit(socket_events['ERROR'], {'msg': 'Lobby not found.'})


def handle_server_presence_event(data, *, logger, build_lobby_server_presence):
    try:
        lobby_id = data.get('lobby_id') if data else None
        if not lobby_id:
            return {'success': False, 'message': 'Missing lobby_id'}
        return {
            'success': True,
            'presence': build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=True)
        }
    except ValueError as e:
        return {'success': False, 'message': str(e)}
    except Exception as e:
        logger.error(f"Error in get_lobby_server_presence: {str(e)}")
        return {'success': False, 'message': 'Failed to get lobby server presence'}


def vote_map_event(data, *, request, logger, lobbies, socketio, get_username_by_sid):
    try:
        lobby_id = data.get('lobby_id')
        map_choice = data.get('map')

        logger.info(f"Received vote request - Lobby: {lobby_id}, Map: {map_choice}")

        if not lobby_id or not map_choice:
            logger.error("Missing required data for vote")
            return {'success': False, 'message': 'Missing required data'}

        lobby = lobbies.get(lobby_id)
        if not lobby:
            logger.error(f"Lobby {lobby_id} not found")
            return {'success': False, 'message': 'Lobby not found'}

        username = get_username_by_sid(request.sid)
        if not username:
            logger.error(f"User not found for SID: {request.sid}")
            return {'success': False, 'message': 'User not found'}

        logger.info(f"Processing vote for {username} in lobby {lobby_id}")

        if 'map_votes' not in lobby:
            lobby['map_votes'] = {}

        lobby['map_votes'][username] = map_choice

        vote_counts = {}
        for user, vote in lobby['map_votes'].items():
            vote_counts[vote] = vote_counts.get(vote, 0) + 1

        logger.info(f"Current votes in lobby {lobby_id}:")
        logger.info(f"Map votes: {lobby['map_votes']}")
        logger.info(f"Vote counts: {vote_counts}")

        current_countdown = lobby.get('voting_countdown', 15)

        socketio.emit('lobby_countdown_voting', {
            'countdown': current_countdown,
            'lobby_id': lobby_id,
            'type': 'voting',
            'map_votes': lobby['map_votes'],
            'vote_counts': vote_counts,
            'queue_mode': lobby.get('queue_mode'),
            'queue_label': lobby.get('queue_label'),
            'match_size_label': lobby.get('match_size_label'),
            'max_players': lobby.get('max_players'),
            'map_pool': lobby.get('map_pool', [])
        }, room=lobby_id)

        return {'success': True}
    except Exception as e:
        logger.error(f"Error in vote_map: {str(e)}")
        return {'success': False, 'message': str(e)}
