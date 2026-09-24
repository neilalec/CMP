from threading import RLock
from datetime import datetime, timezone

import pytest

from services.wardogs_dev import (
    SYNTHETIC_IDS, autoaccept_synthetic, clear_simulation,
    decorate_read_model, fill_queue, set_simulated,
)
from services.wardogs_live import poll_interval_seconds
from services.wardogs_lobby import build_wardogs_read_model
from services.game_server_contracts import PlayerSnapshot, ServerPlayer, ServerStatus


def test_fill_around_real_player_is_bounded_deterministic_and_uses_matcher():
    users = {'neil': {'steam_id': '76561198000000001'}}
    queues = {'wardogs_beta9': ['neil']}
    calls = []
    kwargs = dict(
        enabled=True, username='neil', users=users, matchmaking_queue=queues,
        queue_lock=RLock(), upsert_player_activity=lambda *args, **kw: None,
        save_users=lambda: calls.append('users'), save_queue=lambda: calls.append('queue'),
        check_queue_and_start_countdown=lambda: calls.append('matcher'),
        pending_match={'wardogs_beta9': None}, broadcast_queue_update=lambda: None)
    seeded = fill_queue(**kwargs)
    assert seeded == list(SYNTHETIC_IDS[:8])
    assert queues['wardogs_beta9'] == ['neil', *seeded]
    assert len(set(queues['wardogs_beta9'])) == 9
    assert all(users[name]['wardogs_dev_synthetic'] for name in seeded)
    assert calls == ['users', 'queue', 'matcher']
    assert fill_queue(**kwargs) == []
    assert calls[-1] == 'matcher'


def test_dev_fill_gate_and_real_user_requirement():
    kwargs = dict(username='neil', users={'neil': {}}, matchmaking_queue={'wardogs_beta9': ['neil']},
                  queue_lock=RLock(), upsert_player_activity=lambda *args, **kw: None,
                  save_users=lambda: None, save_queue=lambda: None,
                  check_queue_and_start_countdown=lambda: None,
                  pending_match={}, broadcast_queue_update=lambda: None)
    with pytest.raises(PermissionError):
        fill_queue(enabled=False, **kwargs)
    kwargs['matchmaking_queue']['wardogs_beta9'].clear()
    with pytest.raises(ValueError, match='Join the WARDOGS'):
        fill_queue(enabled=True, **kwargs)


def test_only_dev_wardogs_synthetics_autoaccept():
    pending = {'game_type': 'wardogs', 'queue_mode': 'wardogs_beta9',
               'players': ['neil', SYNTHETIC_IDS[0]],
               'accepted': {'neil': False, SYNTHETIC_IDS[0]: False}}
    from services.wardogs_dev import SYNTHETIC_STEAM_IDS
    users = {SYNTHETIC_IDS[0]: {'seeded_player': True,
                                'steam_id': SYNTHETIC_STEAM_IDS[SYNTHETIC_IDS[0]]}}
    assert autoaccept_synthetic(pending, enabled=False, users=users) == ()
    assert pending['accepted'][SYNTHETIC_IDS[0]] is False
    assert autoaccept_synthetic(pending, enabled=True, users=users) == (SYNTHETIC_IDS[0],)
    assert pending['accepted']['neil'] is False
    pending['game_type'] = 'squad'
    pending['accepted'][SYNTHETIC_IDS[0]] = False
    assert autoaccept_synthetic(pending, enabled=True, users=users) == ()


def test_overlay_preserves_real_observation_and_planned_roster():
    planned = {'id': 'dev-test', 'phase': 'assembling', 'serverId': None,
               'factions': [{'id': faction, 'commanderId': None, 'groups': [
                   {'id': f'{faction}-solo', 'type': 'solo', 'leaderId': None,
                    'players': [{'id': name, 'displayName': name, 'steamId': None,
                                 'registered': True, 'rosterStatus': 'active', 'ready': False}]}
               ]} for faction, name in (
                   ('valkyra', 'neil'), ('lonestar', SYNTHETIC_IDS[0]),
                   ('manticore', 'other'))]}
    planned['factions'][0]['groups'][0]['players'][0]['steamId'] = '76561198000000001'
    now = datetime.now(timezone.utc)
    observation = PlayerSnapshot((ServerPlayer('76561198000000001', 'Neil', 'Valkyra'),), now)
    status = ServerStatus(now, server_name='Real WARDOGS server', current_players=1, max_players=100)
    original = build_wardogs_read_model(planned, players=observation, status=status, now=now)
    with pytest.raises(PermissionError):
        set_simulated(planned, True, dev_mode=False)
    set_simulated(planned, True, dev_mode=True)
    model = decorate_read_model(planned, build_wardogs_read_model(
        planned, players=observation, status=status, now=now), dev_mode=True)
    player = model['factions'][1]['groups'][0]['players'][0]
    assert player['devSimulated'] is True
    assert player['connected'] is True
    assert player['plannedFactionId'] == player['observedFactionId'] == 'lonestar'
    assert model['observation'] == original['observation']
    assert model['serverStatus'] == original['serverStatus']
    real = model['factions'][0]['groups'][0]['players'][0]
    assert real['connected'] is True and real['observedFactionId'] == 'valkyra'
    assert real.get('devSimulated') is None
    assert decorate_read_model(planned, build_wardogs_read_model(
        planned, players=observation, status=status, now=now), dev_mode=False) == original
    assert planned['factions'][1]['groups'][0]['players'][0]['id'] == SYNTHETIC_IDS[0]
    clear_simulation()


def test_poll_cadence_is_safe_and_environment_specific():
    assert poll_interval_seconds(dev_mode=False) == 20
    assert poll_interval_seconds(dev_mode=True) == 5
    assert poll_interval_seconds('2', dev_mode=True) == 2
    with pytest.raises(ValueError):
        poll_interval_seconds('0.01', dev_mode=True)
