from flask import jsonify, redirect, request
from flask_jwt_extended import decode_token, get_jwt_identity, jwt_required
from flask_socketio import emit, join_room, leave_room
import random
import secrets
import time
from types import SimpleNamespace

from services.queue import has_available_server_capacity
from services.steam_auth import (
    build_frontend_callback_url,
    build_steam_login_url,
    extract_steam_id,
    frontend_origin_from_request,
    fetch_steam_persona_name,
    get_steam_openid_verification_result,
    get_or_create_steam_user,
    load_steam_state,
)


def _http_backend_api():
    import app as backend_app

    return SimpleNamespace(
        FRONTEND_ORIGINS=backend_app.FRONTEND_ORIGINS,
        STEAM_WEB_API_KEY=backend_app.STEAM_WEB_API_KEY,
        app=backend_app.app,
        build_lobby_server_presence=backend_app.build_lobby_server_presence,
        build_lobby_join_url=backend_app.build_lobby_join_url,
        approve_server=backend_app.approve_server,
        create_access_token=backend_app.create_access_token,
        create_server=backend_app.create_server,
        fetch_completed_matches=backend_app.fetch_completed_matches,
        fetch_connected_server_players_service=backend_app.fetch_connected_server_players_service,
        find_active_lobby_for_user=backend_app.find_active_lobby_for_user,
        get_admin_diagnostics=backend_app.get_admin_diagnostics,
        set_self_admin_mode=backend_app.set_self_admin_mode,
        can_toggle_admin_mode=backend_app.can_toggle_admin_mode,
        get_bridge_health=backend_app.get_bridge_health,
        get_database_health=backend_app.get_database_health,
        get_server_connection_details=backend_app.get_server_connection_details,
        get_user_profile=backend_app.get_user_profile,
        get_server_by_id=backend_app.get_server_by_id,
        handle_socket_data=backend_app.handle_socket_data,
        is_admin_user=backend_app.is_admin_user,
        list_available_servers=backend_app.list_available_servers,
        list_servers=backend_app.list_servers,
        lobbies=backend_app.lobbies,
        logger=backend_app.logger,
        matchmaking_queue=backend_app.matchmaking_queue,
        run_server_health_check=backend_app.run_server_health_check,
        save_users=backend_app.save_users,
        set_automation_mode=backend_app.set_automation_mode,
        set_server_enabled=backend_app.set_server_enabled,
        socketio=backend_app.socketio,
        squadjs_bridge_request=backend_app.squadjs_bridge_request,
        test_server_connection=backend_app.test_server_connection,
        users=backend_app.users,
    )


