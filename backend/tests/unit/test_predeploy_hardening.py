import app_core
from services.bridge import build_lobby_server_presence
from services.history import build_admin_diagnostics
from services.queue import check_queue_and_start_countdown, get_server_availability
from sockets.lobby import handle_delete_lobby_event, handle_skip_phase_event
from app_core import (
    AutomationCommandBlocked,
    broadcast_server_message,
    set_automation_mode,
)


class DummyLogger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)

    def warning(self, message):
        pass

    def info(self, message):
        pass


class DummyRequest:
    sid = 'sid-1'


class DummySocketIO:
    def __init__(self):
        self.emits = []
        self.server = self
        self.left_rooms = []

    def emit(self, event, payload=None, **kwargs):
        self.emits.append((event, payload, kwargs))

    def leave_room(self, sid, room):
        self.left_rooms.append((sid, room))


class DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_predeploy_server_busy_prevents_new_match_acceptance():
    started = []

    check_queue_and_start_countdown(
        queue_lock=DummyLock(),
        pending_match={'skirmish': None},
        matchmaking_queue={'skirmish': ['p1', 'p2']},
        queue_modes={'skirmish': {'max_players': 2}},
        lobbies={'active': {'step': 4, 'server_id': 1}},
        server_capacity=1,
        start_match_acceptance=lambda players, queue_mode: started.append((queue_mode, players))
    )

    assert started == []
    assert get_server_availability(
        {'active': {'step': 4, 'server_id': 1}},
        {'skirmish': None},
        server_capacity=1
    )['reason'] == 'server_in_use'


def test_predeploy_squadjs_unavailable_returns_degraded_presence_shape():
    presence = build_lobby_server_presence(
        'lobby_1',
        {
            'lobby_1': {
                'players': ['sam'],
                'teams': {'team1': ['sam'], 'team2': []},
            }
        },
        get_user_profile=lambda username: {'steam_id': '76561198000000001'},
        bridge_request=lambda path: (_ for _ in ()).throw(RuntimeError('SquadJS offline')),
        tolerate_bridge_unavailable=True
    )

    assert presence['bridgeAvailable'] is False
    assert presence['bridgeError'] == 'SquadJS offline'
    assert presence['unauthorizedPlayers'] == []
    assert presence['players'][0]['connected'] is False


def test_predeploy_admin_players_bypass_lobby_enforcement():
    def bridge_request(path):
        assert path == '/players'
        return {
            'players': [
                {
                    'steamID': '76561198000000001',
                    'name': 'neil',
                    'teamID': 2
                },
                {
                    'steamID': '76561198000000002',
                    'name': 'extra',
                    'teamID': 1
                }
            ]
        }

    presence = build_lobby_server_presence(
        'lobby_1',
        {
            'lobby_1': {
                'players': ['neil'],
                'teams': {'team1': ['neil'], 'team2': []},
            }
        },
        get_user_profile=lambda username: {'steam_id': '76561198000000001'},
        bridge_request=bridge_request,
        is_bypass_steam_id=lambda steam_id: steam_id == '76561198000000001',
    )

    assert presence['players'][0]['adminBypass'] is True
    assert presence['players'][0]['teamAligned'] is True
    assert presence['mismatched'] == []
    assert presence['unauthorizedPlayers'] == [
        {
            'steam_id': '76561198000000002',
            'eosID': None,
            'serverName': 'extra',
            'actualTeamId': 1,
            'actualSquadId': None
        }
    ]


def test_predeploy_admin_team_bypass_can_be_disabled_for_live_testing():
    def bridge_request(path):
        assert path == '/players'
        return {
            'players': [
                {
                    'steamID': '76561198000000001',
                    'name': 'neil',
                    'teamID': 2
                }
            ]
        }

    presence = build_lobby_server_presence(
        'lobby_1',
        {
            'lobby_1': {
                'players': ['neil'],
                'teams': {'team1': ['neil'], 'team2': []},
            }
        },
        get_user_profile=lambda username: {'steam_id': '76561198000000001'},
        bridge_request=bridge_request,
        is_bypass_steam_id=lambda steam_id: steam_id == '76561198000000001',
        is_team_bypass_steam_id=lambda steam_id: False,
    )

    assert presence['players'][0]['adminBypass'] is True
    assert presence['players'][0]['teamBypass'] is False
    assert presence['players'][0]['teamAligned'] is False
    assert presence['mismatched'] == ['neil']
    assert presence['unauthorizedPlayers'] == []


def test_admin_self_mode_controls_cmp_team_bypass(monkeypatch):
    steam_id = '76561198000000001'
    monkeypatch.setattr(app_core, 'ADMIN_STEAM_IDS', {steam_id})
    monkeypatch.setattr(app_core, 'ADMIN_TEAM_ENFORCEMENT_BYPASS_ENABLED', True)
    monkeypatch.setattr(app_core, 'save_users', lambda: None)

    original_users = dict(app_core.users)
    app_core.users.clear()
    app_core.users['neil'] = {'steam_id': steam_id}

    try:
        profile = app_core.set_self_admin_mode('neil', True)
        assert profile['is_admin'] is True
        assert profile['can_toggle_admin'] is True
        assert app_core.is_admin_steam_id(steam_id) is True
        assert app_core.is_team_enforcement_bypass_steam_id(steam_id) is True

        profile = app_core.set_self_admin_mode('neil', False)
        assert profile['is_admin'] is False
        assert profile['can_toggle_admin'] is True
        assert app_core.is_admin_steam_id(steam_id) is False
        assert app_core.is_team_enforcement_bypass_steam_id(steam_id) is False
    finally:
        app_core.users.clear()
        app_core.users.update(original_users)


