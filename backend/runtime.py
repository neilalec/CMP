PRE_LIVE_LOBBY_STEPS = {1, 2, 3}


def cleanup_player(
    username,
    *,
    matchmaking_queue,
    player_activity,
    lobbies,
    emit,
    save_queue
):
    removed_from_queue = False
    for queue in matchmaking_queue.values():
        if username in queue:
            queue.remove(username)
            removed_from_queue = True
    if removed_from_queue:
        save_queue()

    if username in player_activity:
        del player_activity[username]

    for lobby_id, lobby in list(lobbies.items()):
        if username in lobby['players']:
            emit('player_disconnected', {
                'username': username,
                'msg': f'Player {username} has disconnected'
            }, room=lobby_id)
            del lobbies[lobby_id]


def _remove_player_from_lobby_roster(lobby, username, *, select_captains=None):
    removed = False
    if username in lobby.get('players', []):
        lobby['players'].remove(username)
        removed = True

    teams = lobby.get('teams') or {}
    for team_name in ('team1', 'team2'):
        team_players = teams.get(team_name) or []
        if username in team_players:
            team_players.remove(username)
            removed = True

    disconnected_players = lobby.get('disconnected_players')
    if isinstance(disconnected_players, set):
        disconnected_players.discard(username)
    elif isinstance(disconnected_players, list) and username in disconnected_players:
        disconnected_players.remove(username)

    player_groups = lobby.get('player_groups')
    if isinstance(player_groups, dict):
        player_groups.pop(username, None)

    if removed and lobby.get('captains') is not None and select_captains and teams:
        lobby['captains'] = select_captains(teams)

    return removed


def cleanup_stale_disconnected_players(
    *,
    current_time,
    queue_lock,
    player_activity,
    matchmaking_queue,
    lobbies,
    broadcast_queue_update,
    broadcast_open_lobbies_update=None,
    socketio=None,
    build_player_profile_map=None,
    select_captains=None,
    emit_active_lobby_sync=None,
    record_lobby_event=None,
    release_server_allocation=None,
    save_runtime_state=None,
    queue_stale_timeout=300,
    lobby_disconnect_grace_seconds=600,
    web_lobby_disconnect_tracking_enabled=False,
    logger=None
):
    queue_changed = False
    lobbies_changed = False

    with queue_lock:
        for username, data in list(player_activity.items()):
            if data.get('status') != 'disconnected':
                continue

            elapsed_seconds = current_time - data.get('last_seen', 0)
            stale_for_queue = elapsed_seconds > queue_stale_timeout
            stale_for_lobby = elapsed_seconds > lobby_disconnect_grace_seconds

            if stale_for_queue:
                for queue in matchmaking_queue.values():
                    while username in queue:
                        queue.remove(username)
                        queue_changed = True

            lobby_id = data.get('lobby_id')
            lobby = lobbies.get(lobby_id) if lobby_id else None
            if not lobby:
                lobby_id = None
                for candidate_lobby_id, candidate_lobby in lobbies.items():
                    if username in candidate_lobby.get('players', []):
                        lobby_id = candidate_lobby_id
                        lobby = candidate_lobby
                        break

            lobby_step = int((lobby or {}).get('step') or 1) if lobby else None
            should_reopen_lobby_slot = (
                web_lobby_disconnect_tracking_enabled
                and lobby is not None
                and lobby_step in PRE_LIVE_LOBBY_STEPS
                and stale_for_lobby
            )

            if should_reopen_lobby_slot:
                if _remove_player_from_lobby_roster(lobby, username, select_captains=select_captains):
                    lobbies_changed = True
                    if logger:
                        logger.info(f"Removed stale disconnected player {username} from lobby {lobby_id}")
                    if record_lobby_event:
                        record_lobby_event(lobby_id, 'player_removed_after_disconnect_timeout', {
                            'username': username,
                            'grace_seconds': lobby_disconnect_grace_seconds,
                            'step': lobby_step
                        }, created_at=current_time)
                    if socketio:
                        socketio.emit('player_left', {
                            'username': username,
                            'lobby_id': lobby_id,
                            'reason': 'disconnect_timeout'
                        }, room=lobby_id)
                        socketio.emit('lobby_update', {
                            'lobby_id': lobby_id,
                            'players': lobby.get('players', []),
                            'player_profiles': build_player_profile_map(lobby.get('players', [])) if build_player_profile_map else {},
                            'teams': lobby.get('teams'),
                            'captains': lobby.get('captains'),
                            'step': lobby.get('step', 1),
                            'queue_mode': lobby.get('queue_mode'),
                            'queue_label': lobby.get('queue_label'),
                            'match_size_label': lobby.get('match_size_label'),
                            'max_players': lobby.get('max_players'),
                            'map_pool': lobby.get('map_pool', [])
                        }, room=lobby_id)

                if lobby is not None and not lobby.get('players'):
                    if logger:
                        logger.info(f"Removed empty abandoned lobby {lobby_id}")
                    if record_lobby_event:
                        record_lobby_event(lobby_id, 'lobby_closed', {
                            'reason': 'disconnect_timeout'
                        }, created_at=current_time)
                    if release_server_allocation:
                        release_server_allocation(lobby_id, reason='disconnect_timeout')
                    lobbies.pop(lobby_id, None)
                    lobbies_changed = True

                if emit_active_lobby_sync:
                    emit_active_lobby_sync(username, None)
                player_activity.pop(username, None)
                continue

            if not lobby and stale_for_queue:
                player_activity.pop(username, None)
            elif lobby_step not in PRE_LIVE_LOBBY_STEPS and stale_for_queue:
                player_activity.pop(username, None)

    if queue_changed:
        broadcast_queue_update()
    if lobbies_changed and broadcast_open_lobbies_update:
        broadcast_open_lobbies_update()
    if (queue_changed or lobbies_changed) and save_runtime_state:
        save_runtime_state()

    return {
        'queueChanged': queue_changed,
        'lobbiesChanged': lobbies_changed
    }


