import logging
import math
import time
from datetime import datetime, timezone

import eventlet

from services.bridge import BridgeUnavailable
from services.bridge import layer_matches_selected_map


def mark_live_roll_change_attempt(lobby, response=None, error=None, *, now=None):
    lobby['live_roll_change_attempts'] = int(lobby.get('live_roll_change_attempts') or 0) + 1
    lobby['live_roll_last_change_attempt_at'] = time.time() if now is None else now
    if response is not None:
        lobby['live_roll_command_sent'] = True
        lobby['live_roll_command_response'] = response
        lobby['live_roll_command_error'] = None
    if error is not None:
        lobby['live_roll_command_error'] = str(error)


def mark_live_roll_broadcast_attempt(lobby, response=None, error=None, *, now=None):
    lobby['live_roll_broadcast_attempts'] = int(lobby.get('live_roll_broadcast_attempts') or 0) + 1
    lobby['live_roll_broadcast_last_attempt_at'] = time.time() if now is None else now
    if response is not None:
        lobby['live_roll_broadcast_sent'] = True
        lobby['live_roll_broadcast_response'] = response
        lobby['live_roll_broadcast_error'] = None
    if error is not None:
        lobby['live_roll_broadcast_error'] = str(error)


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


def parse_server_match_start_time(value):
    text = str(value or '').strip()
    if not text:
        return None
    if text.endswith('Z'):
        text = f'{text[:-1]}+00:00'
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def get_server_playtime_seconds(layer_status):
    server_info = (layer_status or {}).get('serverInfo') or {}
    if server_info.get('playtimeSeconds') is None:
        return None
    try:
        elapsed_seconds = int(float(server_info.get('playtimeSeconds')))
    except (TypeError, ValueError):
        return None
    return elapsed_seconds if elapsed_seconds >= 0 else None


def get_server_match_started_at(layer_status, *, now=None):
    server_info = (layer_status or {}).get('serverInfo') or {}
    started_at = parse_server_match_start_time(server_info.get('matchStartTime'))
    if started_at is not None:
        return started_at

    playtime_seconds = get_server_playtime_seconds(layer_status)
    if playtime_seconds is None:
        return None

    current_time = time.time() if now is None else now
    return current_time - playtime_seconds


def has_selected_layer_started_after_roll(lobby, layer_status, *, now=None, tolerance_seconds=5):
    if not (layer_status or {}).get('currentMatches'):
        return False

    command_sent_at = float(lobby.get('live_roll_last_change_attempt_at') or 0)
    started_at = get_server_match_started_at(layer_status, now=now)
    if not command_sent_at or started_at is None:
        return True
    return started_at >= command_sent_at - tolerance_seconds


def get_live_started_at_from_layer_status(layer_status, *, now=None):
    current_time = time.time() if now is None else now
    return get_server_match_started_at(layer_status, now=current_time) or current_time


