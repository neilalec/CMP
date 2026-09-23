"""Offline periodic WARDOGS observation and private update delivery."""

from datetime import datetime, timezone
import time

import app as backend_app
import app_core
from flask_jwt_extended import create_access_token

from services.game_server_adapter import AdapterError, AdapterErrorKind
from services.game_server_contracts import (
    FactionScore, PlayerSnapshot, ScoreTick, ServerPlayer, ServerStatus,
)
from services.server_registry import (
    approve_server, create_server, get_server_by_id, set_server_enabled,
    update_server_record,
)
from services.wardogs_allocation import allocate_wardogs_server_for_lobby, cleanup_wardogs_lobby
from services.wardogs_live import WardogsLivePoller, wardogs_lobby_room
from services.wardogs_lobby import (
    clear_wardogs_observation, get_wardogs_lobby, read_wardogs_lobby,
    save_wardogs_lobby,
)


SECRET = 'offline-registry-key'


def lobby(lobby_id='live-lobby'):
    return {'id': lobby_id, 'phase': 'assembling', 'serverId': None,
            'factions': [
                {'id': faction, 'commanderId': None, 'groups': [{
                    'id': f'{faction}-solo', 'type': 'solo', 'leaderId': None,
                    'players': [{'id': name, 'displayName': name.title(),
                                 'steamId': steam_id, 'registered': True,
                                 'rosterStatus': 'active', 'ready': False}],
                }]}
                for faction, name, steam_id in (
                    ('valkyra', 'alice', '76561198000000001'),
                    ('lonestar', 'bob', '76561198000000002'),
                    ('manticore', 'carol', '76561198000000003'),
                )]}


def allocated_server(monkeypatch, lobby_id='live-lobby'):
    save_wardogs_lobby(app_core.get_db_connection, lobby(lobby_id))
    monkeypatch.setenv('CMP_WARDOGS_RCON_LIVE_TEST', 'offline-credential')
    server = create_server(app_core.get_db_connection, SECRET, {
        'game_type': 'wardogs', 'display_name': f'Test {lobby_id}',
        'bridge_url': 'https://example.test',
        'wdrcon_secret_env': 'CMP_WARDOGS_RCON_LIVE_TEST',
    }, submitted_by='admin')
    approve_server(app_core.get_db_connection, SECRET, server['id'], 'admin')
    update_server_record(app_core.get_db_connection, SECRET, server['id'],
                         status='healthy', last_health_status='healthy',
                         last_health_check_at=time.time())
    set_server_enabled(app_core.get_db_connection, SECRET, server['id'], True)
    assert allocate_wardogs_server_for_lobby(app_core.get_db_connection, lobby_id) == server['id']
    return server['id']


class FakeSocketIO:
    def __init__(self):
        self.events = []

    def emit(self, event, payload, *, room):
        self.events.append((event, payload, room))


class FakeAdapter:
    def __init__(self, now):
        self.now = now
        self.calls = []
        self.fails = False

    def get_status(self):
        self.calls.append('status')
        if self.fails:
            raise AdapterError(AdapterErrorKind.TRANSPORT_FAILURE)
        return ServerStatus(
            self.now, server_name='Observed WARDOGS server', map_id='Bakurani',
            current_players=3, max_players=100,
            faction_scores=(FactionScore('Valkyra', 7), FactionScore('Lonestar', 9),
                            FactionScore('Manticore', 8)),
            rotation_now_index=0, rotation_next_index=1,
            score_tick=ScoreTick(24, 18, 30),
        )

    def get_players(self):
        self.calls.append('players')
        return PlayerSnapshot((
            ServerPlayer('76561198000000001', 'Aster server name', 'Lonestar'),
            ServerPlayer('76561198000000003', 'Carol server name', 'Manticore'),
            ServerPlayer('76561198000000099', 'Unexpected', 'Valkyra'),
        ), self.now)


