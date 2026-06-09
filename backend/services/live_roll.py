import logging
import math
import time

import eventlet

from services.bridge import BridgeUnavailable
from services.bridge import layer_matches_selected_map


def mark_live_roll_change_attempt(lobby, response=None, *, now=None):
    lobby['live_roll_command_sent'] = True
    lobby['live_roll_change_attempts'] = int(lobby.get('live_roll_change_attempts') or 0) + 1
    lobby['live_roll_last_change_attempt_at'] = time.time() if now is None else now
    if response is not None:
        lobby['live_roll_command_response'] = response


def get_live_broadcast_retry_state(lobby, *, retry_seconds, now=None):
    current_time = time.time() if now is None else now
    ready_at = lobby.get('live_broadcast_ready_at')
    last_attempt_at = lobby.get('live_broadcast_last_attempt_at')

    if lobby.get('live_broadcast_sent'):
        return {
            'shouldRetry': False,
            'remainingSeconds': 0,
            'attempts': int(lobby.get('live_broadcast_attempts') or 0)
        }

    if ready_at and current_time < ready_at:
        return {
            'shouldRetry': False,
            'remainingSeconds': int(math.ceil(ready_at - current_time)),
            'attempts': int(lobby.get('live_broadcast_attempts') or 0)
        }

    if not last_attempt_at:
        return {
            'shouldRetry': True,
            'remainingSeconds': 0,
            'attempts': int(lobby.get('live_broadcast_attempts') or 0)
        }

    elapsed_seconds = max(0, current_time - last_attempt_at)
    remaining_seconds = max(0, retry_seconds - elapsed_seconds)
    return {
        'shouldRetry': remaining_seconds <= 0,
        'remainingSeconds': int(remaining_seconds),
        'attempts': int(lobby.get('live_broadcast_attempts') or 0)
    }


def mark_live_broadcast_attempt(lobby, response=None, error=None, *, now=None):
    lobby['live_broadcast_attempts'] = int(lobby.get('live_broadcast_attempts') or 0) + 1
    lobby['live_broadcast_last_attempt_at'] = time.time() if now is None else now
    if response is not None:
        lobby['live_broadcast_response'] = response
        lobby['live_broadcast_error'] = None
        lobby['live_broadcast_sent'] = True
    if error is not None:
        lobby['live_broadcast_error'] = str(error)


def schedule_live_broadcast(lobby, *, delay_seconds=10, now=None):
    current_time = time.time() if now is None else now
    lobby['live_broadcast_ready_at'] = current_time + delay_seconds


def get_live_roll_readiness(lobby, presence, *, ready_ratio, ready_grace_seconds, now=None):
    players = presence.get('players') or []
    total_players = len(players)
    connected_count = len(presence.get('connected') or [])
    aligned_count = len(presence.get('aligned') or [])
    required_after_grace = int(total_players * ready_ratio)
    if total_players and required_after_grace < total_players * ready_ratio:
        required_after_grace += 1

    current_time = time.time() if now is None else now
    details_provided_at = lobby.get('server_details_provided_at') or current_time
    elapsed_seconds = max(0, current_time - details_provided_at)
    all_connected = total_players > 0 and aligned_count >= total_players
    grace_ready = (
        total_players > 0
        and aligned_count >= required_after_grace
        and elapsed_seconds >= ready_grace_seconds
    )

    return {
        'ready': all_connected or grace_ready,
        'allConnected': all_connected,
        'graceReady': grace_ready,
        'connectedCount': connected_count,
        'alignedCount': aligned_count,
        'totalPlayers': total_players,
        'requiredAfterGrace': required_after_grace,
        'elapsedSeconds': elapsed_seconds,
        'remainingGraceSeconds': max(0, ready_grace_seconds - elapsed_seconds)
    }


