from flask import jsonify, request
from flask_jwt_extended import decode_token, jwt_required
from flask_socketio import emit, join_room, leave_room
import random
import time


def register_http_routes(app):
    import app as backend_app

    @app.route('/')
    def index():
        return f"CMP SocketIO backend running. Frontend handled through Vue.js for origins: {', '.join(backend_app.FRONTEND_ORIGINS)}"

    @app.route('/health', methods=['GET'])
    def health():
        database = backend_app.get_database_health()
        bridge = backend_app.get_bridge_health()
        ok = bool(database.get('ok')) and bool(bridge.get('ok'))
        payload = {
            'ok': ok,
            'status': 'ok' if ok else 'degraded',
            'service': 'backend',
            'database': database,
            'squadjsBridge': bridge,
            'queueSize': len(backend_app.matchmaking_queue),
            'lobbyCount': len(backend_app.lobbies)
        }
        return jsonify(payload), (200 if ok else 503)

    @app.route('/api/server/players', methods=['GET'])
    @jwt_required()
    def api_server_players():
        try:
            return jsonify({
                'success': True,
                'players': backend_app.fetch_connected_server_players_service(
                    backend_app.squadjs_bridge_request_service
                )
            })
        except Exception as e:
            backend_app.logger.error(f"Error fetching server players from SquadJS bridge: {str(e)}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 502

    @app.route('/api/lobbies/<lobby_id>/server-presence', methods=['GET'])
    @jwt_required()
    def api_lobby_server_presence(lobby_id):
        try:
            return jsonify({
                'success': True,
                'presence': backend_app.build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=True)
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 404
        except Exception as e:
            backend_app.logger.error(f"Error building server presence for lobby {lobby_id}: {str(e)}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 502

    @backend_app.socketio.on_error_default
    @backend_app.handle_socket_data
    def default_error_handler(e):
        print(f"SocketIO error: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Request SID: {request.sid}")
        print(f"Request event: {request.event}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")


def register_socket_routes(socketio):
    import app as backend_app

    @socketio.on('*')
    @backend_app.handle_socket_data
    def catch_all(event, *args):
        backend_app.logger.info("=== Caught unhandled event ===")
        backend_app.logger.info(f"Event: {event}")
        backend_app.logger.info(f"Data: {args}")

    @socketio.on(backend_app.SOCKET_EVENTS['CONNECTION']['CONNECT'])
    def handle_connect(auth):
        return backend_app.handle_connect_event(
            auth,
            request=request,
            logger=backend_app.logger,
            emit=emit,
            socket_events=backend_app.SOCKET_EVENTS,
            decode_token=decode_token,
            is_countdown_paused=backend_app.is_countdown_paused,
            find_active_lobby_for_user=backend_app.find_active_lobby_for_user,
            upsert_player_activity=backend_app.upsert_player_activity,
            join_room=join_room,
            get_user_room=backend_app.get_user_room
        )

    @socketio.on(backend_app.SOCKET_EVENTS['CONNECTION']['DISCONNECT'])
    @backend_app.handle_socket_data
    def handle_disconnect(reason=None):
        return backend_app.handle_disconnect_event(
            reason,
            request=request,
            logger=backend_app.logger,
            get_username_by_sid=backend_app.get_username_by_sid,
            remove_player_session=backend_app.remove_player_session,
            player_activity=backend_app.player_activity,
            lobbies=backend_app.lobbies,
            emit=emit,
            matchmaking_queue=backend_app.matchmaking_queue,
            pending_match=backend_app.pending_match,
            cancel_pending_match=backend_app.cancel_pending_match,
            broadcast_queue_update=backend_app.broadcast_queue_update
        )

    @socketio.on(backend_app.SOCKET_EVENTS['AUTH']['REGISTER'])
    @backend_app.handle_socket_data
    def register_socket(data):
        return backend_app.register_socket_event(
            data,
            users=backend_app.users,
            save_users=backend_app.save_users,
            create_access_token=backend_app.create_access_token,
            get_user_profile=backend_app.get_user_profile,
            logger=backend_app.logger
        )

    @socketio.on(backend_app.SOCKET_EVENTS['AUTH']['LOGIN'])
    @backend_app.handle_socket_data
    def login_socket(data):
        return backend_app.login_socket_event(
            data,
            logger=backend_app.logger,
            get_user_record=backend_app.get_user_record,
            create_access_token=backend_app.create_access_token,
            find_active_lobby_for_user=backend_app.find_active_lobby_for_user,
            lobbies=backend_app.lobbies,
            upsert_player_activity=backend_app.upsert_player_activity,
            request=request,
            join_room=join_room,
            get_user_room=backend_app.get_user_room,
            emit=emit,
            get_user_profile=backend_app.get_user_profile
        )

    @socketio.on(backend_app.SOCKET_EVENTS['AUTH']['AUTHENTICATE'])
    @backend_app.handle_socket_data
    def handle_authenticate(data):
        return backend_app.handle_authenticate_event(
            data,
            request=request,
            logger=backend_app.logger,
            upsert_player_activity=backend_app.upsert_player_activity,
            matchmaking_queue=backend_app.matchmaking_queue,
            join_room=join_room,
            get_user_room=backend_app.get_user_room,
            build_queue_payload=backend_app.build_queue_payload,
            emit=emit
        )

    @socketio.on(backend_app.SOCKET_EVENTS['PROFILE']['STATUS'])
    @backend_app.handle_socket_data
    def handle_profile_status(data=None):
        return backend_app.handle_profile_status_event(
            data,
            backend_app.build_profile_status_service,
            backend_app.get_user_profile,
            backend_app.find_active_lobby_for_user,
            backend_app.logger
        )

    @socketio.on(backend_app.SOCKET_EVENTS['PROFILE']['UPDATE_STEAM_ID'])
    @backend_app.handle_socket_data
    def handle_update_steam_id(data=None):
        return backend_app.handle_update_steam_id_event(
            data,
            backend_app.update_steam_id_service,
            backend_app.get_user_record,
            backend_app.matchmaking_queue,
            backend_app.is_user_in_any_lobby,
            backend_app.save_users,
            backend_app.users,
            backend_app.get_user_profile,
            backend_app.logger
        )

    @socketio.on(backend_app.SOCKET_EVENTS['QUEUE']['JOIN'])
    @backend_app.handle_socket_data
    def handle_join_queue(data):
        return backend_app.handle_join_queue_event(
            data,
            socket_events=backend_app.SOCKET_EVENTS,
            emit=emit,
            socketio=socketio,
            request=request,
            logger=backend_app.logger,
            group_lock=backend_app.group_lock,
            get_user_group=backend_app.get_user_group,
            user_has_steam_id=backend_app.user_has_steam_id,
            build_queue_payload=backend_app.build_queue_payload,
            queue_lock=backend_app.queue_lock,
            matchmaking_queue=backend_app.matchmaking_queue,
            max_lobby_players=backend_app.MAX_LOBBY_PLAYERS,
            upsert_player_activity=backend_app.upsert_player_activity,
            save_queue=backend_app.save_queue,
            check_queue_and_start_countdown=backend_app.check_queue_and_start_countdown
        )

    @socketio.on(backend_app.SOCKET_EVENTS['QUEUE']['LEAVE'])
    @backend_app.handle_socket_data
    def handle_leave_queue(data):
        return backend_app.handle_leave_queue_event(
            data,
            socket_events=backend_app.SOCKET_EVENTS,
            emit=emit,
            socketio=socketio,
            logger=backend_app.logger,
            queue_lock=backend_app.queue_lock,
            matchmaking_queue=backend_app.matchmaking_queue,
            save_queue=backend_app.save_queue,
            pending_match=backend_app.pending_match,
            build_queue_payload=backend_app.build_queue_payload,
            cancel_pending_match=backend_app.cancel_pending_match
        )

    @socketio.on(backend_app.SOCKET_EVENTS['QUEUE']['STATUS'])
    @backend_app.handle_socket_data
    def handle_queue_status(data=None):
        return backend_app.handle_queue_status_event(
            data,
            socket_events=backend_app.SOCKET_EVENTS,
            emit=emit,
            logger=backend_app.logger,
            build_queue_payload=backend_app.build_queue_payload
        )

    @socketio.on(backend_app.SOCKET_EVENTS['QUEUE']['ACCEPT_MATCH'])
    @backend_app.handle_socket_data
    def handle_accept_match(data=None):
        return backend_app.handle_accept_match_event(
            data,
            request=request,
            logger=backend_app.logger,
            queue_lock=backend_app.queue_lock,
            pending_match=backend_app.pending_match,
            get_username_by_sid=backend_app.get_username_by_sid,
            get_match_accept_payload=backend_app.get_match_accept_payload,
            broadcast_queue_update=backend_app.broadcast_queue_update,
            finalize_pending_match=backend_app.finalize_pending_match
        )

    @socketio.on(backend_app.SOCKET_EVENTS['GROUP']['CREATE'])
    @backend_app.handle_socket_data
    def handle_group_create(data=None):
        return backend_app.handle_group_create_event(
            data,
            request=request,
            logger=backend_app.logger,
            group_lock=backend_app.group_lock,
            get_user_group=backend_app.get_user_group,
            generate_group_code=backend_app.generate_group_code,
            groups=backend_app.groups,
            user_to_group=backend_app.user_to_group,
            upsert_player_activity=backend_app.upsert_player_activity,
            join_room=join_room,
            get_group_payload=backend_app.get_group_payload,
            broadcast_group_update=backend_app.broadcast_group_update
        )

    @socketio.on(backend_app.SOCKET_EVENTS['GROUP']['JOIN'])
    @backend_app.handle_socket_data
    def handle_group_join(data=None):
        return backend_app.handle_group_join_event(
            data,
            request=request,
            logger=backend_app.logger,
            group_lock=backend_app.group_lock,
            get_user_group=backend_app.get_user_group,
            groups=backend_app.groups,
            max_lobby_players=backend_app.MAX_LOBBY_PLAYERS,
            user_to_group=backend_app.user_to_group,
            upsert_player_activity=backend_app.upsert_player_activity,
            join_room=join_room,
            get_group_payload=backend_app.get_group_payload,
            broadcast_group_update=backend_app.broadcast_group_update
        )

    @socketio.on(backend_app.SOCKET_EVENTS['GROUP']['LEAVE'])
    @backend_app.handle_socket_data
    def handle_group_leave(data=None):
        return backend_app.handle_group_leave_event(
            data,
            logger=backend_app.logger,
            group_lock=backend_app.group_lock,
            get_user_group=backend_app.get_user_group,
            groups=backend_app.groups,
            user_to_group=backend_app.user_to_group,
            leave_room=leave_room,
            get_group_payload=backend_app.get_group_payload,
            broadcast_group_update=backend_app.broadcast_group_update
        )

    @socketio.on(backend_app.SOCKET_EVENTS['GROUP']['STATUS'])
    @backend_app.handle_socket_data
    def handle_group_status(data=None):
        return backend_app.handle_group_status_event(
            data,
            logger=backend_app.logger,
            group_lock=backend_app.group_lock,
            get_user_group=backend_app.get_user_group,
            get_group_payload=backend_app.get_group_payload
        )

    @socketio.on(backend_app.SOCKET_EVENTS['GROUP']['QUEUE'])
    @backend_app.handle_socket_data
    def handle_group_queue(data=None):
        return backend_app.handle_group_queue_event(
            data,
            logger=backend_app.logger,
            group_lock=backend_app.group_lock,
            get_user_group=backend_app.get_user_group,
            groups=backend_app.groups,
            max_lobby_players=backend_app.MAX_LOBBY_PLAYERS,
            user_has_steam_id=backend_app.user_has_steam_id,
            is_user_in_any_lobby=backend_app.is_user_in_any_lobby,
            queue_lock=backend_app.queue_lock,
            matchmaking_queue=backend_app.matchmaking_queue,
            upsert_player_activity=backend_app.upsert_player_activity,
            save_queue=backend_app.save_queue,
            broadcast_queue_update=backend_app.broadcast_queue_update,
            check_queue_and_start_countdown=backend_app.check_queue_and_start_countdown,
            build_queue_payload=backend_app.build_queue_payload
        )

    @socketio.on(backend_app.SOCKET_EVENTS['GROUP']['UNQUEUE'])
    @backend_app.handle_socket_data
    def handle_group_unqueue(data=None):
        return backend_app.handle_group_unqueue_event(
            data,
            logger=backend_app.logger,
            group_lock=backend_app.group_lock,
            get_user_group=backend_app.get_user_group,
            groups=backend_app.groups,
            queue_lock=backend_app.queue_lock,
            matchmaking_queue=backend_app.matchmaking_queue,
            player_activity=backend_app.player_activity,
            save_queue=backend_app.save_queue,
            broadcast_queue_update=backend_app.broadcast_queue_update
        )

    @socketio.on(backend_app.SOCKET_EVENTS['OPEN_LOBBIES']['STATUS'])
    @backend_app.handle_socket_data
    def handle_open_lobbies_status(data=None):
        return backend_app.handle_open_lobbies_status_event(
            backend_app.get_open_lobbies,
            backend_app.get_active_lobbies,
            backend_app.logger
        )

    @socketio.on(backend_app.SOCKET_EVENTS['COUNTDOWN']['STATUS'])
    @backend_app.handle_socket_data
    def handle_countdown_status(data=None):
        return backend_app.handle_countdown_status_event(
            backend_app.is_countdown_paused,
            backend_app.logger
        )

    @socketio.on(backend_app.SOCKET_EVENTS['COUNTDOWN']['TOGGLE_PAUSE'])
    @backend_app.handle_socket_data
    def handle_toggle_countdown_pause(data=None):
        return backend_app.handle_toggle_countdown_pause_event(
            data,
            socketio=socketio,
            socket_events=backend_app.SOCKET_EVENTS,
            is_countdown_paused=backend_app.is_countdown_paused,
            set_countdown_paused=backend_app.set_countdown_paused,
            logger=backend_app.logger
        )

    @socketio.on(backend_app.SOCKET_EVENTS['LOBBY']['JOIN'])
    @backend_app.handle_socket_data
    def handle_join_lobby(data=None):
        return backend_app.handle_join_lobby_event(
            data,
            request=request,
            logger=backend_app.logger,
            lobbies=backend_app.lobbies,
            matchmaking_queue=backend_app.matchmaking_queue,
            queue_lock=backend_app.queue_lock,
            MAX_LOBBY_PLAYERS=backend_app.MAX_LOBBY_PLAYERS,
            get_user_group=backend_app.get_user_group,
            groups=backend_app.groups,
            user_to_group=backend_app.user_to_group,
            save_queue=backend_app.save_queue,
            broadcast_queue_update=backend_app.broadcast_queue_update,
            broadcast_open_lobbies_update=backend_app.broadcast_open_lobbies_update,
            join_room=join_room,
            upsert_player_activity=backend_app.upsert_player_activity,
            get_user_room=backend_app.get_user_room,
            get_player_groups=backend_app.get_player_groups,
            emit=emit,
            emit_active_lobby_sync=backend_app.emit_active_lobby_sync,
            assign_teams=backend_app.assign_teams,
            select_captains=backend_app.select_captains
        )

    @socketio.on(backend_app.SOCKET_EVENTS['LOBBY']['LEAVE'])
    @backend_app.handle_socket_data
    def handle_leave_lobby(data=None):
        return backend_app.handle_leave_lobby_event(
            data,
            request=request,
            logger=backend_app.logger,
            lobbies=backend_app.lobbies,
            get_username_by_sid=backend_app.get_username_by_sid,
            player_activity=backend_app.player_activity,
            get_player_sids=backend_app.get_player_sids,
            socketio=socketio,
            emit=emit,
            broadcast_queue_update=backend_app.broadcast_queue_update,
            broadcast_open_lobbies_update=backend_app.broadcast_open_lobbies_update,
            emit_active_lobby_sync=backend_app.emit_active_lobby_sync,
            select_captains=backend_app.select_captains
        )

    @socketio.on(backend_app.SOCKET_EVENTS['LOBBY']['GET_DATA'])
    @backend_app.handle_socket_data
    def handle_get_lobby_data(data=None):
        return backend_app.handle_get_lobby_data_event(
            data,
            lobbies=backend_app.lobbies,
            emit=emit,
            socket_events=backend_app.SOCKET_EVENTS
        )

    @socketio.on(backend_app.SOCKET_EVENTS['LOBBY']['SERVER_PRESENCE'])
    @backend_app.handle_socket_data
    def handle_lobby_server_presence(data=None):
        return backend_app.handle_server_presence_event(
            data,
            logger=backend_app.logger,
            build_lobby_server_presence=backend_app.build_lobby_server_presence
        )

    @socketio.on(backend_app.SOCKET_EVENTS['LOBBY']['VOTE_MAP'])
    @backend_app.handle_socket_data
    def handle_vote_map(data=None):
        return backend_app.vote_map_event(
            data,
            request=request,
            logger=backend_app.logger,
            lobbies=backend_app.lobbies,
            socketio=socketio,
            get_username_by_sid=backend_app.get_username_by_sid
        )

    @socketio.on(backend_app.SOCKET_EVENTS['LOBBY']['SKIP_PHASE'])
    @backend_app.handle_socket_data
    def handle_skip_phase(data=None):
        return backend_app.handle_skip_phase_event(
            data,
            logger=backend_app.logger,
            lobbies=backend_app.lobbies,
            select_map_from_votes_fn=backend_app.select_map_from_votes,
            socketio=socketio,
            start_live_roll_monitor=backend_app.start_live_roll_monitor
        )

    @socketio.on(backend_app.SOCKET_EVENTS['LOBBY']['PREV_PHASE'])
    @backend_app.handle_socket_data
    def handle_prev_phase(data=None):
        return backend_app.handle_prev_phase_event(
            data,
            logger=backend_app.logger,
            dev_mode=backend_app.DEV_MODE,
            lobbies=backend_app.lobbies,
            socketio=socketio
        )

    @socketio.on(backend_app.SOCKET_EVENTS['LOBBY']['START'])
    @backend_app.handle_socket_data
    def handle_start_lobby(data=None):
        return backend_app.handle_start_lobby_event(
            data,
            lobbies=backend_app.lobbies,
            emit=emit,
            socket_events=backend_app.SOCKET_EVENTS
        )