def _socket_backend_api():
    import app as backend_app

    return SimpleNamespace(
        AUTH_LOGIN_MAX_ATTEMPTS=backend_app.AUTH_LOGIN_MAX_ATTEMPTS,
        AUTH_RATE_LIMIT_WINDOW_SECONDS=backend_app.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        AUTH_REGISTER_MAX_ATTEMPTS=backend_app.AUTH_REGISTER_MAX_ATTEMPTS,
        DEV_MODE=backend_app.DEV_MODE,
        LIVE_ROLL_READY_GRACE_SECONDS=backend_app.LIVE_ROLL_READY_GRACE_SECONDS,
        MAX_LOBBY_PLAYERS=backend_app.MAX_LOBBY_PLAYERS,
        PASSWORD_AUTH_ENABLED=backend_app.PASSWORD_AUTH_ENABLED,
        QUEUE_MODES=backend_app.QUEUE_MODES,
        SOCKET_EVENTS=backend_app.SOCKET_EVENTS,
        WEB_LOBBY_DISCONNECT_TRACKING_ENABLED=backend_app.WEB_LOBBY_DISCONNECT_TRACKING_ENABLED,
        assign_teams=backend_app.assign_teams,
        broadcast_group_update=backend_app.broadcast_group_update,
        broadcast_open_lobbies_update=backend_app.broadcast_open_lobbies_update,
        broadcast_queue_update=backend_app.broadcast_queue_update,
        build_lobby_server_presence=backend_app.build_lobby_server_presence,
        build_profile_status_service=backend_app.build_profile_status_service,
        build_queue_payload=backend_app.build_queue_payload,
        cancel_pending_match=backend_app.cancel_pending_match,
        check_queue_and_start_countdown=backend_app.check_queue_and_start_countdown,
        release_server_allocation=backend_app.release_server_allocation,
        create_access_token=backend_app.create_access_token,
        emit_active_lobby_sync=backend_app.emit_active_lobby_sync,
        find_active_lobby_for_user=backend_app.find_active_lobby_for_user,
        finalize_pending_match=backend_app.finalize_pending_match,
        generate_group_code=backend_app.generate_group_code,
        get_active_lobbies=backend_app.get_active_lobbies,
        get_group_payload=backend_app.get_group_payload,
        get_match_accept_payload=backend_app.get_match_accept_payload,
        get_open_lobbies=backend_app.get_open_lobbies,
        get_player_groups=backend_app.get_player_groups,
        get_player_sids=backend_app.get_player_sids,
        get_server_connection_details=backend_app.get_server_connection_details,
        get_selected_map_team_labels=backend_app.get_selected_map_team_labels,
        get_user_group=backend_app.get_user_group,
        get_user_profile=backend_app.get_user_profile,
        get_user_record=backend_app.get_user_record,
        get_user_room=backend_app.get_user_room,
        get_username_by_sid=backend_app.get_username_by_sid,
        disabled_queue_modes=backend_app.disabled_queue_modes,
        group_lock=backend_app.group_lock,
        groups=backend_app.groups,
        handle_accept_match_event=backend_app.handle_accept_match_event,
        handle_authenticate_event=backend_app.handle_authenticate_event,
        handle_clear_queue_event=backend_app.handle_clear_queue_event,
        handle_connect_event=backend_app.handle_connect_event,
        handle_countdown_status_event=backend_app.handle_countdown_status_event,
        handle_delete_lobby_event=backend_app.handle_delete_lobby_event,
        handle_disconnect_event=backend_app.handle_disconnect_event,
        handle_force_live_ready_event=backend_app.handle_force_live_ready_event,
        handle_get_lobby_data_event=backend_app.handle_get_lobby_data_event,
        handle_group_create_event=backend_app.handle_group_create_event,
        handle_group_join_event=backend_app.handle_group_join_event,
        handle_group_kick_event=backend_app.handle_group_kick_event,
        handle_group_leave_event=backend_app.handle_group_leave_event,
        handle_group_queue_event=backend_app.handle_group_queue_event,
        handle_group_seed_event=backend_app.handle_group_seed_event,
        handle_group_status_event=backend_app.handle_group_status_event,
        handle_group_transfer_event=backend_app.handle_group_transfer_event,
        handle_group_unqueue_event=backend_app.handle_group_unqueue_event,
        handle_join_lobby_event=backend_app.handle_join_lobby_event,
        handle_join_queue_event=backend_app.handle_join_queue_event,
        handle_leave_lobby_event=backend_app.handle_leave_lobby_event,
        handle_leave_queue_event=backend_app.handle_leave_queue_event,
        handle_open_lobbies_status_event=backend_app.handle_open_lobbies_status_event,
        handle_prev_phase_event=backend_app.handle_prev_phase_event,
        handle_profile_status_event=backend_app.handle_profile_status_event,
        handle_queue_status_event=backend_app.handle_queue_status_event,
        handle_seed_queue_event=backend_app.handle_seed_queue_event,
        handle_set_queue_enabled_event=backend_app.handle_set_queue_enabled_event,
        handle_server_presence_event=backend_app.handle_server_presence_event,
        handle_skip_phase_event=backend_app.handle_skip_phase_event,
        handle_socket_data=backend_app.handle_socket_data,
        handle_start_lobby_event=backend_app.handle_start_lobby_event,
        handle_toggle_countdown_pause_event=backend_app.handle_toggle_countdown_pause_event,
        handle_update_display_name_event=backend_app.handle_update_display_name_event,
        handle_update_steam_id_event=backend_app.handle_update_steam_id_event,
        hash_password=backend_app.hash_password,
        is_admin_user=backend_app.is_admin_user,
        is_countdown_paused=backend_app.is_countdown_paused,
        is_user_in_any_lobby=backend_app.is_user_in_any_lobby,
        lobbies=backend_app.lobbies,
        logger=backend_app.logger,
        login_socket_event=backend_app.login_socket_event,
        matchmaking_queue=backend_app.matchmaking_queue,
        pending_match=backend_app.pending_match,
        player_activity=backend_app.player_activity,
        queue_lock=backend_app.queue_lock,
        record_lobby_event=backend_app.record_lobby_event,
        register_socket_event=backend_app.register_socket_event,
        remove_player_session=backend_app.remove_player_session,
        save_queue=backend_app.save_queue,
        save_users=backend_app.save_users,
        select_captains=backend_app.select_captains,
        select_map_from_votes=backend_app.select_map_from_votes,
        set_countdown_paused=backend_app.set_countdown_paused,
        socketio=backend_app.socketio,
        start_live_roll_monitor=backend_app.start_live_roll_monitor,
        update_display_name_service=backend_app.update_display_name_service,
        update_steam_id_service=backend_app.update_steam_id_service,
        upsert_player_activity=backend_app.upsert_player_activity,
        user_has_steam_id=backend_app.user_has_steam_id,
        user_to_group=backend_app.user_to_group,
        users=backend_app.users,
        vote_map_event=backend_app.vote_map_event,
    )


def _with_socket_backend(handler):
    def wrapped(*args, **kwargs):
        backend = _socket_backend_api()
        try:
            return handler(backend, *args, **kwargs)
        except Exception as exc:
            backend.logger.error(
                'Socket handler %s failed before completing: %s',
                getattr(handler, '__name__', 'unknown'),
                exc,
                exc_info=True
            )
            return {'success': False, 'message': f"{getattr(handler, '__name__', 'Socket handler')} failed"}

    return wrapped


def _queue_socket_dependencies(backend, socketio):
    return {
        'socket_events': backend.SOCKET_EVENTS,
        'emit': emit,
        'socketio': socketio,
        'broadcast_queue_update': backend.broadcast_queue_update,
        'logger': backend.logger,
        'queue_lock': backend.queue_lock,
        'matchmaking_queue': backend.matchmaking_queue,
        'save_queue': backend.save_queue,
        'build_queue_payload': backend.build_queue_payload,
    }


def _lobby_socket_dependencies(backend, socketio):
    return {
        'lobbies': backend.lobbies,
        'logger': backend.logger,
        'socketio': socketio,
        'broadcast_queue_update': backend.broadcast_queue_update,
        'broadcast_open_lobbies_update': backend.broadcast_open_lobbies_update,
        'emit_active_lobby_sync': backend.emit_active_lobby_sync,
        'get_username_by_sid': backend.get_username_by_sid,
        'record_lobby_event': backend.record_lobby_event,
    }