def get_live_roll_retry_state(lobby, *, retry_seconds, now=None):
    current_time = time.time() if now is None else now
    last_attempt_at = lobby.get('live_roll_last_change_attempt_at')

    if not last_attempt_at:
        return {
            'shouldRetry': True,
            'remainingSeconds': 0,
            'attempts': int(lobby.get('live_roll_change_attempts') or 0)
        }

    elapsed_seconds = max(0, current_time - last_attempt_at)
    remaining_seconds = max(0, retry_seconds - elapsed_seconds)
    return {
        'shouldRetry': remaining_seconds <= 0,
        'remainingSeconds': int(remaining_seconds),
        'attempts': int(lobby.get('live_roll_change_attempts') or 0)
    }


def get_team_swap_retry_state(lobby, username, *, retry_seconds, now=None):
    current_time = time.time() if now is None else now
    attempts = lobby.setdefault('live_roll_team_swap_attempts', {})
    last_attempt_at = attempts.get(username)
    if not last_attempt_at:
        return {
            'shouldRetry': True,
            'remainingSeconds': 0
        }

    elapsed_seconds = max(0, current_time - last_attempt_at)
    remaining_seconds = max(0, retry_seconds - elapsed_seconds)
    return {
        'shouldRetry': remaining_seconds <= 0,
        'remainingSeconds': int(remaining_seconds)
    }


def mark_team_swap_attempt(lobby, username, *, now=None):
    attempts = lobby.setdefault('live_roll_team_swap_attempts', {})
    attempts[username] = time.time() if now is None else now


def should_team_swap_block_live_roll(lobby):
    return bool(
        not lobby.get('live_roll_command_sent')
        and not lobby.get('live_roll_done')
    )


def try_broadcast_live_message(
    lobby,
    broadcast_server_message,
    *,
    logger=None,
    lobby_id='',
    retry_seconds=5
):
    retry_state = get_live_broadcast_retry_state(lobby, retry_seconds=retry_seconds)
    if not retry_state.get('shouldRetry'):
        return lobby.get('live_broadcast_sent'), lobby.get('live_broadcast_error')

    try:
        response = broadcast_server_message('Live')
        mark_live_broadcast_attempt(lobby, response=response)
        if logger:
            logger.info(f"Broadcasted Live message for lobby {lobby_id}: {response}")
        return True, None
    except Exception as broadcast_error:
        mark_live_broadcast_attempt(lobby, error=broadcast_error)
        if logger:
            logger.warning(
                f"Failed to broadcast Live message for lobby {lobby_id}: "
                f"{broadcast_error}"
            )
        return False, str(broadcast_error)


def get_round_result_layer(round_side):
    if isinstance(round_side, dict):
        return round_side.get('layer')
    return None


def round_result_has_layer_data(round_result):
    if not round_result:
        return False
    return bool(
        get_round_result_layer(round_result.get('winner'))
        or get_round_result_layer(round_result.get('loser'))
        or round_result.get('layer')
    )


def round_result_matches_selected_map(round_result, selected_map):
    if not round_result or not selected_map:
        return False
    return (
        layer_matches_selected_map(get_round_result_layer(round_result.get('winner')), selected_map)
        or layer_matches_selected_map(get_round_result_layer(round_result.get('loser')), selected_map)
        or layer_matches_selected_map(round_result.get('layer'), selected_map)
    )


def should_finalize_live_lobby(current_lobby, round_result, selected_map):
    return bool(
        round_result
        and round_result.get('observedAt')
        and round_result.get('observedAt') >= current_lobby.get('live_started_at', 0)
        and (
            round_result_matches_selected_map(round_result, selected_map)
            or not round_result_has_layer_data(round_result)
        )
    )


def summarize_round_result(round_result):
    if not round_result:
        return {}

    winner = round_result.get('winner') if isinstance(round_result.get('winner'), dict) else {}
    loser = round_result.get('loser') if isinstance(round_result.get('loser'), dict) else {}

    return {
        'observedAt': round_result.get('observedAt'),
        'time': round_result.get('time'),
        'layer': round_result.get('layer') or winner.get('layer') or loser.get('layer'),
        'winner': {
            'team': winner.get('team'),
            'faction': winner.get('faction') or winner.get('winner'),
            'tickets': winner.get('tickets'),
            'inferred': bool(winner.get('inferred'))
        } if winner else None,
        'loser': {
            'team': loser.get('team'),
            'faction': loser.get('faction') or loser.get('winner'),
            'tickets': loser.get('tickets'),
            'inferred': bool(loser.get('inferred'))
        } if loser else None,
        'partial': bool(round_result.get('partial'))
    }


