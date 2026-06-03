import json
import logging
import random
import time
from functools import wraps

import eventlet

from app_state import ALL_SKIRMISH_MAPS, MATCH_ACCEPT_COUNTDOWN, MAX_LOBBY_PLAYERS
from services.queue import (
    add_to_queue as add_to_queue_service,
    build_queue_payload as build_queue_payload_service,
    cancel_pending_match as cancel_pending_match_service,
    check_queue_and_start_countdown as check_queue_and_start_countdown_service,
    finalize_pending_match as finalize_pending_match_service,
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


def save_queue(queue=None):
    app = _app()
    try:
        queue_to_save = list(app.matchmaking_queue if queue is None else queue)
        with app.get_db_connection() as conn:
            conn.execute('DELETE FROM queue_entries')
            conn.executemany(
                'INSERT INTO queue_entries (position, username) VALUES (?, ?)',
                [(index, username) for index, username in enumerate(queue_to_save)]
            )
            conn.commit()
    except Exception as e:
        logging.getLogger(__name__).error(f"Failed to save queue to SQLite: {str(e)}")


def broadcast_queue_update(countdown=None):
    app = _app()
    try:
        app.logger.debug(f"Queue before broadcast: {list(app.matchmaking_queue)}")
        queue_status = build_queue_payload(username=None)
        if countdown is not None:
            queue_status['countdown'] = countdown
        app.socketio.emit(app.SOCKET_EVENTS['QUEUE']['UPDATE'], queue_status, room=None)
        app.logger.debug(f"Broadcasting queue update: {queue_status}")
    except Exception as e:
        app.logger.error(f"Error in broadcast_queue_update: {str(e)}")


def build_queue_payload(username=None, countdown=None):
    app = _app()
    return build_queue_payload_service(
        app.matchmaking_queue,
        app.user_has_steam_id,
        app.get_match_accept_payload,
        username=username,
        countdown=countdown
    )


def cancel_pending_match(reason='Match acceptance cancelled.', remove_players=None):
    app = _app()
    current_pending_match = app.pending_match
    app.logger.info(
        "Cancelling pending match: reason=%s current_pending=%s remove_players=%s",
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
        app.pending_match = None
        app.countdown_active = False
    return success


def finalize_pending_match(match_id):
    app = _app()
    current_pending_match = app.pending_match
    app.logger.info(
        "Finalizing pending match: match_id=%s current_pending=%s",
        match_id,
        current_pending_match.get('id') if current_pending_match else None
    )
    success = finalize_pending_match_service(
        current_pending_match,
        match_id,
        broadcast_queue_update,
        create_lobby
    )
    if success:
        app.pending_match = None
        app.logger.info("Pending match cleared: match_id=%s", match_id)
    return success


def start_match_acceptance(players):
    app = _app()
    current_pending_match = app.pending_match

    def finalize_wrapper(match_id):
        return finalize_pending_match(match_id)

    def cancel_wrapper(reason, remove_players=None):
        return cancel_pending_match(reason=reason, remove_players=remove_players)

    success, new_pending_match = start_match_acceptance_service(
        players=players,
        max_lobby_players=app.MAX_LOBBY_PLAYERS,
        match_accept_countdown=app.MATCH_ACCEPT_COUNTDOWN,
        pending_match=current_pending_match,
        set_pending_match=lambda state: setattr(app, 'pending_match', state),
        broadcast_queue_update=broadcast_queue_update,
        pause_aware_sleep=pause_aware_sleep,
        finalize_pending_match=finalize_wrapper,
        cancel_pending_match=cancel_wrapper
    )
    if success:
        app.pending_match = new_pending_match
        app.countdown_active = False
        app.logger.info(
            "Pending match stored: id=%s players=%s countdown=%s",
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
            max_lobby_players=app.MAX_LOBBY_PLAYERS,
            start_match_acceptance=start_match_acceptance
        )
    except Exception as e:
        app.logger.error(f"Error starting match acceptance: {e}")


def add_to_queue(username):
    app = _app()
    return add_to_queue_service(username, app.matchmaking_queue, upsert_player_activity, save_queue)


def start_map_voting(lobby_id):
    app = _app()
    try:
        countdown = 30
        lobby = app.lobbies.get(lobby_id)
        if not lobby:
            app.logger.error(f"Lobby {lobby_id} not found when starting map vote")
            return

        lobby['countdown_token'] = lobby.get('countdown_token', 0) + 1
        countdown_token = lobby['countdown_token']
        app.logger.info(f"Starting map voting countdown for lobby {lobby_id}")

        if 'map_votes' not in lobby:
            lobby['map_votes'] = {}

        if 'map_pool' not in lobby or not lobby['map_pool']:
            lobby['map_pool'] = random.sample(ALL_SKIRMISH_MAPS, k=min(5, len(ALL_SKIRMISH_MAPS)))

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

        vote_counts = {}
        if lobby['map_votes']:
            for username, map_choice in lobby['map_votes'].items():
                vote_counts[map_choice] = vote_counts.get(map_choice, 0) + 1
            max_votes = max(vote_counts.values())
            winning_maps = [map_name for map_name, votes in vote_counts.items() if votes == max_votes]
            selected_map = random.choice(winning_maps)
        else:
            fallback_pool = lobby.get('map_pool') or ALL_SKIRMISH_MAPS
            selected_map = random.choice(fallback_pool)

        lobby['selected_map'] = selected_map
        lobby['step'] = 3
        lobby['countdown'] = None
        lobby['voting_countdown'] = None
        lobby['vote_counts'] = vote_counts

        app.socketio.emit('lobby_update', {
            'step': 3,
            'selected_map': selected_map,
            'lobby_id': lobby_id,
            'voting_countdown': None,
            'vote_counts': vote_counts,
            'announcement': None
        }, room=lobby_id)
        app.socketio.emit(app.SOCKET_EVENTS['LOBBY']['MAP_SELECTED'], {
            'lobby_id': lobby_id,
            'map': selected_map,
            'step': 3,
            'voting_countdown': None,
            'vote_counts': vote_counts
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


def select_map_from_votes(lobby):
    if lobby.get('map_votes'):
        vote_counts = {}
        for username, map_choice in lobby['map_votes'].items():
            vote_counts[map_choice] = vote_counts.get(map_choice, 0) + 1
        max_votes = max(vote_counts.values())
        winning_maps = [map_name for map_name, votes in vote_counts.items() if votes == max_votes]
        selected_map = random.choice(winning_maps)
        return selected_map, vote_counts
    pool = lobby.get('map_pool') or ALL_SKIRMISH_MAPS
    return random.choice(pool), {}


def create_lobby(players_override=None):
    app = _app()
    with app.queue_lock:
        players = list(players_override[:app.MAX_LOBBY_PLAYERS]) if players_override else None
        if players is not None:
            if len(players) < app.MAX_LOBBY_PLAYERS:
                return False
        elif len(app.matchmaking_queue) >= app.MAX_LOBBY_PLAYERS:
            players = app.matchmaking_queue[:app.MAX_LOBBY_PLAYERS]
        else:
            return False

    try:
        app.logger.debug(f"Creating lobby for players: {players}")
        app.logger.info(
            "create_lobby start: players=%s queue_snapshot=%s pending_match=%s",
            players,
            list(app.matchmaking_queue),
            app.pending_match.get('id') if app.pending_match else None
        )
        teams = assign_teams(players)
        captains = select_captains(teams)
        map_pool = random.sample(ALL_SKIRMISH_MAPS, k=min(5, len(ALL_SKIRMISH_MAPS)))
        lobby_id = f"lobby_{int(time.time())}"
        lobby_data = {
            'lobby_id': lobby_id,
            'players': players,
            'teams': teams,
            'captains': captains,
            'step': 2,
            'selected_map': None,
            'server_details': None,
            'countdown_active': False,
            'map_votes': {},
            'map_pool': map_pool,
            'voting_countdown': 30,
            'countdown': None,
            'countdown_token': 0,
            'player_groups': get_player_groups(players),
            'announcement': None,
            'live_roll_done': False,
            'live_roll_token': 0
        }

        app.lobbies[lobby_id] = lobby_data
        with app.queue_lock:
            for player in players:
                if player in app.matchmaking_queue:
                    app.matchmaking_queue.remove(player)
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
        return True
    except Exception as e:
        app.logger.error(f"Error creating lobby: {str(e)}")
        if 'lobby_id' in locals() and lobby_id in app.lobbies:
            del app.lobbies[lobby_id]
        return False