def get_live_roll_readiness(
    lobby,
    presence,
    *,
    ready_ratio,
    threshold_grace_seconds=300,
    ready_grace_seconds=600,
    ratio_ready_enabled=True,
    force_requires_aligned=True,
    now=None
):
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
    connected_players_aligned = connected_count == aligned_count
    threshold_ready = elapsed_seconds >= threshold_grace_seconds
    force_ready = elapsed_seconds >= ready_grace_seconds
    grace_ready = (
        ratio_ready_enabled
        and
        total_players > 0
        and aligned_count >= required_after_grace
        and threshold_ready
        and connected_players_aligned
    )
    force_ready_allowed = force_ready and (
        connected_players_aligned if force_requires_aligned else True
    )

    return {
        'ready': all_connected or grace_ready or force_ready_allowed,
        'allConnected': all_connected,
        'connectedPlayersAligned': connected_players_aligned,
        'graceReady': grace_ready,
        'thresholdReady': threshold_ready,
        'forceReady': force_ready,
        'forceReadyAllowed': force_ready_allowed,
        'ratioReadyEnabled': ratio_ready_enabled,
        'forceRequiresAligned': force_requires_aligned,
        'connectedCount': connected_count,
        'alignedCount': aligned_count,
        'totalPlayers': total_players,
        'requiredAfterGrace': required_after_grace,
        'elapsedSeconds': elapsed_seconds,
        'remainingThresholdSeconds': max(0, threshold_grace_seconds - elapsed_seconds),
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


def has_live_roll_ready_override(
    *,
    enabled,
    connected_usernames=None,
    connected_steam_ids=None,
    override_username='',
    override_steam_id=''
):
    if not enabled:
        return False

    normalized_connected = {
        str(username or '').strip().lower()
        for username in (connected_usernames or [])
    }
    normalized_steam_ids = {
        str(steam_id or '').strip()
        for steam_id in (connected_steam_ids or [])
    }

    return bool(
        (
            override_username
            and override_username.strip().lower() in normalized_connected
        )
        or (
            override_steam_id
            and override_steam_id.strip() in normalized_steam_ids
        )
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
    observed_at = round_result.get('observedAt') if round_result else None
    result_started_after = (
        current_lobby.get('server_details_provided_at')
        or current_lobby.get('live_started_at')
        or 0
    )
    return bool(
        round_result
        and observed_at
        and observed_at >= result_started_after
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
        'partial': bool(round_result.get('partial')),
        'roundAudit': {
            'eventCount': len((round_result.get('roundAudit') or {}).get('events') or []),
            'emittedBy': (round_result.get('roundAudit') or {}).get('emittedBy'),
            'completeAtEmit': (round_result.get('roundAudit') or {}).get('completeAtEmit')
        } if round_result.get('roundAudit') else None
    }


def get_round_duration_seconds(lobby, round_result):
    live_started_at = float(lobby.get('live_started_at') or 0)
    round_ended_at = float(
        (round_result or {}).get('observedAt')
        or (round_result or {}).get('capturedAt')
        or 0
    )
    if not live_started_at or not round_ended_at or round_ended_at < live_started_at:
        return None
    return int(round_ended_at - live_started_at)


def is_skirmish_layer(selected_map):
    return 'skirmish' in str(selected_map or '').lower()


def should_end_live_match(lobby, *, max_seconds, now=None):
    return False


def get_live_match_timer_status(lobby, *, max_seconds, layer_status=None, now=None):
    elapsed_seconds = None
    if (layer_status or {}).get('currentMatches'):
        elapsed_seconds = get_server_playtime_seconds(layer_status)
    return {
        'shouldEnd': False,
        'elapsedSeconds': elapsed_seconds,
        'remainingSeconds': None,
        'source': 'server_playtime' if elapsed_seconds is not None else None
    }


def has_live_layer_transitioned_away(lobby, layer_status):
    if not lobby.get('live_roll_done') or not layer_status:
        return False
    if layer_status.get('currentMatches'):
        return False
    return bool(
        layer_status.get('currentLayer')
        or layer_status.get('currentLayerInfo')
        or (layer_status.get('serverInfo') or {}).get('currentLayer')
    )


def build_unresolved_round_result(lobby, selected_map, *, source, now=None):
    observed_at = time.time() if now is None else now
    return {
        'observedAt': observed_at,
        'capturedAt': observed_at,
        'time': time.strftime('%Y.%m.%d-%H.%M.%S', time.gmtime(observed_at)),
        'source': source,
        'resultQuality': 'draw_or_unresolved',
        'draw': True,
        'unresolved': True,
        'partial': True,
        'winner': None,
        'loser': None,
        'layer': selected_map,
        'teams': []
    }


def get_unauthorized_connected_players(presence):
    return [
        player
        for player in (presence or {}).get('unauthorizedPlayers') or []
        if player.get('eosID') or player.get('steam_id')
    ]


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
    kick_player_from_server=None,
    release_server_allocation=None,
    broadcast_open_lobbies_update=None,
    broadcast_queue_update=None,
    end_server_match=None,
    player_activity=None,
    get_player_sids=None,
    emit_active_lobby_sync=None,
    ready_ratio=0.9,
    threshold_grace_seconds=300,
    ready_grace_seconds=600,
    poll_seconds=5,
    retry_seconds=15,
    team_swap_retry_seconds=10,
    live_broadcast_delay_seconds=10,
    pre_live_roll_broadcast_delay_seconds=3,
    finalized_cleanup_delay_seconds=60,
    live_match_max_seconds=3600,
    automation_mode_provider=None,
    save_runtime_state=None,
    dev_mode=False,
    ready_override_enabled=False,
    dev_override_username='',
    dev_override_steam_id='',
    logger=None
):
    current_logger = logger or logging.getLogger(__name__)
    lobby = lobbies.get(lobby_id)
    if not lobby:
        return

    def get_effective_live_roll_readiness_settings(current_lobby):
        is_s3o_small = str(current_lobby.get('queue_mode') or '').strip().lower().startswith('s3osmall')
        if is_s3o_small:
            return {
                'ready_ratio': 1.0,
                'threshold_grace_seconds': ready_grace_seconds,
                'ready_grace_seconds': 300,
                'ratio_ready_enabled': False,
                'force_requires_aligned': False,
                'mode': 's3o_small_force_only'
            }
        return {
            'ready_ratio': ready_ratio,
            'threshold_grace_seconds': threshold_grace_seconds,
            'ready_grace_seconds': ready_grace_seconds,
            'ratio_ready_enabled': True,
            'force_requires_aligned': True,
            'mode': 'standard'
        }

    lobby['live_roll_token'] = lobby.get('live_roll_token', 0) + 1
    token = lobby['live_roll_token']
    lobby.setdefault('live_roll_command_sent', False)
    lobby.setdefault('live_roll_next_layer_sent', False)
    lobby.setdefault('live_roll_change_attempts', 0)
    lobby.setdefault('live_roll_last_change_attempt_at', None)
    lobby.setdefault('live_roll_broadcast_sent', False)
    lobby.setdefault('live_roll_broadcast_attempts', 0)
    lobby.setdefault('live_roll_broadcast_last_attempt_at', None)
    lobby.setdefault('live_roll_broadcast_error', None)
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
        try:
            if save_runtime_state:
                save_runtime_state()
        except Exception as save_error:
            current_logger.warning(f"Failed to save runtime state after {event_type} for {lobby_id}: {save_error}")

    def emit_announcement(current_lobby, announcement):
        if current_lobby.get('announcement') == announcement:
            return
        current_lobby['announcement'] = announcement
        socketio.emit('lobby_update', {
            'lobby_id': lobby_id,
            'announcement': announcement
        }, room=lobby_id)

    def log_live_roll_state(message, current_lobby, presence=None, readiness=None, **extra):
        presence = presence or {}
        readiness = readiness or {}
        current_logger.info(
            'Live roll state: lobby_id=%s %s step=%s selected_map=%s override=%s command_sent=%s live_done=%s connected=%s aligned=%s total=%s ready=%s writes_enabled=%s extra=%s',
            lobby_id,
            message,
            current_lobby.get('step'),
            current_lobby.get('selected_map'),
            bool(current_lobby.get('live_roll_admin_ready_override')),
            bool(current_lobby.get('live_roll_command_sent')),
            bool(current_lobby.get('live_roll_done')),
            readiness.get('connectedCount'),
            readiness.get('alignedCount'),
            readiness.get('totalPlayers') or len(current_lobby.get('players') or []),
            readiness.get('ready'),
            extra.pop('automation_writes_enabled', None),
            extra
        )

    def attempt_live_roll_change(current_lobby, selected_map, event_type):
        try:
            current_logger.info(
                'Live roll command attempt: lobby_id=%s selected_map=%s attempts_before=%s',
                lobby_id,
                selected_map,
                current_lobby.get('live_roll_change_attempts', 0)
            )
            response = change_server_to_selected_map(selected_map)
            mark_live_roll_change_attempt(current_lobby, response=response)
            record_event(event_type, {
                'selected_map': selected_map,
                'attempts': current_lobby.get('live_roll_change_attempts'),
                'response': current_lobby.get('live_roll_command_response')
            })
            current_logger.info(
                'Live roll command succeeded: lobby_id=%s selected_map=%s attempts=%s response=%s',
                lobby_id,
                selected_map,
                current_lobby.get('live_roll_change_attempts'),
                current_lobby.get('live_roll_command_response')
            )
            return True
        except BridgeUnavailable:
            raise
        except Exception as change_error:
            mark_live_roll_change_attempt(current_lobby, error=change_error)
            error_text = str(change_error)
            record_event(f'{event_type}_failed', {
                'selected_map': selected_map,
                'attempts': current_lobby.get('live_roll_change_attempts'),
                'error': error_text
            })
            current_logger.warning(
                f"Live roll attempt {current_lobby.get('live_roll_change_attempts')} "
                f"for lobby {lobby_id} failed on {selected_map}: {error_text}"
            )
            emit_announcement(
                current_lobby,
                f'Could not roll server live on {selected_map}: {error_text}. Retrying automatically.'
            )
            return False

    def release_finalized_server(current_lobby, reason='match_completed'):
        if not release_server_allocation or current_lobby.get('server_released_at'):
            return
        try:
            release_server_allocation(lobby_id, reason=reason)
            current_lobby['server_released_at'] = time.time()
            record_event('server_released', {
                'server_id': current_lobby.get('server_id'),
                'reason': reason
            })
        except Exception as release_error:
            current_logger.warning(f"Failed to release server for lobby {lobby_id}: {release_error}")
            record_event('server_release_failed', {
                'server_id': current_lobby.get('server_id'),
                'reason': reason,
                'error': str(release_error)
            })

    def cleanup_finalized_lobby(finalized_lobby):
        pause_aware_sleep(finalized_cleanup_delay_seconds)
        current_lobby = lobbies.get(lobby_id)
        if not current_lobby or current_lobby.get('step') != 5:
            return

        kicked_players = []
        kick_errors = []
        try:
            presence = build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=True)
            for row in presence.get('players') or []:
                if not row.get('connected'):
                    continue
                player_id = row.get('eosID') or row.get('steam_id')
                if not player_id:
                    continue
                if not kick_player_from_server:
                    continue
                try:
                    kick_player_from_server(player_id, reason='Match complete.', lobby_id=lobby_id)
                    kicked_players.append({
                        'username': row.get('username'),
                        'player_id': player_id
                    })
                except Exception as kick_error:
                    kick_errors.append({
                        'username': row.get('username'),
                        'player_id': player_id,
                        'error': str(kick_error)
                    })
                    current_logger.warning(
                        f"Failed to kick {row.get('username')} after lobby {lobby_id} finalized: {kick_error}"
                    )
        except Exception as presence_error:
            kick_errors.append({'error': str(presence_error)})
            current_logger.warning(f"Failed to build cleanup presence for lobby {lobby_id}: {presence_error}")

        current_lobby['post_match_cleanup'] = {
            'completed_at': time.time(),
            'kicked_players': kicked_players,
            'kick_errors': kick_errors
        }
        record_event('post_match_cleanup', current_lobby['post_match_cleanup'])

        release_finalized_server(current_lobby, reason='match_completed_cleanup')

        expired_players = list(current_lobby.get('players') or [])
        for player in expired_players:
            if player_activity is not None and player in player_activity:
                player_activity[player].pop('lobby_id', None)
                player_activity[player]['status'] = 'authenticated'
                player_activity[player]['last_seen'] = time.time()
            if get_player_sids:
                for sid in get_player_sids(player):
                    try:
                        socketio.server.leave_room(sid, lobby_id)
                    except Exception as room_error:
                        current_logger.warning(
                            f"Failed to remove sid {sid} from finalized lobby {lobby_id}: {room_error}"
                        )
            if emit_active_lobby_sync:
                try:
                    emit_active_lobby_sync(player, None)
                except Exception as sync_error:
                    current_logger.warning(
                        f"Failed to clear active lobby sync for {player} after {lobby_id}: {sync_error}"
                    )

        lobbies.pop(lobby_id, None)
        record_event('finalized_lobby_expired', {
            'players': expired_players,
            'delay_seconds': finalized_cleanup_delay_seconds
        })

        if broadcast_open_lobbies_update:
            try:
                broadcast_open_lobbies_update()
            except Exception as broadcast_error:
                current_logger.warning(f"Failed to broadcast open lobbies after cleanup for {lobby_id}: {broadcast_error}")
        if broadcast_queue_update:
            try:
                broadcast_queue_update()
            except Exception as broadcast_error:
                current_logger.warning(f"Failed to broadcast queue availability after cleanup for {lobby_id}: {broadcast_error}")

    def finalize_with_round_result(current_lobby, round_result, selected_map, log_message):
        round_result_summary = summarize_round_result(round_result)
        finalized_at = time.time()
        round_duration_seconds = get_round_duration_seconds(current_lobby, round_result)
        current_logger.info(f"{log_message}: {round_result_summary}")
        current_lobby['round_result'] = round_result
        current_lobby['announcement'] = 'Match finalised'
        current_lobby['step'] = 5
        current_lobby['finalized_at'] = finalized_at
        current_lobby['round_duration_seconds'] = round_duration_seconds
        current_lobby['server_details'] = {
            **(current_lobby.get('server_details') or {}),
            'roundResult': round_result,
            'liveStartedAt': current_lobby.get('live_started_at'),
            'matchFinalizedAt': finalized_at,
            'roundDurationSeconds': round_duration_seconds,
            'postMatchCleanupDelaySeconds': finalized_cleanup_delay_seconds
        }
        record_event('match_finalized', {
            'selected_map': selected_map,
            'round_result': round_result,
            'round_result_summary': round_result_summary,
            'round_duration_seconds': round_duration_seconds
        })
        save_completed_match(lobby_id, current_lobby, completed_at=finalized_at)
        release_finalized_server(current_lobby, reason='match_completed')
        socketio.emit('lobby_update', {
            'lobby_id': lobby_id,
            'announcement': current_lobby['announcement'],
            'server_details': current_lobby['server_details'],
            'server_released_at': current_lobby.get('server_released_at'),
            'step': 5
        }, room=lobby_id)
        eventlet.spawn(cleanup_finalized_lobby, dict(current_lobby))

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
            automation_mode = (
                automation_mode_provider() if automation_mode_provider else 'on'
            )
            automation_writes_enabled = automation_mode == 'on'
            if automation_mode == 'off':
                waiting_message = 'Automation is off. Manual admin control required.'
                if current_lobby.get('announcement') != waiting_message:
                    current_lobby['announcement'] = waiting_message
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': waiting_message
                    }, room=lobby_id)
                pause_aware_sleep(poll_seconds)
                continue

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

            unauthorized_players = get_unauthorized_connected_players(presence)
            kicked_unauthorized_players = []
            if unauthorized_players and kick_player_from_server and automation_writes_enabled:
                for player in unauthorized_players:
                    player_id = player.get('eosID') or player.get('steam_id')
                    try:
                        kick_player_from_server(
                            player_id,
                            reason='You are not in this match lobby.',
                            lobby_id=lobby_id
                        )
                        kicked_unauthorized_players.append({
                            'player_id': player_id,
                            'steam_id': player.get('steam_id'),
                            'serverName': player.get('serverName')
                        })
                    except Exception as kick_error:
                        current_logger.warning(
                            f"Failed to kick unauthorized player from lobby {lobby_id}: {kick_error}"
                        )
                        record_event('unauthorized_player_kick_failed', {
                            'player': player,
                            'error': str(kick_error)
                        })

            if kicked_unauthorized_players:
                record_event('unauthorized_players_kicked', {
                    'players': kicked_unauthorized_players
                })

            readiness_settings = get_effective_live_roll_readiness_settings(current_lobby)
            readiness = get_live_roll_readiness(
                current_lobby,
                presence,
                **{
                    key: value
                    for key, value in readiness_settings.items()
                    if key != 'mode'
                }
            )
            current_lobby['live_roll_countdown'] = int(readiness['remainingGraceSeconds'])
            ready_override = bool(current_lobby.get('live_roll_admin_ready_override'))

            mismatched_players = [
                row for row in (presence.get('players') or [])
                if row.get('connected') and not row.get('teamAligned')
            ]
            has_connected_team_mismatch = bool(mismatched_players)
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
                if not current_lobby.get('live_roll_done') and not retry_state.get('shouldRetry'):
                    continue
                if not automation_writes_enabled:
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

            force_timer_allows_mismatch = (
                readiness.get('forceReady')
                and not readiness.get('forceRequiresAligned')
            )
            if (
                waiting_for_initial_live_roll
                and has_connected_team_mismatch
                and not force_timer_allows_mismatch
            ):
                log_live_roll_state(
                    'blocked_team_mismatch',
                    current_lobby,
                    presence=presence,
                    readiness=readiness,
                    automation_writes_enabled=automation_writes_enabled,
                    mismatched_players=[
                        {
                            'username': row.get('username'),
                            'connected': row.get('connected'),
                            'teamAligned': row.get('teamAligned'),
                            'expectedTeam': row.get('expectedTeam'),
                            'serverTeam': row.get('serverTeam')
                        }
                        for row in mismatched_players
                    ]
                )
                mismatch_message = (
                    f"Waiting for connected players to be on the correct side: "
                    f"{readiness['alignedCount']}/{readiness['connectedCount']} aligned."
                )
                if current_lobby.get('announcement') != mismatch_message:
                    current_lobby['announcement'] = mismatch_message
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': mismatch_message,
                        'live_roll_ready_at': current_lobby.get('live_roll_ready_at'),
                        'live_roll_countdown': current_lobby.get('live_roll_countdown')
                    }, room=lobby_id)
                pause_aware_sleep(poll_seconds)
                continue

            if waiting_for_initial_live_roll and not readiness['ready'] and not ready_override:
                log_live_roll_state(
                    'blocked_readiness',
                    current_lobby,
                    presence=presence,
                    readiness=readiness,
                    automation_writes_enabled=automation_writes_enabled,
                    remaining_grace=readiness.get('remainingGraceSeconds')
                )
                threshold_minutes = max(1, int(threshold_grace_seconds / 60))
                force_minutes = max(1, int(readiness_settings['ready_grace_seconds'] / 60))
                if readiness.get('ratioReadyEnabled'):
                    waiting_message = (
                        f"Please join the server: {readiness['alignedCount']}/"
                        f"{readiness['totalPlayers']} on the correct team "
                        f"({readiness['connectedCount']} connected). "
                        f"Rolling to live once everyone is connected, "
                        f"or {readiness['requiredAfterGrace']}/{readiness['totalPlayers']} "
                        f"({int(readiness_settings['ready_ratio'] * 100)}%) are connected after {threshold_minutes} minutes. "
                        f"Force rolling after {force_minutes} minutes."
                    )
                else:
                    waiting_message = (
                        f"Please join the server: {readiness['alignedCount']}/"
                        f"{readiness['totalPlayers']} on the correct team "
                        f"({readiness['connectedCount']} connected). "
                        f"Rolling to live once everyone is connected. "
                        f"Force rolling after {force_minutes} minutes."
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
                log_live_roll_state(
                    'ready_to_process',
                    current_lobby,
                    presence=presence,
                    readiness=readiness,
                    automation_writes_enabled=automation_writes_enabled
                )
                round_result = fetch_latest_round_result()
                layer_status = None

                if current_lobby.get('live_roll_done'):
                    layer_status = get_server_layer_status(selected_map)

                if should_finalize_live_lobby(
                    current_lobby,
                    round_result,
                    selected_map
                ):
                    finalize_with_round_result(
                        current_lobby,
                        round_result,
                        selected_map,
                        f"Finalizing lobby {lobby_id} from matching round result"
                    )
                    return

                live_timer_status = get_live_match_timer_status(
                    current_lobby,
                    max_seconds=live_match_max_seconds,
                    layer_status=layer_status
                )
                if live_timer_status.get('elapsedSeconds') is not None:
                    current_lobby['live_match_elapsed_seconds'] = live_timer_status.get('elapsedSeconds')
                    current_lobby['live_match_timer_source'] = live_timer_status.get('source')

                if not current_lobby.get('live_roll_command_sent'):
                    if not automation_writes_enabled:
                        log_live_roll_state(
                            'blocked_monitor_only',
                            current_lobby,
                            presence=presence,
                            readiness=readiness,
                            automation_writes_enabled=automation_writes_enabled
                        )
                        waiting_message = 'Automation is monitor only. Manual admin control required.'
                        if current_lobby.get('announcement') != waiting_message:
                            current_lobby['announcement'] = waiting_message
                            socketio.emit('lobby_update', {
                                'lobby_id': lobby_id,
                                'announcement': waiting_message
                            }, room=lobby_id)
                        pause_aware_sleep(poll_seconds)
                        continue
                    retry_state = get_live_roll_retry_state(
                        current_lobby,
                        retry_seconds=retry_seconds
                    )
                    if current_lobby.get('live_roll_change_attempts') and not retry_state.get('shouldRetry'):
                        log_live_roll_state(
                            'waiting_retry',
                            current_lobby,
                            presence=presence,
                            readiness=readiness,
                            automation_writes_enabled=automation_writes_enabled,
                            retry_state=retry_state,
                            last_error=current_lobby.get('live_roll_command_error')
                        )
                        retry_message = (
                            f'Could not roll server live on {selected_map}. '
                            f'Retrying in {retry_state.get("remainingSeconds")}s.'
                        )
                        last_error = current_lobby.get('live_roll_command_error')
                        if last_error:
                            retry_message = f'{retry_message} Last error: {last_error}'
                        emit_announcement(current_lobby, retry_message)
                        pause_aware_sleep(poll_seconds)
                        continue
                    announcement = f'Rolling to live on {selected_map}. Stand by.'
                    current_lobby['announcement'] = announcement
                    socketio.emit('lobby_update', {
                        'lobby_id': lobby_id,
                        'announcement': announcement
                    }, room=lobby_id)
                    try:
                        broadcast_response = broadcast_server_message(announcement)
                        mark_live_roll_broadcast_attempt(
                            current_lobby,
                            response=broadcast_response
                        )
                        record_event('live_roll_broadcast_sent', {
                            'selected_map': selected_map,
                            'message': announcement,
                            'response': broadcast_response
                        })
                        if pre_live_roll_broadcast_delay_seconds > 0:
                            pause_aware_sleep(pre_live_roll_broadcast_delay_seconds)
                    except Exception as broadcast_error:
                        mark_live_roll_broadcast_attempt(
                            current_lobby,
                            error=broadcast_error
                        )
                        record_event('live_roll_broadcast_failed', {
                            'selected_map': selected_map,
                            'message': announcement,
                            'error': str(broadcast_error)
                        })
                        current_logger.warning(
                            f"Failed to broadcast live roll announcement for lobby {lobby_id}: "
                            f"{broadcast_error}"
                        )
                    attempt_live_roll_change(
                        current_lobby,
                        selected_map,
                        'live_roll_attempted'
                    )
                    pause_aware_sleep(2)
                    continue

                if layer_status is None:
                    layer_status = get_server_layer_status(selected_map)
                retry_state = get_live_roll_retry_state(
                    current_lobby,
                    retry_seconds=retry_seconds
                )

                if has_live_layer_transitioned_away(current_lobby, layer_status):
                    fallback_result = build_unresolved_round_result(
                        current_lobby,
                        selected_map,
                        source='cmp-layer-transition-fallback'
                    )
                    finalize_with_round_result(
                        current_lobby,
                        fallback_result,
                        selected_map,
                        f"Finalizing live lobby {lobby_id} after selected layer rolled away"
                    )
                    return

                if has_selected_layer_started_after_roll(current_lobby, layer_status):
                    live_team_labels = layer_status.get('teamLabels') or {}
                    if live_team_labels:
                        current_lobby['team_labels'] = live_team_labels

                    if current_lobby.get('live_roll_done'):
                        was_live_broadcast_sent = bool(current_lobby.get('live_broadcast_sent'))
                        if automation_writes_enabled:
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
                                'team_labels': current_lobby.get('team_labels', {}),
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
                                'team_labels': current_lobby.get('team_labels', {}),
                                'live_roll_ready_at': current_lobby.get('live_roll_ready_at'),
                                'live_roll_countdown': 0,
                                'step': 4
                            }, room=lobby_id)
                    else:
                        live_announcement = 'Live'
                        live_started_at = get_live_started_at_from_layer_status(layer_status)
                        schedule_live_broadcast(
                            current_lobby,
                            delay_seconds=live_broadcast_delay_seconds,
                            now=live_started_at
                        )
                        live_broadcast_error = current_lobby.get('live_broadcast_error')
                        server_details = get_server_connection_details()
                        current_lobby['live_roll_done'] = True
                        current_lobby['live_started_at'] = live_started_at
                        current_lobby['live_match_max_seconds'] = live_match_max_seconds
                        current_lobby['announcement'] = live_announcement
                        current_lobby['server_details'] = {
                            **server_details,
                            'map': selected_map,
                            'bridge_response': current_lobby.get('live_roll_command_response'),
                            'layerStatus': layer_status,
                            'liveMatchMaxSeconds': live_match_max_seconds,
                            'liveRollBroadcastResponse': current_lobby.get('live_roll_broadcast_response'),
                            'liveRollBroadcastError': current_lobby.get('live_roll_broadcast_error'),
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
                            'team_labels': current_lobby.get('team_labels', {}),
                            'server_details': current_lobby['server_details'],
                            'live_started_at': current_lobby.get('live_started_at'),
                            'live_match_max_seconds': live_match_max_seconds,
                            'live_roll_ready_at': current_lobby.get('live_roll_ready_at'),
                            'live_roll_countdown': 0,
                            'step': 4
                        }, room=lobby_id)

                    if should_finalize_live_lobby(current_lobby, round_result, selected_map):
                        finalize_with_round_result(
                            current_lobby,
                            round_result,
                            selected_map,
                            f"Finalizing live lobby {lobby_id} after layer confirmation"
                        )
                        return

                    pause_aware_sleep(poll_seconds)
                    continue

                if layer_status.get('currentMatches'):
                    waiting_message = f'Waiting for {selected_map} to finish loading.'
                    if current_lobby.get('announcement') != waiting_message:
                        current_lobby['announcement'] = waiting_message
                        socketio.emit('lobby_update', {
                            'lobby_id': lobby_id,
                            'announcement': waiting_message
                        }, room=lobby_id)
                    pause_aware_sleep(poll_seconds)
                    continue

                if layer_status.get('nextMatches'):
                    if retry_state.get('shouldRetry'):
                        if not automation_writes_enabled:
                            queued_message = f'{selected_map} is queued as the next round. Manual admin control required.'
                            if current_lobby.get('announcement') != queued_message:
                                current_lobby['announcement'] = queued_message
                                socketio.emit('lobby_update', {
                                    'lobby_id': lobby_id,
                                    'announcement': queued_message
                                }, room=lobby_id)
                            pause_aware_sleep(poll_seconds)
                            continue
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
                        attempt_live_roll_change(
                            current_lobby,
                            selected_map,
                            'live_roll_retry_attempted'
                        )
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
                    if not automation_writes_enabled:
                        waiting_message = f'Waiting for the server to move onto {selected_map}. Manual admin control required.'
                        if current_lobby.get('announcement') != waiting_message:
                            current_lobby['announcement'] = waiting_message
                            socketio.emit('lobby_update', {
                                'lobby_id': lobby_id,
                                'announcement': waiting_message
                            }, room=lobby_id)
                        pause_aware_sleep(poll_seconds)
                        continue
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
                    if not automation_writes_enabled:
                        waiting_message = f'Waiting for the server to move onto {selected_map}. Manual admin control required.'
                        if current_lobby.get('announcement') != waiting_message:
                            current_lobby['announcement'] = waiting_message
                            socketio.emit('lobby_update', {
                                'lobby_id': lobby_id,
                                'announcement': waiting_message
                            }, room=lobby_id)
                        pause_aware_sleep(poll_seconds)
                        continue
                    retry_message = f'Waiting for the server to move onto {selected_map}. Retrying immediate roll now.'
                    if current_lobby.get('announcement') != retry_message:
                        current_lobby['announcement'] = retry_message
                        socketio.emit('lobby_update', {
                            'lobby_id': lobby_id,
                            'announcement': retry_message
                        }, room=lobby_id)
                    attempt_live_roll_change(
                        current_lobby,
                        selected_map,
                        'live_roll_retry_attempted'
                    )
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