def start_live_roll_monitor(
    lobby_id,
    lobbies,
    socketio,
    build_lobby_server_presence,
    pause_aware_sleep,
    broadcast_server_message,
    change_server_to_selected_map,
    set_next_server_map,
    force_player_to_expected_team,
    get_server_layer_status,
    get_server_connection_details,
    fetch_latest_round_result,
    record_lobby_event,
    save_completed_match,
    ready_ratio=0.9,
    ready_grace_seconds=600,
    poll_seconds=5,
    retry_seconds=15,
    team_swap_retry_seconds=10,
    live_broadcast_delay_seconds=10,
    dev_mode=False,
    dev_override_username='',
    logger=None
):
    current_logger = logger or logging.getLogger(__name__)
    lobby = lobbies.get(lobby_id)
    if not lobby:
        return

    lobby['live_roll_token'] = lobby.get('live_roll_token', 0) + 1
    token = lobby['live_roll_token']
    lobby.setdefault('live_roll_command_sent', False)
    lobby.setdefault('live_roll_next_layer_sent', False)
    lobby.setdefault('live_roll_change_attempts', 0)
    lobby.setdefault('live_roll_last_change_attempt_at', None)
    lobby.setdefault('live_roll_team_swap_attempts', {})
    lobby.setdefault('live_broadcast_sent', False)
    lobby.setdefault('live_broadcast_attempts', 0)
    lobby.setdefault('live_broadcast_last_attempt_at', None)
    lobby.setdefault('live_broadcast_ready_at', None)
    lobby.setdefault('live_broadcast_error', None)
    lobby.setdefault('round_result', None)

    def record_event(event_type, payload=None):
        try:
            record_lobby_event(lobby_id, event_type, payload, created_at=time.time())
        except Exception as event_error:
            current_logger.warning(f"Failed to record lobby event {event_type} for {lobby_id}: {event_error}")

    def monitor():
        while True:
            current_lobby = lobbies.get(lobby_id)
            if not current_lobby:
                return
            if current_lobby.get('live_roll_token') != token:
                return
            if current_lobby.get('step') not in (3, 4):
                return
            if current_lobby.get('step') == 5:
                return
            if current_lobby.get('live_roll_done'):
                round_result = current_lobby.get('round_result')
                if round_result:
                    return
            if not current_lobby.get('selected_map'):
                return

            try:
                presence = build_lobby_server_presence(lobby_id)
            except BridgeUnavailable:
                waiting_message = 'Waiting for SquadJS bridge to become available.'
                if current_lobby.get('announcement') != waiting_message:
                    current_lobby['announcement'] = waiting_message
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': waiting_message
                    }, room=lobby_id)
                pause_aware_sleep(poll_seconds)
                continue
            except Exception as e:
                current_logger.error(f"Error checking server presence for lobby {lobby_id}: {str(e)}")
                pause_aware_sleep(poll_seconds)
                continue

            readiness = get_live_roll_readiness(
                current_lobby,
                presence,
                ready_ratio=ready_ratio,
                ready_grace_seconds=ready_grace_seconds
            )
            current_lobby['live_roll_countdown'] = int(readiness['remainingGraceSeconds'])
            connected_usernames = set(presence.get('connected', []))
            normalized_connected = {
                str(connected_username or '').strip().lower()
                for connected_username in connected_usernames
            }
            dev_ready_override = (
                dev_mode
                and dev_override_username
                and dev_override_username.strip().lower() in normalized_connected
            )

            mismatched_players = [
                row for row in (presence.get('players') or [])
                if row.get('connected') and not row.get('teamAligned')
            ]
            waiting_for_initial_live_roll = (
                should_team_swap_block_live_roll(current_lobby)
            )
            swapped_players = []
            for row in mismatched_players:
                username = row.get('username')
                steam_id = row.get('steam_id')
                retry_state = get_team_swap_retry_state(
                    current_lobby,
                    username,
                    retry_seconds=team_swap_retry_seconds
                )
                if not retry_state.get('shouldRetry'):
                    continue
                force_player_to_expected_team(steam_id)
                mark_team_swap_attempt(current_lobby, username)
                swapped_players.append(username)

            if swapped_players:
                record_event('team_swap_requested', {
                    'players': swapped_players
                })
                if waiting_for_initial_live_roll:
                    swap_message = (
                        f"Correcting team assignment for {', '.join(swapped_players)}. "
                        f"Waiting for the server roster to refresh."
                    )
                    if current_lobby.get('announcement') != swap_message:
                        current_lobby['announcement'] = swap_message
                        socketio.emit('lobby_update', {
                            'lobby_id': lobby_id,
                            'announcement': swap_message,
                            'live_roll_ready_at': current_lobby.get('live_roll_ready_at'),
                            'live_roll_countdown': current_lobby.get('live_roll_countdown')
                        }, room=lobby_id)
                    pause_aware_sleep(2)
                    continue

            if waiting_for_initial_live_roll and not readiness['ready'] and not dev_ready_override:
                waiting_message = (
                    f"Waiting for players: {readiness['alignedCount']}/"
                    f"{readiness['totalPlayers']} on the correct team "
                    f"({readiness['connectedCount']} connected). "
                    f"Live rolls at {readiness['requiredAfterGrace']}/"
                    f"{readiness['totalPlayers']} after "
                    f"{int(readiness['remainingGraceSeconds'])}s, or immediately at 100%."
                )
                if current_lobby.get('announcement') != waiting_message:
                    current_lobby['announcement'] = waiting_message
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': waiting_message,
                        'live_roll_ready_at': current_lobby.get('live_roll_ready_at'),
                        'live_roll_countdown': current_lobby.get('live_roll_countdown')
                    }, room=lobby_id)
                pause_aware_sleep(poll_seconds)
                continue

            try:
                selected_map = current_lobby.get('selected_map')
                round_result = fetch_latest_round_result()

                if current_lobby.get('live_roll_done') and should_finalize_live_lobby(
                    current_lobby,
                    round_result,
                    selected_map
                ):
                    round_result_summary = summarize_round_result(round_result)
                    current_logger.info(
                        f"Finalizing lobby {lobby_id} from live round result: {round_result_summary}"
                    )
                    current_lobby['round_result'] = round_result
                    current_lobby['announcement'] = 'Match finalised'
                    current_lobby['step'] = 5
                    current_lobby['server_details'] = {
                        **(current_lobby.get('server_details') or {}),
                        'roundResult': round_result
                    }
                    record_event('match_finalized', {
                        'selected_map': selected_map,
                        'round_result': round_result,
                        'round_result_summary': round_result_summary
                    })
                    save_completed_match(lobby_id, current_lobby, completed_at=time.time())
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': current_lobby['announcement'],
                        'server_details': current_lobby['server_details'],
                        'step': 5
                    }, room=lobby_id)
                    return

                if not current_lobby.get('live_roll_command_sent'):
                    announcement = f'Rolling to live on {selected_map}'
                    current_lobby['announcement'] = announcement
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': announcement
                    }, room=lobby_id)
                    broadcast_server_message(announcement)
                    mark_live_roll_change_attempt(
                        current_lobby,
                        change_server_to_selected_map(selected_map)
                    )
                    record_event('live_roll_attempted', {
                        'selected_map': selected_map,
                        'attempts': current_lobby.get('live_roll_change_attempts'),
                        'response': current_lobby.get('live_roll_command_response')
                    })
                    pause_aware_sleep(2)
                    continue

                layer_status = get_server_layer_status(selected_map)
                retry_state = get_live_roll_retry_state(
                    current_lobby,
                    retry_seconds=retry_seconds
                )

                if layer_status.get('currentMatches'):
                    if current_lobby.get('live_roll_done'):
                        was_live_broadcast_sent = bool(current_lobby.get('live_broadcast_sent'))
                        try_broadcast_live_message(
                            current_lobby,
                            broadcast_server_message,
                            logger=current_logger,
                            lobby_id=lobby_id
                        )
                        if current_lobby.get('live_broadcast_sent') and not was_live_broadcast_sent:
                            current_lobby['server_details'] = {
                                **(current_lobby.get('server_details') or {}),
                                'liveBroadcastResponse': current_lobby.get('live_broadcast_response'),
                                'liveBroadcastError': current_lobby.get('live_broadcast_error')
                            }
                            record_event('live_broadcast_sent', {
                                'response': current_lobby.get('live_broadcast_response')
                            })
                            socketio.emit('lobby_update', {
                                'lobby_id': lobby_id,
                                'announcement': 'Live',
                                'server_details': current_lobby.get('server_details'),
                                'live_roll_ready_at': current_lobby.get('live_roll_ready_at'),
                                'live_roll_countdown': 0,
                                'step': 4
                            }, room=lobby_id)
                        if current_lobby.get('step') == 4 and current_lobby.get('announcement') != 'Live':
                            current_lobby['announcement'] = 'Live'
                            socketio.emit('lobby_update', {
                                'lobby_id': lobby_id,
                                'announcement': 'Live',
                                'live_roll_ready_at': current_lobby.get('live_roll_ready_at'),
                                'live_roll_countdown': 0,
                                'step': 4
                            }, room=lobby_id)
                    else:
                        live_announcement = 'Live'
                        live_started_at = time.time()
                        schedule_live_broadcast(
                            current_lobby,
                            delay_seconds=live_broadcast_delay_seconds,
                            now=live_started_at
                        )
                        live_broadcast_error = current_lobby.get('live_broadcast_error')
                        server_details = get_server_connection_details()
                        current_lobby['live_roll_done'] = True
                        current_lobby['live_started_at'] = live_started_at
                        current_lobby['announcement'] = live_announcement
                        current_lobby['server_details'] = {
                            **server_details,
                            'map': selected_map,
                            'bridge_response': current_lobby.get('live_roll_command_response'),
                            'layerStatus': layer_status,
                            'liveBroadcastReadyAt': current_lobby.get('live_broadcast_ready_at'),
                            'liveBroadcastResponse': current_lobby.get('live_broadcast_response'),
                            'liveBroadcastError': current_lobby.get('live_broadcast_error')
                        }
                        current_lobby['step'] = 4
                        record_event('live_started', {
                            'selected_map': selected_map,
                            'server_details': current_lobby['server_details'],
                            'broadcast_error': live_broadcast_error
                        })
                        socketio.emit('lobby_update', {
                            'lobby_id': lobby_id,
                            'announcement': live_announcement,
                            'selected_map': selected_map,
                            'server_details': current_lobby['server_details'],
                            'live_roll_ready_at': current_lobby.get('live_roll_ready_at'),
                            'live_roll_countdown': 0,
                            'step': 4
                        }, room=lobby_id)

                    if should_finalize_live_lobby(current_lobby, round_result, selected_map):
                        round_result_summary = summarize_round_result(round_result)
                        current_logger.info(
                            f"Finalizing live lobby {lobby_id} after layer confirmation with round result: "
                            f"{round_result_summary}"
                        )
                        current_lobby['round_result'] = round_result
                        current_lobby['announcement'] = 'Match finalised'
                        current_lobby['step'] = 5
                        current_lobby['server_details'] = {
                            **(current_lobby.get('server_details') or {}),
                            'roundResult': round_result
                        }
                        record_event('match_finalized', {
                            'selected_map': selected_map,
                            'round_result': round_result,
                            'round_result_summary': round_result_summary
                        })
                        save_completed_match(lobby_id, current_lobby, completed_at=time.time())
                        socketio.emit('lobby_update', {
                            'lobby_id': lobby_id,
                            'announcement': current_lobby['announcement'],
                            'server_details': current_lobby['server_details'],
                            'step': 5
                        }, room=lobby_id)
                        return

                    pause_aware_sleep(poll_seconds)
                    continue

                if layer_status.get('nextMatches'):
                    if retry_state.get('shouldRetry'):
                        retry_message = (
                            f'{selected_map} is still queued as the next round. '
                            f'Retrying immediate roll now.'
                        )
                        if current_lobby.get('announcement') != retry_message:
                            current_lobby['announcement'] = retry_message
                            socketio.emit('lobby_update', {
                                'lobby_id': lobby_id,
                                'announcement': retry_message
                            }, room=lobby_id)
                        mark_live_roll_change_attempt(
                            current_lobby,
                            change_server_to_selected_map(selected_map)
                        )
                        record_event('live_roll_retry_attempted', {
                            'selected_map': selected_map,
                            'attempts': current_lobby.get('live_roll_change_attempts'),
                            'response': current_lobby.get('live_roll_command_response')
                        })
                        pause_aware_sleep(2)
                        continue

                    queued_message = f'{selected_map} is queued as the next round. Waiting for the server to transition.'
                    if current_lobby.get('announcement') != queued_message:
                        current_lobby['announcement'] = queued_message
                        socketio.emit('lobby_update', {
                            'lobby_id': lobby_id,
                            'announcement': queued_message
                    }, room=lobby_id)
                    pause_aware_sleep(poll_seconds)
                    continue

                if not current_lobby.get('live_roll_next_layer_sent'):
                    current_lobby['live_roll_next_layer_response'] = set_next_server_map(selected_map)
                    current_lobby['live_roll_next_layer_sent'] = True
                    record_event('live_roll_queued_next_round', {
                        'selected_map': selected_map,
                        'response': current_lobby.get('live_roll_next_layer_response')
                    })
                    queued_message = f'Immediate roll not confirmed. {selected_map} has been queued as the next round.'
                    current_lobby['announcement'] = queued_message
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': queued_message
                    }, room=lobby_id)
                    pause_aware_sleep(poll_seconds)
                    continue

                if retry_state.get('shouldRetry'):
                    retry_message = f'Waiting for the server to move onto {selected_map}. Retrying immediate roll now.'
                    if current_lobby.get('announcement') != retry_message:
                        current_lobby['announcement'] = retry_message
                        socketio.emit('lobby_update', {
                            'lobby_id': lobby_id,
                            'announcement': retry_message
                        }, room=lobby_id)
                    mark_live_roll_change_attempt(
                        current_lobby,
                        change_server_to_selected_map(selected_map)
                    )
                    record_event('live_roll_retry_attempted', {
                        'selected_map': selected_map,
                        'attempts': current_lobby.get('live_roll_change_attempts'),
                        'response': current_lobby.get('live_roll_command_response')
                    })
                    pause_aware_sleep(2)
                    continue

                waiting_message = f'Waiting for the server to move onto {selected_map}.'
                if current_lobby.get('announcement') != waiting_message:
                    current_lobby['announcement'] = waiting_message
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': waiting_message
                    }, room=lobby_id)
                pause_aware_sleep(poll_seconds)
                continue
            except BridgeUnavailable:
                waiting_message = 'Waiting for SquadJS bridge to become available.'
                current_lobby['announcement'] = waiting_message
                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'announcement': waiting_message
                }, room=lobby_id)
                pause_aware_sleep(poll_seconds)
                continue
            except Exception as e:
                error_message = f'Failed to roll server live on "{selected_map}": {str(e)}'
                current_lobby['announcement'] = error_message
                current_logger.error(error_message)
                record_event('live_roll_failed', {
                    'selected_map': selected_map,
                    'error': str(e)
                })
                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'announcement': error_message
                }, room=lobby_id)
                return

    eventlet.spawn(monitor)
