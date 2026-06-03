import logging

import eventlet

from services.bridge import BridgeUnavailable


def start_live_roll_monitor(
    lobby_id,
    lobbies,
    socketio,
    build_lobby_server_presence,
    pause_aware_sleep,
    broadcast_server_message,
    change_server_to_selected_map,
    dev_mode=False,
    logger=None
):
    current_logger = logger or logging.getLogger(__name__)
    lobby = lobbies.get(lobby_id)
    if not lobby:
        return

    lobby['live_roll_token'] = lobby.get('live_roll_token', 0) + 1
    token = lobby['live_roll_token']

    def monitor():
        while True:
            current_lobby = lobbies.get(lobby_id)
            if not current_lobby:
                return
            if current_lobby.get('live_roll_token') != token:
                return
            if current_lobby.get('step') != 3:
                return
            if current_lobby.get('live_roll_done'):
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
                pause_aware_sleep(5)
                continue
            except Exception as e:
                current_logger.error(f"Error checking server presence for lobby {lobby_id}: {str(e)}")
                pause_aware_sleep(5)
                continue

            connected_usernames = set(presence.get('connected', []))
            dev_ready_override = dev_mode and 'neil' in connected_usernames

            if presence.get('missing') and not dev_ready_override:
                pause_aware_sleep(5)
                continue

            selected_map = current_lobby.get('selected_map')
            announcement = f'Rolling to live on {selected_map}'
            current_lobby['announcement'] = announcement
            socketio.emit('lobby_update', {
                'lobby_id': lobby_id,
                'announcement': announcement
            }, room=lobby_id)

            pause_aware_sleep(2)

            try:
                broadcast_server_message(announcement)
                bridge_response = change_server_to_selected_map(selected_map)
                live_announcement = 'Live'
                broadcast_server_message(live_announcement)
                current_lobby['live_roll_done'] = True
                current_lobby['announcement'] = live_announcement
                current_lobby['server_details'] = {
                    'map': selected_map,
                    'bridge_response': bridge_response
                }
                current_lobby['step'] = 4
                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'announcement': live_announcement,
                    'selected_map': selected_map,
                    'server_details': current_lobby['server_details'],
                    'step': 4
                }, room=lobby_id)
            except BridgeUnavailable:
                waiting_message = 'Waiting for SquadJS bridge to become available.'
                current_lobby['announcement'] = waiting_message
                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'announcement': waiting_message
                }, room=lobby_id)
                pause_aware_sleep(5)
                continue
            except Exception as e:
                error_message = f'Failed to roll server live on "{selected_map}": {str(e)}'
                current_lobby['announcement'] = error_message
                current_logger.error(error_message)
                socketio.emit('lobby_update', {
                    'lobby_id': lobby_id,
                    'announcement': error_message
                }, room=lobby_id)
            return

    eventlet.spawn(monitor)
