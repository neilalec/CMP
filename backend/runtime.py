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


def cleanup_stale_players(
    *,
    queue_lock,
    player_activity,
    matchmaking_queue,
    broadcast_queue_update,
    logger,
    eventlet
):
    while True:
        try:
            current_time = __import__('time').time()
            stale_timeout = 300

            with queue_lock:
                for username, data in list(player_activity.items()):
                    if (
                        data.get('status') == 'disconnected'
                        and current_time - data.get('last_seen', 0) > stale_timeout
                    ):
                        logger.info(f"Removing stale player {username}")
                        for queue in matchmaking_queue.values():
                            if username in queue:
                                queue.remove(username)
                        del player_activity[username]
                        broadcast_queue_update()
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