def poller(adapter, socketio=None):
    return WardogsLivePoller(
        socketio=socketio or FakeSocketIO(), get_db_connection=app_core.get_db_connection,
        get_server_by_id=lambda server_id: get_server_by_id(
            app_core.get_db_connection, server_id, SECRET),
        adapter_factory=lambda _server: adapter, logger=backend_app.logger,
        now=lambda: adapter.now,
    )


def test_poll_reconciles_planned_and_observed_without_result_inference(monkeypatch):
    allocated_server(monkeypatch)
    now = datetime.now(timezone.utc)
    adapter = FakeAdapter(now)
    worker = poller(adapter)
    worker.poll_once()
    state = read_wardogs_lobby(get_wardogs_lobby(app_core.get_db_connection, 'live-lobby'), now=now)
    assert adapter.calls == ['status', 'players']
    assert state['observation']['state'] == 'fresh'
    assert state['server']['name'] == 'Observed WARDOGS server'
    assert state['configuration']['map'] == 'Bakurani'
    assert state['serverStatus']['currentPlayers'] == 3
    assert state['serverStatus']['maxPlayers'] == 100
    assert state['serverStatus']['rotation'] == {'nowIndex': 0, 'nextIndex': 1}
    assert state['serverStatus']['scoreTick']['current'] == 24
    assert state['scores'] == {'valkyra': 7, 'lonestar': 9, 'manticore': 8}
    alice = state['factions'][0]['groups'][0]['players'][0]
    bob = state['factions'][1]['groups'][0]['players'][0]
    carol = state['factions'][2]['groups'][0]['players'][0]
    assert (alice['plannedFactionId'], alice['observedFactionId'], alice['alignmentState']) == (
        'valkyra', 'lonestar', 'mismatch')
    assert bob['connected'] is False
    assert (carol['connected'], carol['alignmentState']) == (True, 'aligned')
    assert [player['displayName'] for player in state['unexpectedPlayers']] == ['Unexpected']
    assert state['result']['status'] == 'unconfirmed'
    assert len(worker.socketio.events) == 1
    assert worker.socketio.events[0][2] == wardogs_lobby_room('live-lobby')
    worker.poll_once()
    assert len(worker.socketio.events) == 1  # unchanged data is quiet


def test_failure_preserves_last_read_and_allocation_then_recovers(monkeypatch):
    server_id = allocated_server(monkeypatch)
    adapter = FakeAdapter(datetime.now(timezone.utc))
    worker = poller(adapter)
    worker.poll_once()
    adapter.fails = True
    worker.poll_once()
    state = read_wardogs_lobby(get_wardogs_lobby(app_core.get_db_connection, 'live-lobby'))
    assert state['observation']['state'] == 'stale'
    assert state['observation']['pollState'] == 'error'
    assert state['scores']['lonestar'] == 9
    assert state['factions'][0]['groups'][0]['players'][0]['observedFactionId'] == 'lonestar'
    assert get_server_by_id(app_core.get_db_connection, server_id, SECRET)['current_lobby_id'] == 'live-lobby'
    with app_core.get_db_connection() as conn:
        assert conn.execute("SELECT state FROM server_allocations WHERE server_id=?",
                            (server_id,)).fetchone()[0] == 'reserved'
    assert len(worker.socketio.events) == 2
    worker.poll_once()
    assert len(worker.socketio.events) == 2
    adapter.fails = False
    worker.poll_once()
    assert read_wardogs_lobby(get_wardogs_lobby(app_core.get_db_connection, 'live-lobby'))['observation']['state'] == 'fresh'