def cleanup_stale_players(
    *,
    queue_lock,
    player_activity,
    matchmaking_queue,
    lobbies=None,
    broadcast_queue_update,
    broadcast_open_lobbies_update=None,
    socketio=None,
    build_player_profile_map=None,
    select_captains=None,
    emit_active_lobby_sync=None,
    record_lobby_event=None,
    release_server_allocation=None,
    save_runtime_state=None,
    lobby_disconnect_grace_seconds=600,
    web_lobby_disconnect_tracking_enabled=False,
    logger,
    eventlet
):
    while True:
        try:
            current_time = __import__('time').time()
            cleanup_stale_disconnected_players(
                current_time=current_time,
                queue_lock=queue_lock,
                player_activity=player_activity,
                matchmaking_queue=matchmaking_queue,
                lobbies=lobbies or {},
                broadcast_queue_update=broadcast_queue_update,
                broadcast_open_lobbies_update=broadcast_open_lobbies_update,
                socketio=socketio,
                build_player_profile_map=build_player_profile_map,
                select_captains=select_captains,
                emit_active_lobby_sync=emit_active_lobby_sync,
                record_lobby_event=record_lobby_event,
                release_server_allocation=release_server_allocation,
                save_runtime_state=save_runtime_state,
                lobby_disconnect_grace_seconds=lobby_disconnect_grace_seconds,
                web_lobby_disconnect_tracking_enabled=web_lobby_disconnect_tracking_enabled,
                logger=logger
            )
        except Exception as e:
            logger.error(f"Error in cleanup_stale_players: {str(e)}")
        finally:
            eventlet.sleep(60)


def cleanup_on_start(*, reset_state, save_queue, logger):
    logger.info("Cleaning up stale state...")
    reset_state()
    save_queue()
    logger.info("Cleanup complete")


def start_periodic_tasks(
    *,
    socketio,
    periodic_queue_management,
    cleanup_stale_players_task,
    runtime_state_persistence_task=None,
    resume_lobby_tasks=None,
    logger
):
    def safe_start(task, name):
        try:
            socketio.start_background_task(task)
            logger.info(f"Started {name} task")
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")

    safe_start(periodic_queue_management, "queue management")
    safe_start(cleanup_stale_players_task, "stale player cleanup")
    if runtime_state_persistence_task:
        safe_start(runtime_state_persistence_task, "runtime state persistence")
    if resume_lobby_tasks:
        resume_lobby_tasks()


def start_auth_timeout(
    sid,
    username=None,
    *,
    player_activity,
    socketio,
    logger,
    eventlet
):
    def check_auth():
        eventlet.sleep(10)
        if not username:
            if any(data.get('sid') == sid and data.get('status') == 'connected' for data in player_activity.values()):
                logger.warning(f"Authentication timeout for SID: {sid}")
                socketio.disconnect(sid)
        else:
            user_data = player_activity.get(username)
            if user_data and user_data['sid'] == sid and user_data['status'] == 'connected':
                logger.warning(f"Authentication timeout for user: {username}")
                socketio.disconnect(sid)

    eventlet.spawn(check_auth)


def periodic_queue_management(*, app_context, broadcast_queue_update, logger, eventlet, countdown_active_ref):
    while True:
        try:
            with app_context():
                if not countdown_active_ref():
                    broadcast_queue_update()
        except Exception as e:
            logger.error(f"Error in queue management: {str(e)}")
        eventlet.sleep(5)


def periodic_runtime_state_persistence(*, save_runtime_state, logger, eventlet, interval_seconds=5):
    while True:
        try:
            save_runtime_state()
        except Exception as e:
            logger.error(f"Error saving runtime state: {str(e)}")
        finally:
            eventlet.sleep(interval_seconds)