def test_predeploy_monitor_mode_blocks_rcon_writes():
    set_automation_mode('monitor')
    try:
        try:
            broadcast_server_message('test')
        except AutomationCommandBlocked as error:
            assert 'monitor' in str(error)
        else:
            raise AssertionError('Expected monitor mode to block RCON writes')
    finally:
        set_automation_mode('on')


def test_predeploy_admin_only_lobby_mutations_are_server_side_guarded():
    lobbies = {
        'lobby_1': {
            'players': ['sam'],
            'teams': {'team1': ['sam'], 'team2': []},
            'step': 2,
            'selected_map': None,
        }
    }

    delete_response = handle_delete_lobby_event(
        {'lobby_id': 'lobby_1'},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        socketio=DummySocketIO(),
        get_username_by_sid=lambda sid: 'neil',
        is_admin_user=lambda username: False,
        player_activity={},
        get_player_sids=lambda username: [],
        emit_active_lobby_sync=lambda username, lobby_id: None,
        broadcast_queue_update=lambda: None,
        broadcast_open_lobbies_update=lambda: None,
    )

    skip_response = handle_skip_phase_event(
        {'lobby_id': 'lobby_1'},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        select_map_from_votes_fn=lambda lobby: ('Logar Valley Skirmish v1', {}),
        socketio=DummySocketIO(),
        start_live_roll_monitor=lambda lobby_id: None,
        get_server_connection_details=lambda server_id=None: {},
        get_selected_map_team_labels=lambda selected_map, server_id=None: {},
        ready_grace_seconds=300,
        get_username_by_sid=lambda sid: 'neil',
        is_admin_user=lambda username: False,
    )

    assert delete_response == {'success': False, 'message': 'Admin access required'}
    assert skip_response == {'success': False, 'message': 'Admin access required'}
    assert 'lobby_1' in lobbies
    assert lobbies['lobby_1']['step'] == 2


def test_predeploy_admin_delete_releases_server_and_notifies_users():
    socketio = DummySocketIO()
    released = []
    synced = []
    queue_updates = []
    lobby_updates = []
    lobbies = {
        'lobby_1': {
            'players': ['sam'],
            'teams': {'team1': ['sam'], 'team2': []},
            'step': 4,
            'server_id': 1,
        }
    }

    response = handle_delete_lobby_event(
        {'lobby_id': 'lobby_1'},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        socketio=socketio,
        get_username_by_sid=lambda sid: 'admin',
        is_admin_user=lambda username: True,
        player_activity={'sam': {'lobby_id': 'lobby_1', 'status': 'in_lobby'}},
        get_player_sids=lambda username: ['sid-sam'],
        emit_active_lobby_sync=lambda username, lobby_id: synced.append((username, lobby_id)),
        broadcast_queue_update=lambda: queue_updates.append(True),
        broadcast_open_lobbies_update=lambda: lobby_updates.append(True),
        release_server_allocation=lambda lobby_id, reason: released.append((lobby_id, reason)),
    )

    assert response['success'] is True
    assert 'lobby_1' not in lobbies
    assert released == [('lobby_1', 'admin_deleted')]
    assert socketio.left_rooms == [('sid-sam', 'lobby_1')]
    assert synced == [('sam', None)]
    assert queue_updates == [True]
    assert lobby_updates == [True]


def test_predeploy_diagnostics_exposes_dependency_and_server_availability():
    diagnostics = build_admin_diagnostics(
        get_database_health=lambda: {'ok': True},
        get_bridge_health=lambda: {'ok': False, 'error': 'bridge offline'},
        get_eos_runtime_status=lambda: {'configured': False},
        get_server_connection_details=lambda: (_ for _ in ()).throw(RuntimeError('SquadJS offline')),
        fetch_latest_round_result=lambda: (_ for _ in ()).throw(RuntimeError('SquadJS offline')),
        fetch_lobby_audit_events=lambda limit=20: [],
        get_history_counts=lambda: {'total': 0},
        lobbies={'active': {'step': 4, 'players': ['sam'], 'selected_map': 'Logar Valley Skirmish v1'}},
        queue_modes={'skirmish': {'label': 'Skirmish', 'max_players': 40, 'team_size': 20}},
        matchmaking_queue={'skirmish': ['neil']},
        pending_match={'skirmish': None},
        servers=[{'id': 1}],
        automation_control={'mode': 'monitor', 'rconWritesEnabled': False},
        admin_steam_ids={'76561198000000001'}
    )

    assert diagnostics['bridge']['ok'] is False
    assert diagnostics['server']['bridgeAvailable'] is False
    assert diagnostics['latestRoundResult']['error'] == 'SquadJS offline'
    assert diagnostics['automation']['mode'] == 'monitor'
    assert diagnostics['adminSteamIds'] == ['76561198000000001']
    assert diagnostics['serverAvailability']['available'] is False
    assert diagnostics['serverAvailability']['reason'] == 'server_in_use'
