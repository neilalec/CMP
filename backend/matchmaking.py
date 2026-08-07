import json
import logging
import random
import time
from functools import wraps

import eventlet

from app_state import DEFAULT_QUEUE_MODE, MAP_VOTE_COUNTDOWN, MATCH_ACCEPT_COUNTDOWN, MAX_LOBBY_PLAYERS, QUEUE_MODES
from services.queue import (
    add_to_queue as add_to_queue_service,
    build_queue_payload as build_queue_payload_service,
    cancel_pending_match as cancel_pending_match_service,
    check_queue_and_start_countdown as check_queue_and_start_countdown_service,
    finalize_pending_match as finalize_pending_match_service,
    has_available_server_capacity,
    find_user_queue_mode,
    get_pending_for_mode,
    get_queue_for_mode,
    start_match_acceptance as start_match_acceptance_service,
    update_queue_state as update_queue_state_service
)
from state.group import get_player_groups, get_user_group
from state.lobby import emit_active_lobby_sync, get_player_sids, is_user_in_any_lobby, upsert_player_activity
from state.runtime import is_countdown_paused, pause_aware_sleep, with_retry


def _app():
    import app as backend_app
    return backend_app


def handle_socket_data(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        data = args[0] if args else {}
        if isinstance(data, list):
            data = data[0] if data else {}
        args = (data,) + args[1:]
        return f(*args, **kwargs)
    return decorated


def log_event(event_type, data):
    app = _app()
    app.logger.info(json.dumps({
        'event': event_type,
        'data': data,
        'timestamp': time.time()
    }))


def get_queue_config(queue_mode):
    return QUEUE_MODES.get(queue_mode or DEFAULT_QUEUE_MODE, QUEUE_MODES[DEFAULT_QUEUE_MODE])


def build_lobby_map_pool(queue_config):
    full_pool = list(queue_config.get('vote_pool') or queue_config['map_pool'])
    if queue_config.get('vote_pool'):
        return full_pool
    queue_identity = ' '.join([
        str(queue_config.get('id') or ''),
        str(queue_config.get('label') or ''),
        str(queue_config.get('short_label') or '')
    ]).strip().lower()
    if (
        queue_config.get('id') == 'hotdrop'
        or str(queue_config.get('id') or '').startswith('sec')
        or 'hotdrop' in queue_identity
        or 'esports cup' in queue_identity
        or queue_config.get('max_players') == 60
    ):
        return full_pool
    return random.sample(full_pool, k=min(5, len(full_pool)))


def resolve_selected_map_variant(selected_map, queue_config):
    variants = (queue_config or {}).get('map_variants') or {}
    options = variants.get(selected_map)
    if options:
        return random.choice(list(options))
    return selected_map


def select_map_from_votes(lobby):
    queue_config = get_queue_config(lobby.get('queue_mode'))
    if lobby.get('map_votes'):
        vote_counts = {}
        for username, map_choice in lobby['map_votes'].items():
            vote_counts[map_choice] = vote_counts.get(map_choice, 0) + 1
        max_votes = max(vote_counts.values())
        winning_maps = [map_name for map_name, votes in vote_counts.items() if votes == max_votes]
        voted_map = random.choice(winning_maps)
        return resolve_selected_map_variant(voted_map, queue_config), vote_counts
    pool = lobby.get('map_pool') or build_lobby_map_pool(queue_config)
    voted_map = random.choice(pool)
    return resolve_selected_map_variant(voted_map, queue_config), {}


def save_queue(queue=None):
    app = _app()
    try:
        queues_to_save = queue or app.matchmaking_queue
        with app.get_db_connection() as conn:
            conn.execute('DELETE FROM queue_entries')
            rows = []
            for mode_id, members in queues_to_save.items():
                for index, username in enumerate(members):
                    rows.append((mode_id, index, username))
            conn.executemany(
                'INSERT INTO queue_entries (mode, position, username) VALUES (?, ?, ?)',
                rows
            )
            conn.commit()
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to save queue to SQLite: {str(e)}")


def broadcast_queue_update(countdown=None):
    app = _app()
    try:
        app.logger.debug(f"Queue before broadcast: {app.matchmaking_queue}")
        queue_status = build_queue_payload(username=None)
        if countdown is not None:
            queue_status['countdown'] = countdown
        app.socketio.emit(app.SOCKET_EVENTS['QUEUE']['UPDATE'], queue_status, room=None)
        for username in list(app.player_activity.keys()):
            personalized_status = build_queue_payload(username=username)
            if countdown is not None:
                personalized_status['countdown'] = countdown
            app.socketio.emit(
                app.SOCKET_EVENTS['QUEUE']['UPDATE'],
                personalized_status,
                room=app.get_user_room(username)
            )
        app.logger.debug(f"Broadcasting queue update: {queue_status}")
    except Exception as e:
        app.logger.error(f"Error in broadcast_queue_update: {str(e)}")


def build_queue_payload(username=None, countdown=None, queue_mode=None):
    app = _app()
    return build_queue_payload_service(
        app.matchmaking_queue,
        app.user_has_steam_id,
        app.get_match_accept_payload,
        QUEUE_MODES,
        lobbies=app.lobbies,
        pending_match=app.pending_match,
        server_capacity=app.get_server_pool_capacity(),
        username=username,
        countdown=countdown,
        queue_mode=queue_mode
    )


def cancel_pending_match(reason='Match acceptance cancelled.', remove_players=None, queue_mode=None):
    app = _app()
    current_pending_match = get_pending_for_mode(app.pending_match, queue_mode) if queue_mode else next(
        (match for match in app.pending_match.values() if match),
        None
    )
    app.logger.info(
        "Cancelling pending match: mode=%s reason=%s current_pending=%s remove_players=%s",
        queue_mode or (current_pending_match or {}).get('queue_mode'),
        reason,
        current_pending_match.get('id') if current_pending_match else None,
        remove_players
    )
    success, _removed_players = cancel_pending_match_service(
        queue_lock=app.queue_lock,
        pending_match=current_pending_match,
        matchmaking_queue=app.matchmaking_queue,
        player_activity=app.player_activity,
        save_queue=save_queue,
        broadcast_queue_update=broadcast_queue_update,
        socketio=app.socketio,
        socket_events=app.SOCKET_EVENTS,
        get_user_room=app.get_user_room,
        reason=reason,
        remove_players=remove_players
    )
    if success:
        match_mode = current_pending_match.get('queue_mode')
        app.pending_match[match_mode] = None
        app.countdown_active = False
    return success


def finalize_pending_match(match_id):
    app = _app()
    current_pending_match = next(
        (match for match in app.pending_match.values() if match and match.get('id') == match_id),
        None
    )
    app.logger.info(
        "Finalizing pending match: match_id=%s current_pending=%s",
        match_id,
        current_pending_match.get('id') if current_pending_match else None
    )
    lobby_id = finalize_pending_match_service(
        current_pending_match,
        match_id,
        broadcast_queue_update,
        create_lobby
    )
    if lobby_id:
        app.pending_match[current_pending_match.get('queue_mode')] = None
        app.logger.info("Pending match cleared: match_id=%s", match_id)
    return lobby_id


def start_match_acceptance(players, queue_mode):
    app = _app()
    queue_config = get_queue_config(queue_mode)
    current_pending_match = get_pending_for_mode(app.pending_match, queue_mode)

    def finalize_wrapper(match_id):
        return finalize_pending_match(match_id)

    def cancel_wrapper(reason, remove_players=None):
        return cancel_pending_match(reason=reason, remove_players=remove_players, queue_mode=queue_mode)

    success, new_pending_match = start_match_acceptance_service(
        players=players,
        queue_mode=queue_mode,
        max_lobby_players=queue_config['max_players'],
        match_accept_countdown=MATCH_ACCEPT_COUNTDOWN,
        pending_match=current_pending_match,
        set_pending_match=lambda state: app.pending_match.__setitem__(queue_mode, state),
        broadcast_queue_update=broadcast_queue_update,
        pause_aware_sleep=pause_aware_sleep,
        finalize_pending_match=finalize_wrapper,
        cancel_pending_match=cancel_wrapper
    )
    if success:
        app.countdown_active = False
        app.logger.info(
            "Pending match stored: mode=%s id=%s players=%s countdown=%s",
            queue_mode,
            new_pending_match.get('id'),
            new_pending_match.get('players'),
            new_pending_match.get('countdown')
        )
    return success


def update_queue_state(save=True, broadcast=True):
    app = _app()
    try:
        update_queue_state_service(
            queue_lock=app.queue_lock,
            save_queue=save_queue,
            socketio=app.socketio,
            socket_events=app.SOCKET_EVENTS,
            matchmaking_queue=app.matchmaking_queue,
            save=save,
            broadcast=broadcast
        )
    except Exception as e:
        app.logger.error(f"Failed to update queue state: {str(e)}")


def check_queue_and_start_countdown():
    app = _app()
    try:
        check_queue_and_start_countdown_service(
            queue_lock=app.queue_lock,
            pending_match=app.pending_match,
            matchmaking_queue=app.matchmaking_queue,
            queue_modes=QUEUE_MODES,
            lobbies=app.lobbies,
            server_capacity=app.get_server_pool_capacity(),
            start_match_acceptance=start_match_acceptance
        )
    except Exception as e:
        app.logger.error(f"Error starting match acceptance: {e}")


def add_to_queue(username, queue_mode):
    app = _app()
    return add_to_queue_service(
        username,
        app.matchmaking_queue,
        queue_mode,
        upsert_player_activity,
        save_queue
    )


def start_map_voting(lobby_id):
    app = _app()
    try:
        lobby = app.lobbies.get(lobby_id)
        if not lobby:
            app.logger.error(f"Lobby {lobby_id} not found when starting map vote")
            return
        saved_countdown = lobby.get('voting_countdown')
        try:
            countdown = int(saved_countdown)
        except (TypeError, ValueError):
            countdown = MAP_VOTE_COUNTDOWN
        if countdown < 0 or countdown > MAP_VOTE_COUNTDOWN:
            countdown = MAP_VOTE_COUNTDOWN

        lobby['countdown_token'] = lobby.get('countdown_token', 0) + 1
        countdown_token = lobby['countdown_token']
        app.logger.info(f"Starting map voting countdown for lobby {lobby_id}")

        if 'map_votes' not in lobby:
            lobby['map_votes'] = {}

        if 'map_pool' not in lobby or not lobby['map_pool']:
            queue_config = get_queue_config(lobby.get('queue_mode'))
            lobby['map_pool'] = build_lobby_map_pool(queue_config)

        lobby['voting_countdown'] = countdown

        while countdown > 0:
            if lobby.get('step') != 2 or lobby.get('skip_phase'):
                return
            if lobby.get('countdown_token') != countdown_token:
                return
            if is_countdown_paused():
                eventlet.sleep(0.2)
                continue

            app.socketio.emit('lobby_countdown_voting', {
                'countdown': countdown,
                'lobby_id': lobby_id,
                'type': 'voting',
                'map_pool': lobby.get('map_pool', []),
                'map_votes': lobby['map_votes'],
                'queue_mode': lobby.get('queue_mode'),
                'queue_label': lobby.get('queue_label'),
                'match_size_label': lobby.get('match_size_label'),
                'max_players': lobby.get('max_players'),
                'vote_counts': {vote: sum(1 for v in lobby['map_votes'].values() if v == vote)
                                for vote in set(lobby['map_votes'].values())}
            }, room=lobby_id)

            app.logger.debug(f"Map voting countdown: {countdown}, Votes: {lobby['map_votes']}")
            pause_aware_sleep(1)
            countdown -= 1
            lobby['voting_countdown'] = countdown

        if lobby.get('step') != 2 or lobby.get('skip_phase'):
            return
        if lobby.get('countdown_token') != countdown_token:
            return

        selected_map, vote_counts = select_map_from_votes(lobby)

        lobby['selected_map'] = selected_map
        lobby['server_details'] = lobby.get('server_details') or app.get_server_connection_details(
            server_id=lobby.get('server_id')
        )
        lobby['team_labels'] = app.get_selected_map_team_labels(
            selected_map,
            server_id=lobby.get('server_id')
        )
        lobby['server_details_provided_at'] = time.time()
        lobby['live_roll_ready_at'] = lobby['server_details_provided_at'] + app.LIVE_ROLL_READY_GRACE_SECONDS
        lobby['live_roll_countdown'] = app.LIVE_ROLL_READY_GRACE_SECONDS
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
        lobby['countdown'] = None
        lobby['voting_countdown'] = None
        lobby['vote_counts'] = vote_counts
        app.record_lobby_event(lobby_id, 'map_selected', {
            'selected_map': selected_map,
            'vote_counts': vote_counts,
            'server_details': lobby.get('server_details'),
            'team_labels': lobby.get('team_labels', {})
        }, created_at=lobby['server_details_provided_at'])

        app.socketio.emit('lobby_update', {
            'step': 3,
            'selected_map': selected_map,
            'lobby_id': lobby_id,
            'voting_countdown': None,
            'vote_counts': vote_counts,
            'server_details': lobby.get('server_details'),
            'team_labels': lobby.get('team_labels', {}),
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
        app.socketio.emit(app.SOCKET_EVENTS['LOBBY']['MAP_SELECTED'], {
            'lobby_id': lobby_id,
            'map': selected_map,
            'step': 3,
            'voting_countdown': None,
            'vote_counts': vote_counts,
            'server_details': lobby.get('server_details'),
            'team_labels': lobby.get('team_labels', {}),
            'queue_mode': lobby.get('queue_mode'),
            'queue_label': lobby.get('queue_label'),
            'match_size_label': lobby.get('match_size_label'),
            'max_players': lobby.get('max_players'),
            'map_pool': lobby.get('map_pool', [])
        }, room=lobby_id)

        app.logger.info(f"Map {selected_map} selected for lobby {lobby_id}")
        app.start_live_roll_monitor(lobby_id)
    except Exception as e:
        app.logger.error(f"Error in map voting countdown: {str(e)}")


def assign_teams(players):
    app = _app()
    if not players:
        return {'team1': [], 'team2': []}

    cap1 = len(players) // 2
    cap2 = len(players) - cap1
    team1 = []
    team2 = []
    group_map = {}
    solo_players = []

    for player in players:
        code = app.user_to_group.get(player)
        if code and code in app.groups:
            group_map.setdefault(code, []).append(player)
        else:
            solo_players.append(player)

    clusters = list(group_map.values()) + [[player] for player in solo_players]
    random.shuffle(clusters)

    for cluster in clusters:
        if len(team1) + len(cluster) <= cap1:
            team1.extend(cluster)
        elif len(team2) + len(cluster) <= cap2:
            team2.extend(cluster)
        else:
            if (cap1 - len(team1)) >= (cap2 - len(team2)):
                team1.extend(cluster)
            else:
                team2.extend(cluster)

    random.shuffle(team1)
    random.shuffle(team2)
    return {'team1': team1, 'team2': team2}


def select_captains(teams):
    return {'team1': None, 'team2': None}


def team_assignment_matches_queue_format(teams, queue_config):
    team_size = int((queue_config or {}).get('team_size') or 0)
    if team_size <= 0:
        return False
    return (
        len((teams or {}).get('team1') or []) == team_size
        and len((teams or {}).get('team2') or []) == team_size
    )


def create_lobby(players_override=None, queue_mode=None):
    app = _app()
    resolved_queue_mode = queue_mode
    if not resolved_queue_mode and players_override:
        sample_player = next(iter(players_override), None)
        resolved_queue_mode = find_user_queue_mode(app.matchmaking_queue, sample_player) or DEFAULT_QUEUE_MODE
    queue_config = get_queue_config(resolved_queue_mode)
    queue = get_queue_for_mode(app.matchmaking_queue, queue_config['id'])
    with app.queue_lock:
        players = list(players_override[:queue_config['max_players']]) if players_override else None
        if players is not None:
            if len(players) < queue_config['max_players']:
                return False
        elif len(queue) >= queue_config['max_players']:
            players = queue[:queue_config['max_players']]
        else:
            return False

    try:
        app.logger.debug(f"Creating lobby for players: {players}")
        app.logger.info(
            "create_lobby start: mode=%s players=%s queue_snapshot=%s pending_match=%s",
            queue_config['id'],
            players,
            list(queue),
            (app.pending_match.get(queue_config['id']) or {}).get('id')
        )
        teams = assign_teams(players)
        if not team_assignment_matches_queue_format(teams, queue_config):
            app.logger.warning(
                "Refusing to create lobby for mode=%s because team assignment is invalid: team1=%s team2=%s",
                queue_config['id'],
                teams.get('team1', []),
                teams.get('team2', [])
            )
            return False
        captains = select_captains(teams)
        map_pool = build_lobby_map_pool(queue_config)
        lobby_id = f"lobby_{int(time.time())}"
        allocated_server = app.allocate_server_for_lobby(lobby_id)
        lobby_data = {
            'lobby_id': lobby_id,
            'server_id': (allocated_server or {}).get('id'),
            'created_at': time.time(),
            'queue_mode': queue_config['id'],
            'queue_label': queue_config['label'],
            'match_size_label': f"{queue_config['team_size']}v{queue_config['team_size']}",
            'max_players': queue_config['max_players'],
            'players': players,
            'teams': teams,
            'captains': captains,
            'step': 2,
            'selected_map': None,
            'server_details': app.get_server_connection_details(server_id=(allocated_server or {}).get('id')),
            'team_labels': {},
            'countdown_active': False,
            'map_votes': {},
            'map_pool': map_pool,
            'voting_countdown': MAP_VOTE_COUNTDOWN,
            'countdown': None,
            'countdown_token': 0,
            'player_groups': get_player_groups(players),
            'announcement': None,
            'live_roll_done': False,
            'live_roll_token': 0,
            'live_roll_command_sent': False,
            'live_roll_next_layer_sent': False,
            'live_roll_change_attempts': 0,
            'live_roll_last_change_attempt_at': None,
            'live_roll_team_swap_attempts': {},
            'live_broadcast_sent': False,
            'live_broadcast_attempts': 0,
            'live_broadcast_last_attempt_at': None,
            'live_broadcast_ready_at': None,
            'live_broadcast_error': None,
            'round_result': None
        }

        app.lobbies[lobby_id] = lobby_data
        app.record_lobby_event(lobby_id, 'lobby_created', {
            'queue_mode': queue_config['id'],
            'server_id': lobby_data.get('server_id'),
            'players': players,
            'teams': teams,
            'player_groups': lobby_data.get('player_groups', {}),
            'map_pool': map_pool
        }, created_at=lobby_data['created_at'])
        with app.queue_lock:
            for player in players:
                if player in queue:
                    queue.remove(player)
                if player in app.player_activity:
                    upsert_player_activity(player, status='in_lobby', lobby_id=lobby_id)
            save_queue()

        broadcast_queue_update()

        for player in players:
            for sid in get_player_sids(player):
                try:
                    app.socketio.server.enter_room(sid, lobby_id)
                except Exception as join_error:
                    app.logger.debug(
                        f"Skipping stale SID {sid} while joining lobby {lobby_id} for {player}: {join_error}"
                    )

        app.logger.info(f"Created lobby {lobby_id} with players {players}")
        app.logger.info(
            "Lobby created successfully: lobby_id=%s players=%s team1=%s team2=%s",
            lobby_id,
            players,
            teams.get('team1', []),
            teams.get('team2', [])
        )
        for player in players:
            for sid in get_player_sids(player):
                try:
                    app.socketio.emit(app.SOCKET_EVENTS['LOBBY']['CREATED'], lobby_data, room=sid)
                except Exception as emit_error:
                    app.logger.debug(
                        f"Skipping stale SID {sid} while notifying lobby creation for {player}: {emit_error}"
                    )
            app.socketio.emit(app.SOCKET_EVENTS['LOBBY']['CREATED'], lobby_data, room=app.get_user_room(player))
            emit_active_lobby_sync(player, lobby_id)
        eventlet.spawn(start_map_voting, lobby_id)
        app.broadcast_open_lobbies_update()
        return lobby_id
    except Exception as e:
        app.logger.error(f"Error creating lobby: {str(e)}")
        if 'lobby_id' in locals() and lobby_id in app.lobbies:
            del app.lobbies[lobby_id]
        return False