def test_waiting_squad_cleanup_and_restart_eligibility(monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby('waiting'))
    save_wardogs_lobby(app_core.get_db_connection, lobby('squad-owned'))
    squad = create_server(app_core.get_db_connection, SECRET, {
        'game_type': 'squad', 'display_name': 'Squad only',
        'bridge_url': 'http://127.0.0.1:9876',
    }, submitted_by='admin')
    update_server_record(app_core.get_db_connection, SECRET, squad['id'],
                         current_lobby_id='squad-owned')
    server_id = allocated_server(monkeypatch)
    adapter = FakeAdapter(datetime.now(timezone.utc))
    worker = poller(adapter)
    worker.poll_once()
    assert adapter.calls == ['status', 'players']
    clear_wardogs_observation()  # process restart; persisted allocation remains
    recovered = poller(adapter)
    assert read_wardogs_lobby(get_wardogs_lobby(app_core.get_db_connection, 'live-lobby'))['observation']['state'] == 'none'
    recovered.poll_once()
    assert adapter.calls == ['status', 'players', 'status', 'players']
    assert read_wardogs_lobby(get_wardogs_lobby(app_core.get_db_connection, 'live-lobby'))['observation']['state'] == 'fresh'
    assert cleanup_wardogs_lobby(app_core.get_db_connection, 'live-lobby') == server_id
    recovered.poll_once()
    assert len(adapter.calls) == 4
    assert get_server_by_id(app_core.get_db_connection, server_id, SECRET)['current_lobby_id'] is None


def test_first_worker_failure_is_unavailable_and_does_not_release_allocation(monkeypatch):
    server_id = allocated_server(monkeypatch)
    adapter = FakeAdapter(datetime.now(timezone.utc))
    adapter.fails = True
    worker = poller(adapter)
    worker.poll_once()
    state = read_wardogs_lobby(get_wardogs_lobby(app_core.get_db_connection, 'live-lobby'))
    assert state['observation']['state'] == 'unavailable'
    assert state['observation']['pollState'] == 'error'
    assert state['scores'] == {'valkyra': None, 'lonestar': None, 'manticore': None}
    assert get_server_by_id(app_core.get_db_connection, server_id, SECRET)['current_lobby_id'] == 'live-lobby'


def test_one_worker_guard_prevents_duplicate_active_polling():
    class StopLoop(Exception):
        pass

    class StoppingSocket(FakeSocketIO):
        def sleep(self, _seconds):
            worker.run()  # A second start while the first worker is active exits.
            raise StopLoop

    adapter = FakeAdapter(datetime.now(timezone.utc))
    worker = poller(adapter, socketio=StoppingSocket())
    calls = []
    worker.poll_once = lambda: calls.append('cycle')
    try:
        worker.run()
    except StopLoop:
        pass
    assert calls == ['cycle']
    assert worker._running is False


def test_socket_updates_require_lobby_membership(flask_app, monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: username == 'admin')
    alice = backend_app.socketio.test_client(flask_app)
    outsider = backend_app.socketio.test_client(flask_app)
    admin = backend_app.socketio.test_client(flask_app)
    with flask_app.app_context():
        alice_token = create_access_token(identity='alice')
        outsider_token = create_access_token(identity='outsider')
        admin_token = create_access_token(identity='admin')
    assert alice.emit('wardogs_lobby_subscribe',
                      {'lobbyId': 'live-lobby', 'token': alice_token}, callback=True) == {'success': True}
    assert outsider.emit('wardogs_lobby_subscribe',
                         {'lobbyId': 'live-lobby', 'token': outsider_token}, callback=True) == {'success': False}
    assert admin.emit('wardogs_lobby_subscribe',
                      {'lobbyId': 'live-lobby', 'token': admin_token}, callback=True) == {'success': True}
    alice.get_received()
    outsider.get_received()
    admin.get_received()
    backend_app.socketio.emit('wardogs_lobby_update', {'lobbyId': 'live-lobby'},
                              room=wardogs_lobby_room('live-lobby'))
    assert any(item['name'] == 'wardogs_lobby_update' for item in alice.get_received())
    assert any(item['name'] == 'wardogs_lobby_update' for item in admin.get_received())
    assert not any(item['name'] == 'wardogs_lobby_update' for item in outsider.get_received())
    alice.disconnect()
    outsider.disconnect()
    admin.disconnect()