def _group_socket_dependencies(backend):
    return {
        'logger': backend.logger,
        'group_lock': backend.group_lock,
        'get_user_group': backend.get_user_group,
        'groups': backend.groups,
        'user_to_group': backend.user_to_group,
        'broadcast_group_update': backend.broadcast_group_update,
        'get_group_payload': backend.get_group_payload,
        'queue_lock': backend.queue_lock,
        'matchmaking_queue': backend.matchmaking_queue,
        'is_user_in_any_lobby': backend.is_user_in_any_lobby,
    }


def _auth_socket_dependencies(backend):
    return {
        'logger': backend.logger,
        'users': backend.users,
        'save_users': backend.save_users,
        'create_access_token': backend.create_access_token,
        'get_user_profile': backend.get_user_profile,
        'request': request,
    }


def _countdown_socket_dependencies(backend, socketio):
    return {
        'logger': backend.logger,
        'socketio': socketio,
        'socket_events': backend.SOCKET_EVENTS,
        'is_countdown_paused': backend.is_countdown_paused,
        'get_username_by_sid': backend.get_username_by_sid,
        'is_admin_user': backend.is_admin_user,
    }


def register_http_routes(app):
    @app.route('/')
    def index():
        backend = _http_backend_api()
        return f"SocketIO backend running. Frontend handled through Vue.js for origins: {', '.join(backend.FRONTEND_ORIGINS)}"

    @app.route('/health', methods=['GET'])
    @app.route('/api/health', methods=['GET'])
    def health():
        backend = _http_backend_api()
        database = backend.get_database_health()
        bridge = backend.get_bridge_health()
        public_bridge = {
            'ok': bool(bridge.get('ok')),
            'url': bridge.get('url'),
        }
        if bridge.get('error'):
            public_bridge['error'] = bridge.get('error')
        ok = bool(database.get('ok')) and bool(bridge.get('ok'))
        payload = {
            'ok': ok,
            'status': 'ok' if ok else 'degraded',
            'service': 'backend',
            'database': database,
            'squadjsBridge': public_bridge,
            'queueSize': sum(len(queue) for queue in backend.matchmaking_queue.values()),
            'lobbyCount': len(backend.lobbies)
        }
        return jsonify(payload), (200 if ok else 503)

    @app.route('/health/live', methods=['GET'])
    @app.route('/api/health/live', methods=['GET'])
    def health_live():
        return jsonify({
            'ok': True,
            'status': 'ok',
            'service': 'backend'
        })

    @app.route('/api/server/players', methods=['GET'])
    @jwt_required()
    def api_server_players():
        backend = _http_backend_api()
        try:
            return jsonify({
                'success': True,
                'players': backend.fetch_connected_server_players_service(backend.squadjs_bridge_request)
            })
        except Exception as e:
            backend.logger.error(f"Error fetching server players from SquadJS bridge: {str(e)}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 502

    @app.route('/api/lobbies/<lobby_id>/server-presence', methods=['GET'])
    @jwt_required()
    def api_lobby_server_presence(lobby_id):
        backend = _http_backend_api()
        try:
            return jsonify({
                'success': True,
                'presence': backend.build_lobby_server_presence(lobby_id, tolerate_bridge_unavailable=True)
            })
        except ValueError as e:
            return jsonify({
                'success': False,
                'message': str(e)
            }), 404
        except Exception as e:
            backend.logger.error(f"Error building server presence for lobby {lobby_id}: {str(e)}")
            return jsonify({
                'success': False,
                'message': str(e)
            }), 502

    @app.route('/api/lobbies/<lobby_id>/join-link', methods=['GET'])
    @jwt_required()
    def api_lobby_join_link(lobby_id):
        backend = _http_backend_api()
        if lobby_id not in backend.lobbies:
            return jsonify({'success': False, 'message': 'Lobby not found'}), 404
        lobby = backend.lobbies.get(lobby_id) or {}
        server_id = lobby.get('server_id')
        if server_id:
            try:
                refreshed_details = backend.get_server_connection_details(server_id=server_id)
                if refreshed_details:
                    lobby['server_details'] = refreshed_details
            except Exception as error:
                backend.logger.warning(
                    "Failed to refresh lobby join details for lobby_id=%s server_id=%s: %s",
                    lobby_id,
                    server_id,
                    error,
                )
        server_details = lobby.get('server_details') or {}
        join_url = backend.build_lobby_join_url(lobby_id)
        backend.logger.info(
            "Lobby join link requested: lobby_id=%s server_name=%s steam_lobby_id=%s connect_address=%s join_url=%s",
            lobby_id,
            server_details.get('serverName')
            or (server_details.get('bridge') or {}).get('serverName')
            or '',
            server_details.get('steamLobbyId')
            or server_details.get('steam_lobby_id')
            or '',
            server_details.get('connectAddress')
            or server_details.get('ip')
            or '',
            join_url or '',
        )
        if not join_url:
            return jsonify({'success': False, 'message': 'Server connection details are not ready yet'}), 409
        return jsonify({
            'success': True,
            'join_url': join_url
        })

    @app.route('/api/matches/history', methods=['GET'])
    @jwt_required()
    def api_match_history():
        backend = _http_backend_api()
        username = get_jwt_identity()
        limit = request.args.get('limit', default=20, type=int) or 20
        limit = max(1, min(limit, 100))
        player = str(request.args.get('player', default='') or '').strip()
        scored_only = str(request.args.get('scored', default='') or '').strip().lower() in {'1', 'true', 'yes'}
        if player == 'me':
            player = username
        return jsonify({
            'success': True,
            'matches': backend.fetch_completed_matches(
                limit=limit,
                username=player or None,
                scored_only=scored_only
            )
        })

    @app.route('/api/servers/test', methods=['POST'])
    @jwt_required()
    def api_servers_test():
        backend = _http_backend_api()
        payload = request.get_json(silent=True) or {}
        try:
            result = backend.test_server_connection(payload)
            return jsonify({'success': True, 'result': result})
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/servers/submit', methods=['POST'])
    @jwt_required()
    def api_servers_submit():
        backend = _http_backend_api()
        username = get_jwt_identity()
        payload = request.get_json(silent=True) or {}
        try:
            server = backend.create_server(payload, submitted_by=username)
            return jsonify({'success': True, 'server': server}), 201
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/admin/diagnostics', methods=['GET'])
    @jwt_required()
    def api_admin_diagnostics():
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403

        return jsonify({
            'success': True,
            'diagnostics': backend.get_admin_diagnostics()
        })

    @app.route('/api/admin/self-mode', methods=['POST'])
    @jwt_required()
    def api_admin_self_mode():
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.can_toggle_admin_mode(username):
            return jsonify({'success': False, 'message': 'Root admin access required'}), 403
        payload = request.get_json(silent=True) or {}
        try:
            profile = backend.set_self_admin_mode(username, bool(payload.get('enabled')))
            return jsonify({'success': True, 'profile': profile})
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/admin/automation', methods=['POST'])
    @jwt_required()
    def api_admin_automation():
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        payload = request.get_json(silent=True) or {}
        try:
            automation = backend.set_automation_mode(payload.get('mode'))
            return jsonify({'success': True, 'automation': automation})
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/admin/servers', methods=['GET'])
    @jwt_required()
    def api_admin_servers():
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        return jsonify({
            'success': True,
            'servers': backend.list_servers(),
            'available': backend.list_available_servers()
        })

    @app.route('/api/admin/servers/test', methods=['POST'])
    @jwt_required()
    def api_admin_servers_test():
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        payload = request.get_json(silent=True) or {}
        try:
            result = backend.test_server_connection(payload)
            return jsonify({'success': True, 'result': result})
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/admin/servers', methods=['POST'])
    @jwt_required()
    def api_admin_servers_create():
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        payload = request.get_json(silent=True) or {}
        try:
            server = backend.create_server(payload, submitted_by=username)
            return jsonify({'success': True, 'server': server}), 201
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/admin/servers/<int:server_id>/health-check', methods=['POST'])
    @jwt_required()
    def api_admin_servers_health_check(server_id):
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        try:
            server, result = backend.run_server_health_check(server_id)
            return jsonify({'success': True, 'server': server, 'result': result})
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/admin/servers/<int:server_id>/enable', methods=['POST'])
    @jwt_required()
    def api_admin_servers_enable(server_id):
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        try:
            server = backend.set_server_enabled(server_id, True)
            return jsonify({'success': True, 'server': server})
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/admin/servers/<int:server_id>/approve', methods=['POST'])
    @jwt_required()
    def api_admin_servers_approve(server_id):
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        try:
            server = backend.approve_server(server_id, username)
            return jsonify({'success': True, 'server': server})
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/admin/servers/<int:server_id>/disable', methods=['POST'])
    @jwt_required()
    def api_admin_servers_disable(server_id):
        backend = _http_backend_api()
        username = get_jwt_identity()
        if not backend.is_admin_user(username):
            return jsonify({'success': False, 'message': 'Admin access required'}), 403
        try:
            server = backend.set_server_enabled(server_id, False)
            return jsonify({'success': True, 'server': server})
        except Exception as error:
            return jsonify({'success': False, 'message': str(error)}), 400

    @app.route('/api/auth/steam/start', methods=['GET'])
    @app.route('/auth/steam/start', methods=['GET'])
    def steam_auth_start():
        backend = _http_backend_api()
        frontend_origin = frontend_origin_from_request(request, backend.FRONTEND_ORIGINS)
        return_to = f"{frontend_origin}/api/auth/steam/callback"
        backend.logger.info(
            "Steam auth start: requested_frontend_origin=%s origin_header=%s resolved_frontend_origin=%s return_to=%s",
            request.args.get('frontend_origin'),
            request.headers.get('Origin'),
            frontend_origin,
            return_to
        )
        state = {
            'nonce': secrets.token_urlsafe(16),
            'frontend_origin': frontend_origin
        }
        login_url = build_steam_login_url(
            return_to=return_to,
            realm=frontend_origin,
            state=state,
            secret_key=backend.app.config['SECRET_KEY']
        )
        return redirect(login_url)

    @app.route('/api/auth/steam/callback', methods=['GET'])
    @app.route('/auth/steam/callback', methods=['GET'])
    def steam_auth_callback():
        backend = _http_backend_api()
        state = load_steam_state(
            request.args.get('state'),
            secret_key=backend.app.config['SECRET_KEY']
        )
        if not state:
            return jsonify({'success': False, 'message': 'Invalid or expired Steam auth state'}), 400

        if request.args.get('openid.mode') != 'id_res':
            return jsonify({'success': False, 'message': 'Steam authentication was cancelled'}), 400

        verification = get_steam_openid_verification_result(request.args)
        backend.logger.info(
            "Steam auth verification result: valid=%s result=%s claimed_id=%s return_to=%s",
            verification.get('valid'),
            verification.get('result'),
            request.args.get('openid.claimed_id'),
            request.args.get('openid.return_to')
        )
        if not verification.get('valid'):
            return jsonify({'success': False, 'message': 'Steam authentication could not be verified'}), 400

        steam_id = extract_steam_id(request.args.get('openid.claimed_id'))
        if not steam_id:
            return jsonify({'success': False, 'message': 'Steam response did not include a valid SteamID64'}), 400

        persona_name = ''
        try:
            persona_name = fetch_steam_persona_name(
                steam_id,
                api_key=getattr(backend, 'STEAM_WEB_API_KEY', '')
            )
        except Exception as error:
            backend.logger.warning(
                "Steam persona lookup failed for steam_id=%s: %s",
                steam_id,
                error
            )

        username, created = get_or_create_steam_user(
            steam_id,
            users=backend.users,
            save_users=backend.save_users,
            persona_name=persona_name
        )
        access_token = backend.create_access_token(identity=username)
        active_lobby_id = backend.find_active_lobby_for_user(username)
        profile = backend.get_user_profile(username)
        frontend_origin = state.get('frontend_origin') or frontend_origin_from_request(request, backend.FRONTEND_ORIGINS)

        backend.logger.info(f"Steam auth successful for {username} ({steam_id}); created={created}")
        return redirect(build_frontend_callback_url(frontend_origin, {
            'success': True,
            'access_token': access_token,
            'username': username,
            'active_lobby': active_lobby_id,
            'profile': profile
        }))

    @_http_backend_api().socketio.on_error_default
    @_http_backend_api().handle_socket_data
    def default_error_handler(e):
        print(f"SocketIO error: {str(e)}")
        print(f"Error type: {type(e)}")
        print(f"Request SID: {request.sid}")
        print(f"Request event: {request.event}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")


def register_socket_routes(socketio):
    @socketio.on('*')
    @_socket_backend_api().handle_socket_data
    def catch_all(event, *args):
        backend = _socket_backend_api()
        backend.logger.info("=== Caught unhandled event ===")
        backend.logger.info(f"Event: {event}")
        backend.logger.info(f"Data: {args}")

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['CONNECTION']['CONNECT'])
    def handle_connect(auth):
        backend = _socket_backend_api()
        return backend.handle_connect_event(
            auth,
            request=request,
            logger=backend.logger,
            emit=emit,
            socket_events=backend.SOCKET_EVENTS,
            decode_token=decode_token,
            is_countdown_paused=backend.is_countdown_paused,
            find_active_lobby_for_user=backend.find_active_lobby_for_user,
            upsert_player_activity=backend.upsert_player_activity,
            join_room=join_room,
            get_user_room=backend.get_user_room
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['CONNECTION']['DISCONNECT'])
    @_socket_backend_api().handle_socket_data
    def handle_disconnect(reason=None):
        backend = _socket_backend_api()
        return backend.handle_disconnect_event(
            reason,
            request=request,
            logger=backend.logger,
            get_username_by_sid=backend.get_username_by_sid,
            remove_player_session=backend.remove_player_session,
            player_activity=backend.player_activity,
            lobbies=backend.lobbies,
            emit=emit,
            matchmaking_queue=backend.matchmaking_queue,
            pending_match=backend.pending_match,
            cancel_pending_match=backend.cancel_pending_match,
            broadcast_queue_update=backend.broadcast_queue_update,
            web_lobby_disconnect_tracking_enabled=backend.WEB_LOBBY_DISCONNECT_TRACKING_ENABLED
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['AUTH']['REGISTER'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def register_socket(backend, data):
        dependencies = _auth_socket_dependencies(backend)
        return backend.register_socket_event(
            data,
            password_auth_enabled=backend.PASSWORD_AUTH_ENABLED,
            max_attempts=backend.AUTH_REGISTER_MAX_ATTEMPTS,
            window_seconds=backend.AUTH_RATE_LIMIT_WINDOW_SECONDS,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['AUTH']['LOGIN'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def login_socket(backend, data):
        dependencies = _auth_socket_dependencies(backend)
        return backend.login_socket_event(
            data,
            password_auth_enabled=backend.PASSWORD_AUTH_ENABLED,
            get_user_record=backend.get_user_record,
            find_active_lobby_for_user=backend.find_active_lobby_for_user,
            lobbies=backend.lobbies,
            upsert_player_activity=backend.upsert_player_activity,
            join_room=join_room,
            get_user_room=backend.get_user_room,
            emit=emit,
            max_attempts=backend.AUTH_LOGIN_MAX_ATTEMPTS,
            window_seconds=backend.AUTH_RATE_LIMIT_WINDOW_SECONDS,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['AUTH']['AUTHENTICATE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_authenticate(backend, data):
        return backend.handle_authenticate_event(
            data,
            request=request,
            logger=backend.logger,
            upsert_player_activity=backend.upsert_player_activity,
            matchmaking_queue=backend.matchmaking_queue,
            join_room=join_room,
            get_user_room=backend.get_user_room,
            build_queue_payload=backend.build_queue_payload,
            emit=emit
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['PROFILE']['STATUS'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_profile_status(backend, data=None):
        return backend.handle_profile_status_event(
            data,
            backend.build_profile_status_service,
            backend.get_user_profile,
            backend.find_active_lobby_for_user,
            backend.logger
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['PROFILE']['UPDATE_STEAM_ID'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_update_steam_id(backend, data=None):
        return backend.handle_update_steam_id_event(
            data,
            backend.update_steam_id_service,
            backend.get_user_record,
            backend.matchmaking_queue,
            backend.is_user_in_any_lobby,
            backend.save_users,
            backend.users,
            backend.get_user_profile,
            backend.logger
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['PROFILE']['UPDATE_DISPLAY_NAME'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_update_display_name(backend, data=None):
        return backend.handle_update_display_name_event(
            data,
            backend.update_display_name_service,
            backend.get_user_record,
            backend.save_users,
            backend.users,
            backend.get_user_profile,
            backend.logger
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['QUEUE']['JOIN'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_join_queue(backend, data):
        dependencies = _queue_socket_dependencies(backend, socketio)
        return backend.handle_join_queue_event(
            data,
            request=request,
            group_lock=backend.group_lock,
            get_user_group=backend.get_user_group,
            user_has_steam_id=backend.user_has_steam_id,
            queue_modes=backend.QUEUE_MODES,
            disabled_queue_modes=backend.disabled_queue_modes,
            pending_match=backend.pending_match,
            lobbies=backend.lobbies,
            upsert_player_activity=backend.upsert_player_activity,
            check_queue_and_start_countdown=backend.check_queue_and_start_countdown,
            has_available_server_capacity=has_available_server_capacity,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['QUEUE']['LEAVE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_leave_queue(backend, data):
        dependencies = _queue_socket_dependencies(backend, socketio)
        return backend.handle_leave_queue_event(
            data,
            pending_match=backend.pending_match,
            cancel_pending_match=backend.cancel_pending_match,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['QUEUE']['STATUS'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_queue_status(backend, data=None):
        return backend.handle_queue_status_event(
            data,
            socket_events=backend.SOCKET_EVENTS,
            emit=emit,
            logger=backend.logger,
            build_queue_payload=backend.build_queue_payload
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['QUEUE']['SEED'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_seed_queue(backend, data=None):
        return backend.handle_seed_queue_event(
            data,
            request=request,
            socket_events=backend.SOCKET_EVENTS,
            socketio=socketio,
            broadcast_queue_update=backend.broadcast_queue_update,
            logger=backend.logger,
            get_username_by_sid=backend.get_username_by_sid,
            is_admin_user=backend.is_admin_user,
            users=backend.users,
            save_users=backend.save_users,
            hash_password=backend.hash_password,
            queue_lock=backend.queue_lock,
            matchmaking_queue=backend.matchmaking_queue,
            queue_modes=backend.QUEUE_MODES,
            upsert_player_activity=backend.upsert_player_activity,
            save_queue=backend.save_queue,
            build_queue_payload=backend.build_queue_payload,
            check_queue_and_start_countdown=backend.check_queue_and_start_countdown,
            get_pending_match=lambda queue_mode: backend.pending_match.get(queue_mode),
            finalize_pending_match=backend.finalize_pending_match,
            group_lock=backend.group_lock,
            groups=backend.groups,
            user_to_group=backend.user_to_group
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['QUEUE']['CLEAR'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_clear_queue(backend, data=None):
        return backend.handle_clear_queue_event(
            data,
            request=request,
            socket_events=backend.SOCKET_EVENTS,
            socketio=socketio,
            broadcast_queue_update=backend.broadcast_queue_update,
            logger=backend.logger,
            get_username_by_sid=backend.get_username_by_sid,
            is_admin_user=backend.is_admin_user,
            queue_lock=backend.queue_lock,
            matchmaking_queue=backend.matchmaking_queue,
            player_activity=backend.player_activity,
            save_queue=backend.save_queue,
            build_queue_payload=backend.build_queue_payload,
            cancel_pending_match=backend.cancel_pending_match,
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['QUEUE']['SET_ENABLED'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_set_queue_enabled(backend, data=None):
        return backend.handle_set_queue_enabled_event(
            data,
            request=request,
            socketio=socketio,
            broadcast_queue_update=backend.broadcast_queue_update,
            logger=backend.logger,
            get_username_by_sid=backend.get_username_by_sid,
            is_admin_user=backend.is_admin_user,
            queue_lock=backend.queue_lock,
            matchmaking_queue=backend.matchmaking_queue,
            queue_modes=backend.QUEUE_MODES,
            disabled_queue_modes=backend.disabled_queue_modes,
            player_activity=backend.player_activity,
            save_queue=backend.save_queue,
            build_queue_payload=backend.build_queue_payload,
            cancel_pending_match=backend.cancel_pending_match,
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['QUEUE']['ACCEPT_MATCH'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_accept_match(backend, data=None):
        return backend.handle_accept_match_event(
            data,
            request=request,
            logger=backend.logger,
            queue_lock=backend.queue_lock,
            pending_match=backend.pending_match,
            get_username_by_sid=backend.get_username_by_sid,
            get_match_accept_payload=backend.get_match_accept_payload,
            broadcast_queue_update=backend.broadcast_queue_update,
            finalize_pending_match=backend.finalize_pending_match
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['CREATE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_create(backend, data=None):
        dependencies = _group_socket_dependencies(backend)
        return backend.handle_group_create_event(
            data,
            request=request,
            generate_group_code=backend.generate_group_code,
            upsert_player_activity=backend.upsert_player_activity,
            join_room=join_room,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['JOIN'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_join(backend, data=None):
        dependencies = _group_socket_dependencies(backend)
        return backend.handle_group_join_event(
            data,
            request=request,
            max_lobby_players=backend.MAX_LOBBY_PLAYERS,
            upsert_player_activity=backend.upsert_player_activity,
            join_room=join_room,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['LEAVE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_leave(backend, data=None):
        dependencies = _group_socket_dependencies(backend)
        return backend.handle_group_leave_event(
            data,
            leave_room=leave_room,
            save_queue=backend.save_queue,
            broadcast_queue_update=backend.broadcast_queue_update,
            pending_match=backend.pending_match,
            cancel_pending_match=backend.cancel_pending_match,
            lobbies=backend.lobbies,
            player_activity=backend.player_activity,
            get_player_sids=backend.get_player_sids,
            socketio=socketio,
            broadcast_open_lobbies_update=backend.broadcast_open_lobbies_update,
            emit_active_lobby_sync=backend.emit_active_lobby_sync,
            select_captains=backend.select_captains,
            record_lobby_event=backend.record_lobby_event,
            release_server_allocation=backend.release_server_allocation,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['KICK'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_kick(backend, data=None):
        dependencies = _group_socket_dependencies(backend)
        return backend.handle_group_kick_event(
            data,
            socketio=socketio,
            socket_events=backend.SOCKET_EVENTS,
            get_player_sids=backend.get_player_sids,
            leave_room=leave_room,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['TRANSFER'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_transfer(backend, data=None):
        dependencies = _group_socket_dependencies(backend)
        return backend.handle_group_transfer_event(
            data,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['STATUS'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_status(backend, data=None):
        return backend.handle_group_status_event(
            data,
            logger=backend.logger,
            group_lock=backend.group_lock,
            get_user_group=backend.get_user_group,
            get_group_payload=backend.get_group_payload
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['SEED'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_seed(backend, data=None):
        return backend.handle_group_seed_event(
            data,
            request=request,
            logger=backend.logger,
            group_lock=backend.group_lock,
            get_user_group=backend.get_user_group,
            queue_lock=backend.queue_lock,
            matchmaking_queue=backend.matchmaking_queue,
            is_user_in_any_lobby=backend.is_user_in_any_lobby,
            groups=backend.groups,
            user_to_group=backend.user_to_group,
            users=backend.users,
            save_users=backend.save_users,
            hash_password=backend.hash_password,
            upsert_player_activity=backend.upsert_player_activity,
            get_group_payload=backend.get_group_payload,
            broadcast_group_update=backend.broadcast_group_update,
            get_username_by_sid=backend.get_username_by_sid,
            is_admin_user=backend.is_admin_user,
            max_group_members=max(
                int(config.get('team_size') or 1)
                for config in backend.QUEUE_MODES.values()
            )
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['QUEUE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_queue(backend, data=None):
        return backend.handle_group_queue_event(
            data,
            logger=backend.logger,
            group_lock=backend.group_lock,
            get_user_group=backend.get_user_group,
            groups=backend.groups,
            queue_modes=backend.QUEUE_MODES,
            user_has_steam_id=backend.user_has_steam_id,
            is_user_in_any_lobby=backend.is_user_in_any_lobby,
            queue_lock=backend.queue_lock,
            matchmaking_queue=backend.matchmaking_queue,
            pending_match=backend.pending_match,
            disabled_queue_modes=backend.disabled_queue_modes,
            lobbies=backend.lobbies,
            upsert_player_activity=backend.upsert_player_activity,
            save_queue=backend.save_queue,
            broadcast_queue_update=backend.broadcast_queue_update,
            check_queue_and_start_countdown=backend.check_queue_and_start_countdown,
            build_queue_payload=backend.build_queue_payload,
            has_available_server_capacity=has_available_server_capacity
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['GROUP']['UNQUEUE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_group_unqueue(backend, data=None):
        return backend.handle_group_unqueue_event(
            data,
            logger=backend.logger,
            group_lock=backend.group_lock,
            get_user_group=backend.get_user_group,
            groups=backend.groups,
            queue_lock=backend.queue_lock,
            matchmaking_queue=backend.matchmaking_queue,
            player_activity=backend.player_activity,
            save_queue=backend.save_queue,
            broadcast_queue_update=backend.broadcast_queue_update,
            build_queue_payload=backend.build_queue_payload
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['OPEN_LOBBIES']['STATUS'])
    @_socket_backend_api().handle_socket_data
    def handle_open_lobbies_status(data=None):
        backend = _socket_backend_api()
        return backend.handle_open_lobbies_status_event(
            backend.get_open_lobbies,
            backend.get_active_lobbies,
            backend.logger
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['COUNTDOWN']['STATUS'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_countdown_status(backend, data=None):
        return backend.handle_countdown_status_event(
            backend.is_countdown_paused,
            backend.logger
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['COUNTDOWN']['TOGGLE_PAUSE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_toggle_countdown_pause(backend, data=None):
        dependencies = _countdown_socket_dependencies(backend, socketio)
        return backend.handle_toggle_countdown_pause_event(
            data,
            request=request,
            set_countdown_paused=backend.set_countdown_paused,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['JOIN'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_join_lobby(backend, data=None):
        return backend.handle_join_lobby_event(
            data,
            request=request,
            logger=backend.logger,
            lobbies=backend.lobbies,
            matchmaking_queue=backend.matchmaking_queue,
            queue_lock=backend.queue_lock,
            MAX_LOBBY_PLAYERS=backend.MAX_LOBBY_PLAYERS,
            get_user_group=backend.get_user_group,
            groups=backend.groups,
            user_to_group=backend.user_to_group,
            save_queue=backend.save_queue,
            join_room=join_room,
            upsert_player_activity=backend.upsert_player_activity,
            get_user_room=backend.get_user_room,
            get_player_groups=backend.get_player_groups,
            emit=emit,
            emit_active_lobby_sync=backend.emit_active_lobby_sync,
            broadcast_queue_update=backend.broadcast_queue_update,
            broadcast_open_lobbies_update=backend.broadcast_open_lobbies_update,
            assign_teams=backend.assign_teams,
            select_captains=backend.select_captains,
            is_admin_user=backend.is_admin_user
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['SPECTATE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_spectate_lobby(backend, data=None):
        payload = {
            **(data or {}),
            'username': backend.get_username_by_sid(request.sid),
            'spectate': True
        }
        return backend.handle_join_lobby_event(
            payload,
            request=request,
            logger=backend.logger,
            lobbies=backend.lobbies,
            matchmaking_queue=backend.matchmaking_queue,
            queue_lock=backend.queue_lock,
            MAX_LOBBY_PLAYERS=backend.MAX_LOBBY_PLAYERS,
            get_user_group=backend.get_user_group,
            groups=backend.groups,
            user_to_group=backend.user_to_group,
            save_queue=backend.save_queue,
            join_room=join_room,
            upsert_player_activity=backend.upsert_player_activity,
            get_user_room=backend.get_user_room,
            get_player_groups=backend.get_player_groups,
            emit=emit,
            emit_active_lobby_sync=backend.emit_active_lobby_sync,
            broadcast_queue_update=backend.broadcast_queue_update,
            broadcast_open_lobbies_update=backend.broadcast_open_lobbies_update,
            assign_teams=backend.assign_teams,
            select_captains=backend.select_captains,
            is_admin_user=backend.is_admin_user
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['LEAVE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_leave_lobby(backend, data=None):
        dependencies = _lobby_socket_dependencies(backend, socketio)
        return backend.handle_leave_lobby_event(
            data,
            request=request,
            player_activity=backend.player_activity,
            get_player_sids=backend.get_player_sids,
            emit=emit,
            select_captains=backend.select_captains,
            release_server_allocation=backend.release_server_allocation,
            **dependencies
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['DELETE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_delete_lobby(backend, data=None):
        return backend.handle_delete_lobby_event(
            data,
            request=request,
            logger=backend.logger,
            lobbies=backend.lobbies,
            socketio=socketio,
            get_username_by_sid=backend.get_username_by_sid,
            is_admin_user=backend.is_admin_user,
            player_activity=backend.player_activity,
            get_player_sids=backend.get_player_sids,
            emit_active_lobby_sync=backend.emit_active_lobby_sync,
            broadcast_queue_update=backend.broadcast_queue_update,
            broadcast_open_lobbies_update=backend.broadcast_open_lobbies_update,
            record_lobby_event=backend.record_lobby_event,
            release_server_allocation=backend.release_server_allocation
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['GET_DATA'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_get_lobby_data(backend, data=None):
        return backend.handle_get_lobby_data_event(
            data,
            lobbies=backend.lobbies,
            emit=emit,
            socket_events=backend.SOCKET_EVENTS
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['SERVER_PRESENCE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_lobby_server_presence(backend, data=None):
        return backend.handle_server_presence_event(
            data,
            logger=backend.logger,
            build_lobby_server_presence=backend.build_lobby_server_presence
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['FORCE_LIVE_READY'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_force_live_ready(backend, data=None):
        return backend.handle_force_live_ready_event(
            data,
            request=request,
            logger=backend.logger,
            lobbies=backend.lobbies,
            socketio=socketio,
            get_username_by_sid=backend.get_username_by_sid,
            is_admin_user=backend.is_admin_user,
            select_map_from_votes_fn=backend.select_map_from_votes,
            start_live_roll_monitor=backend.start_live_roll_monitor,
            get_server_connection_details=backend.get_server_connection_details,
            get_selected_map_team_labels=backend.get_selected_map_team_labels,
            ready_grace_seconds=backend.LIVE_ROLL_READY_GRACE_SECONDS,
            record_lobby_event=backend.record_lobby_event,
            save_runtime_state=backend.save_runtime_state
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['VOTE_MAP'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_vote_map(backend, data=None):
        return backend.vote_map_event(
            data,
            request=request,
            logger=backend.logger,
            lobbies=backend.lobbies,
            socketio=socketio,
            get_username_by_sid=backend.get_username_by_sid
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['SKIP_PHASE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_skip_phase(backend, data=None):
        return backend.handle_skip_phase_event(
            data,
            request=request,
            logger=backend.logger,
            lobbies=backend.lobbies,
            socketio=socketio,
            select_map_from_votes_fn=backend.select_map_from_votes,
            start_live_roll_monitor=backend.start_live_roll_monitor,
            get_server_connection_details=backend.get_server_connection_details,
            get_selected_map_team_labels=backend.get_selected_map_team_labels,
            ready_grace_seconds=backend.LIVE_ROLL_READY_GRACE_SECONDS,
            get_username_by_sid=backend.get_username_by_sid,
            is_admin_user=backend.is_admin_user,
            record_lobby_event=backend.record_lobby_event
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['PREV_PHASE'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_prev_phase(backend, data=None):
        return backend.handle_prev_phase_event(
            data,
            request=request,
            logger=backend.logger,
            dev_mode=backend.DEV_MODE,
            lobbies=backend.lobbies,
            socketio=socketio,
            get_username_by_sid=backend.get_username_by_sid,
            is_admin_user=backend.is_admin_user,
            record_lobby_event=backend.record_lobby_event
        )

    @socketio.on(_socket_backend_api().SOCKET_EVENTS['LOBBY']['START'])
    @_socket_backend_api().handle_socket_data
    @_with_socket_backend
    def handle_start_lobby(backend, data=None):
        return backend.handle_start_lobby_event(
            data,
            lobbies=backend.lobbies,
            emit=emit,
            socket_events=backend.SOCKET_EVENTS
        )
