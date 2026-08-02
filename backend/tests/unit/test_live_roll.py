from services.live_roll import (
    start_live_roll_monitor,
    round_result_has_layer_data,
    get_round_result_layer,
    get_live_roll_readiness,
    get_live_roll_retry_state,
    get_team_swap_retry_state,
    get_live_broadcast_retry_state,
    get_live_match_timer_status,
    get_live_started_at_from_layer_status,
    has_selected_layer_started_after_roll,
    mark_live_roll_change_attempt,
    mark_live_roll_broadcast_attempt,
    mark_live_broadcast_attempt,
    mark_team_swap_attempt,
    round_result_matches_selected_map,
    get_unauthorized_connected_players,
    has_live_roll_ready_override,
    should_end_live_match,
    should_finalize_live_lobby,
    should_team_swap_block_live_roll,
    schedule_live_broadcast,
    has_live_layer_transitioned_away,
    build_unresolved_round_result
)
from services.bridge import (
    get_server_layer_status,
    layer_info_matches_selected_map,
    layer_matches_selected_map
)


def build_presence(total_players, connected_players, aligned_players=None):
    if aligned_players is None:
        aligned_players = connected_players
    players = [
        {
            'username': f'player_{index}',
            'connected': index < connected_players,
            'teamAligned': index < aligned_players
        }
        for index in range(total_players)
    ]
    return {
        'players': players,
        'connected': [row['username'] for row in players if row['connected']],
        'aligned': [row['username'] for row in players if row['connected'] and row['teamAligned']],
        'mismatched': [row['username'] for row in players if row['connected'] and not row['teamAligned']],
        'missing': [row['username'] for row in players if not row['connected']]
    }


def test_live_roll_ready_when_all_players_connected_immediately():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=60),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=1000
    )

    assert readiness['ready'] is True
    assert readiness['allConnected'] is True
    assert readiness['connectedCount'] == 60
    assert readiness['alignedCount'] == 60


def test_live_roll_waits_for_grace_period_at_ninety_percent():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=54, aligned_players=54),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=1599
    )

    assert readiness['ready'] is False
    assert readiness['requiredAfterGrace'] == 54
    assert readiness['remainingGraceSeconds'] == 1


def test_live_roll_ready_after_grace_period_at_ninety_percent():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=54, aligned_players=54),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=1600
    )

    assert readiness['ready'] is True
    assert readiness['graceReady'] is True
    assert readiness['forceReady'] is True


def test_live_roll_force_ready_after_grace_period_below_threshold():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=53, aligned_players=53),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=2000
    )

    assert readiness['ready'] is True
    assert readiness['forceReady'] is True
    assert readiness['graceReady'] is False
    assert readiness['requiredAfterGrace'] == 54


def test_live_roll_force_timer_does_not_ignore_wrong_side_players():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=53, aligned_players=52),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=2000
    )

    assert readiness['ready'] is False
    assert readiness['forceReady'] is True
    assert readiness['connectedPlayersAligned'] is False
    assert readiness['connectedCount'] == 53
    assert readiness['alignedCount'] == 52


def test_live_roll_not_ready_below_threshold_before_force_timer():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=53, aligned_players=53),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=1599
    )

    assert readiness['ready'] is False
    assert readiness['forceReady'] is False


def test_live_roll_remaining_grace_uses_server_details_timestamp():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=1),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=1123
    )

    assert readiness['remainingGraceSeconds'] == 477


def test_mark_live_roll_change_attempt_tracks_attempt_count_and_time():
    lobby = {}

    mark_live_roll_change_attempt(lobby, {'ok': True}, now=1234)

    assert lobby['live_roll_command_sent'] is True
    assert lobby['live_roll_change_attempts'] == 1
    assert lobby['live_roll_last_change_attempt_at'] == 1234
    assert lobby['live_roll_command_response'] == {'ok': True}


def test_mark_live_roll_broadcast_attempt_tracks_success():
    lobby = {}

    mark_live_roll_broadcast_attempt(lobby, {'ok': True}, now=1234)

    assert lobby['live_roll_broadcast_sent'] is True
    assert lobby['live_roll_broadcast_attempts'] == 1
    assert lobby['live_roll_broadcast_last_attempt_at'] == 1234
    assert lobby['live_roll_broadcast_response'] == {'ok': True}
    assert lobby['live_roll_broadcast_error'] is None


def test_mark_live_roll_broadcast_attempt_tracks_failure():
    lobby = {}

    mark_live_roll_broadcast_attempt(lobby, error=RuntimeError('rcon down'), now=1234)

    assert lobby['live_roll_broadcast_attempts'] == 1
    assert lobby['live_roll_broadcast_last_attempt_at'] == 1234
    assert lobby['live_roll_broadcast_error'] == 'rcon down'


def test_live_broadcast_retry_state_allows_first_attempt():
    retry_state = get_live_broadcast_retry_state({}, retry_seconds=5, now=1000)

    assert retry_state['shouldRetry'] is True
    assert retry_state['remainingSeconds'] == 0


def test_mark_live_broadcast_attempt_tracks_success():
    lobby = {}

    mark_live_broadcast_attempt(lobby, {'ok': True}, now=1234)

    assert lobby['live_broadcast_sent'] is True
    assert lobby['live_broadcast_attempts'] == 1
    assert lobby['live_broadcast_last_attempt_at'] == 1234
    assert lobby['live_broadcast_response'] == {'ok': True}
    assert lobby['live_broadcast_error'] is None


def test_schedule_live_broadcast_sets_ready_time():
    lobby = {}

    schedule_live_broadcast(lobby, delay_seconds=10, now=1000)

    assert lobby['live_broadcast_ready_at'] == 1010


def test_selected_layer_start_requires_match_started_after_roll_command():
    lobby = {
        'live_roll_last_change_attempt_at': 2000
    }
    layer_status = {
        'currentMatches': True,
        'serverInfo': {
            'matchStartTime': '1970-01-01T00:30:00Z'
        }
    }

    assert has_selected_layer_started_after_roll(lobby, layer_status) is False


def test_selected_layer_start_accepts_match_started_after_roll_command():
    lobby = {
        'live_roll_last_change_attempt_at': 2000
    }
    layer_status = {
        'currentMatches': True,
        'serverInfo': {
            'matchStartTime': '1970-01-01T00:33:30Z'
        }
    }

    assert has_selected_layer_started_after_roll(lobby, layer_status) is True


def test_live_started_at_uses_server_match_start_time():
    layer_status = {
        'currentMatches': True,
        'serverInfo': {
            'matchStartTime': '1970-01-01T00:33:30Z',
            'playtimeSeconds': 30
        }
    }

    assert get_live_started_at_from_layer_status(layer_status, now=2100) == 2010


def test_live_started_at_falls_back_to_playtime_when_match_start_missing():
    layer_status = {
        'currentMatches': True,
        'serverInfo': {
            'playtimeSeconds': 30
        }
    }

    assert get_live_started_at_from_layer_status(layer_status, now=2100) == 2070


def test_live_broadcast_retry_state_waits_until_ready_time():
    retry_state = get_live_broadcast_retry_state(
        {
            'live_broadcast_sent': False,
            'live_broadcast_ready_at': 1010
        },
        retry_seconds=5,
        now=1005
    )

    assert retry_state['shouldRetry'] is False
    assert retry_state['remainingSeconds'] == 5


def test_live_broadcast_retry_state_allows_attempt_after_ready_time():
    retry_state = get_live_broadcast_retry_state(
        {
            'live_broadcast_sent': False,
            'live_broadcast_ready_at': 1010
        },
        retry_seconds=5,
        now=1010
    )

    assert retry_state['shouldRetry'] is True
    assert retry_state['remainingSeconds'] == 0


def test_live_broadcast_retry_state_waits_after_failure():
    retry_state = get_live_broadcast_retry_state(
        {
            'live_broadcast_sent': False,
            'live_broadcast_attempts': 1,
            'live_broadcast_last_attempt_at': 1000
        },
        retry_seconds=5,
        now=1003
    )

    assert retry_state['shouldRetry'] is False
    assert retry_state['remainingSeconds'] == 2


def test_live_broadcast_retry_state_stops_after_success():
    retry_state = get_live_broadcast_retry_state(
        {
            'live_broadcast_sent': True,
            'live_broadcast_attempts': 1,
            'live_broadcast_last_attempt_at': 1000
        },
        retry_seconds=5,
        now=1010
    )

    assert retry_state['shouldRetry'] is False
    assert retry_state['remainingSeconds'] == 0


def test_live_roll_retry_state_waits_for_retry_window():
    retry_state = get_live_roll_retry_state(
        {
            'live_roll_change_attempts': 1,
            'live_roll_last_change_attempt_at': 1000
        },
        retry_seconds=15,
        now=1010
    )

    assert retry_state['shouldRetry'] is False
    assert retry_state['remainingSeconds'] == 5


def test_live_roll_retry_state_allows_retry_after_retry_window():
    retry_state = get_live_roll_retry_state(
        {
            'live_roll_change_attempts': 1,
            'live_roll_last_change_attempt_at': 1000
        },
        retry_seconds=15,
        now=1015
    )

    assert retry_state['shouldRetry'] is True
    assert retry_state['remainingSeconds'] == 0


def test_live_roll_not_ready_when_connected_players_are_on_wrong_team():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=60, aligned_players=58),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=1000
    )

    assert readiness['ready'] is False
    assert readiness['connectedCount'] == 60
    assert readiness['alignedCount'] == 58


def test_mark_team_swap_attempt_tracks_per_player_time():
    lobby = {}

    mark_team_swap_attempt(lobby, 'player_1', now=1200)

    assert lobby['live_roll_team_swap_attempts']['player_1'] == 1200


def test_team_swap_retry_state_waits_for_retry_window():
    retry_state = get_team_swap_retry_state(
        {'live_roll_team_swap_attempts': {'player_1': 1000}},
        'player_1',
        retry_seconds=10,
        now=1005
    )

    assert retry_state['shouldRetry'] is False
    assert retry_state['remainingSeconds'] == 5


def test_team_swap_blocks_before_live_roll_command_is_sent():
    assert should_team_swap_block_live_roll({
        'live_roll_command_sent': False,
        'live_roll_done': False
    }) is True


def test_team_swap_does_not_block_after_live_roll_command_is_sent():
    assert should_team_swap_block_live_roll({
        'live_roll_command_sent': True,
        'live_roll_done': False
    }) is False


def test_team_swap_does_not_block_after_lobby_is_live():
    assert should_team_swap_block_live_roll({
        'live_roll_command_sent': True,
        'live_roll_done': True
    }) is False


def test_live_roll_ready_override_matches_connected_username():
    assert has_live_roll_ready_override(
        enabled=True,
        connected_usernames=['Neil'],
        override_username='neil'
    ) is True


def test_live_roll_ready_override_matches_connected_steam_id():
    assert has_live_roll_ready_override(
        enabled=True,
        connected_steam_ids=['76561198124553635'],
        override_steam_id='76561198124553635'
    ) is True


def test_live_roll_ready_override_requires_flag():
    assert has_live_roll_ready_override(
        enabled=False,
        connected_usernames=['neil'],
        override_username='neil'
    ) is False


def test_round_result_matches_selected_map_from_winner_layer():
    assert round_result_matches_selected_map(
        {
            'winner': {'layer': 'Chora Skirmish v1'}
        },
        'Chora Skirmish v1'
    ) is True


def test_get_round_result_layer_returns_none_for_missing_side():
    assert get_round_result_layer(None) is None


def test_round_result_matches_selected_map_handles_null_winner_and_loser():
    assert round_result_matches_selected_map(
        {
            'winner': None,
            'loser': None,
            'layer': 'Tallil Outskirts Skirmish v2'
        },
        'Tallil Outskirts Skirmish v2'
    ) is True


def test_hotdrop_selected_map_requires_exact_hotdrop_layer():
    assert layer_matches_selected_map(
        'HotDrop_Fallujah',
        'HotDrop_Fallujah'
    ) is True


def test_hotdrop_layer_matches_when_log_uses_space_separator():
    assert layer_matches_selected_map(
        'HotDrop SumariBala',
        'HotDrop_SumariBala'
    ) is True


def test_vanilla_layer_does_not_match_hotdrop_layer():
    assert layer_matches_selected_map(
        'Fallujah Skirmish v1',
        'HotDrop_Fallujah'
    ) is False


def test_hotdrop_layer_info_matches_from_classname():
    assert layer_info_matches_selected_map(
        {
            'name': 'Fallujah',
            'layerClassname': 'HotDrop_Fallujah',
            'classname': 'HotDrop_Fallujah'
        },
        'HotDrop_Fallujah'
    ) is True


def test_vanilla_layer_info_does_not_match_hotdrop_layer():
    assert layer_info_matches_selected_map(
        {
            'name': 'Fallujah Skirmish v1',
            'layerClassname': 'Fallujah Skirmish v1'
        },
        'HotDrop_Fallujah'
    ) is False


def test_server_layer_status_matches_hotdrop_from_raw_rcon_layer():
    def bridge_request(path):
        assert path == '/server'
        return {
            'currentLayerRaw': 'HotDrop_Narva',
            'currentLayer': 'Narva',
            'nextLayerRaw': None
        }

    status = get_server_layer_status('HotDrop_Narva', bridge_request)

    assert status['currentMatches'] is True
    assert status['nextMatches'] is False


def test_round_result_has_no_layer_data_when_end_payload_is_sparse():
    assert round_result_has_layer_data({
        'winner': None,
        'loser': None,
        'time': '2026.06.04-20.00.00'
    }) is False


def test_should_finalize_live_lobby_after_live_started():
    assert should_finalize_live_lobby(
        {'live_started_at': 1000},
        {
            'observedAt': 1010,
            'winner': {'layer': 'Chora Skirmish v1'}
        },
        'Chora Skirmish v1'
    ) is True


def test_should_finalize_live_lobby_accepts_s3o_scoreboard_after_map_selected():
    assert should_finalize_live_lobby(
        {
            'server_details_provided_at': 1000,
            'live_started_at': 1030
        },
        {
            'observedAt': 1015,
            'winner': {'layer': 'S3O_36_Harju_AAS_v3'}
        },
        'S3O_36_Harju_AAS_v3'
    ) is True


def test_should_not_finalize_live_lobby_from_scoreboard_before_map_selected():
    assert should_finalize_live_lobby(
        {
            'server_details_provided_at': 1000,
            'live_started_at': 1030
        },
        {
            'observedAt': 995,
            'winner': {'layer': 'S3O_36_Harju_AAS_v3'}
        },
        'S3O_36_Harju_AAS_v3'
    ) is False


def test_should_finalize_live_lobby_with_sparse_round_end_after_live_started():
    assert should_finalize_live_lobby(
        {'live_started_at': 1000},
        {
            'observedAt': 1010,
            'winner': None,
            'loser': None,
            'time': '2026.06.04-20.00.00'
        },
        'Tallil Outskirts Skirmish v2'
    ) is True


def test_should_finalize_hotdrop_round_when_log_layer_uses_spaces():
    assert should_finalize_live_lobby(
        {'live_started_at': 1000},
        {
            'observedAt': 1010,
            'winner': {
                'layer': 'HotDrop SumariBala',
                'inferred': True
            },
            'loser': None,
            'partial': True
        },
        'HotDrop_SumariBala'
    ) is True


def test_live_match_timer_never_ends_match_from_app_clock():
    assert should_end_live_match(
        {
            'selected_map': 'Logar Valley Skirmish v1',
            'live_roll_done': True,
            'live_started_at': 1000
        },
        max_seconds=3600,
        now=4600
    ) is False
    assert should_end_live_match(
        {
            'selected_map': 'Logar Valley Skirmish v1',
            'live_roll_done': True,
            'live_started_at': 1000
        },
        max_seconds=3600,
        now=4599
    ) is False


def test_live_match_timer_observes_server_playtime_without_ending():
    status = get_live_match_timer_status(
        {
            'selected_map': 'Logar Valley Skirmish v1',
            'live_roll_done': True,
            'live_started_at': 1000
        },
        max_seconds=3600,
        layer_status={
            'currentMatches': True,
            'serverInfo': {
                'playtimeSeconds': 3600
            }
        },
        now=1005
    )

    assert status['shouldEnd'] is False
    assert status['elapsedSeconds'] == 3600
    assert status['source'] == 'server_playtime'
    assert status['remainingSeconds'] is None


def test_live_match_timer_does_not_fall_back_to_cmp_wall_clock():
    status = get_live_match_timer_status(
        {
            'selected_map': 'Logar Valley Skirmish v1',
            'live_roll_done': True,
            'live_started_at': 1000
        },
        max_seconds=3600,
        layer_status={
            'currentMatches': True,
            'serverInfo': {}
        },
        now=4599
    )

    assert status['shouldEnd'] is False
    assert status['elapsedSeconds'] is None
    assert status['source'] is None


def test_live_match_timer_ignores_non_skirmish_layers():
    assert should_end_live_match(
        {
            'selected_map': 'S3O_36_Harju_AAS_v3',
            'live_roll_done': True,
            'live_started_at': 1000
        },
        max_seconds=3600,
        now=5000
    ) is False


def test_live_match_timer_does_not_refire_after_end_sent():
    assert should_end_live_match(
        {
            'selected_map': 'Logar Valley Skirmish v1',
            'live_roll_done': True,
            'live_started_at': 1000,
            'live_match_end_sent': True
        },
        max_seconds=3600,
        now=5000
    ) is False


def test_live_layer_transitioned_away_detects_known_non_matching_current_layer():
    assert has_live_layer_transitioned_away(
        {'live_roll_done': True},
        {'currentMatches': False, 'currentLayer': 'Narva_Skirmish_v1'}
    ) is True
    assert has_live_layer_transitioned_away(
        {'live_roll_done': True},
        {'currentMatches': True, 'currentLayer': 'Logar_Skirmish_v1'}
    ) is False


def test_unresolved_round_result_marks_admin_end_draw_fallback():
    result = build_unresolved_round_result(
        {'live_started_at': 1000},
        'Logar_Skirmish_v1',
        source='test',
        now=4600
    )

    assert result['draw'] is True
    assert result['unresolved'] is True
    assert result['partial'] is True
    assert result['winner'] is None
    assert result['loser'] is None
    assert result['layer'] == 'Logar_Skirmish_v1'
    assert result['observedAt'] == 4600


def test_get_unauthorized_connected_players_returns_kickable_players_only():
    assert get_unauthorized_connected_players({
        'unauthorizedPlayers': [
            {'serverName': 'neil', 'steam_id': '76561198124553635'},
            {'serverName': 'unknown'},
            {'serverName': 'eos-player', 'eosID': 'EOS123'}
        ]
    }) == [
        {'serverName': 'neil', 'steam_id': '76561198124553635'},
        {'serverName': 'eos-player', 'eosID': 'EOS123'}
    ]


def test_finalized_lobby_releases_server_immediately_and_expires(monkeypatch):
    import services.live_roll as live_roll_module

    class DummyServer:
        def __init__(self):
            self.left_rooms = []

        def leave_room(self, sid, room):
            self.left_rooms.append((sid, room))

    class DummySocketIO:
        def __init__(self):
            self.emits = []
            self.server = DummyServer()

        def emit(self, event, payload=None, **kwargs):
            self.emits.append((event, payload, kwargs))

    monkeypatch.setattr(live_roll_module.eventlet, 'spawn', lambda fn, *args, **kwargs: fn(*args, **kwargs))

    lobby_id = 'lobby_final'
    lobbies = {
        lobby_id: {
            'players': ['alice'],
            'teams': {'team1': ['alice'], 'team2': []},
            'step': 3,
            'selected_map': 'OutoftheBox_Tallil',
            'server_id': 1,
            'server_details_provided_at': 1000,
        }
    }
    socketio = DummySocketIO()
    events = []
    saved_matches = []
    released = []
    kicked = []
    synced = []
    saved_runtime = []
    player_activity = {
        'alice': {
            'status': 'in_lobby',
            'lobby_id': lobby_id,
            'last_seen': 1000,
        }
    }

    def build_presence(_lobby_id, tolerate_bridge_unavailable=False):
        return {
            'players': [
                {
                    'username': 'alice',
                    'steam_id': '76561198000000001',
                    'eosID': 'EOS_ALICE',
                    'connected': True,
                    'teamAligned': True,
                }
            ],
            'connected': ['alice'],
            'connectedSteamIds': ['76561198000000001'],
            'aligned': ['alice'],
            'mismatched': [],
            'missing': [],
            'unauthorizedPlayers': [],
        }

    start_live_roll_monitor(
        lobby_id,
        lobbies,
        socketio,
        build_lobby_server_presence=build_presence,
        pause_aware_sleep=lambda _seconds: None,
        broadcast_server_message=lambda _message: {'ok': True},
        change_server_to_selected_map=lambda _selected_map: {'ok': True},
        set_next_server_map=lambda _selected_map: {'ok': True},
        force_player_to_expected_team=lambda _steam_id: {'ok': True},
        get_server_layer_status=lambda _selected_map: {'currentMatches': True},
        get_server_connection_details=lambda: {},
        fetch_latest_round_result=lambda: {
            'observedAt': 1100,
            'layer': 'OutoftheBox_Tallil',
            'winner': {'team': '1', 'tickets': 10},
            'loser': {'team': '2', 'tickets': 0},
        },
        record_lobby_event=lambda _lobby_id, event_type, payload=None, created_at=None: events.append((event_type, payload)),
        save_completed_match=lambda _lobby_id, lobby, completed_at: saved_matches.append((_lobby_id, completed_at, dict(lobby))),
        kick_player_from_server=lambda player_id, reason, lobby_id=None: kicked.append((player_id, reason, lobby_id)),
        release_server_allocation=lambda _lobby_id, reason=None: released.append((_lobby_id, reason)),
        broadcast_open_lobbies_update=lambda: None,
        broadcast_queue_update=lambda: None,
        player_activity=player_activity,
        get_player_sids=lambda username: [f'{username}-sid'],
        emit_active_lobby_sync=lambda username, active_lobby_id: synced.append((username, active_lobby_id)),
        finalized_cleanup_delay_seconds=300,
        save_runtime_state=lambda: saved_runtime.append(True),
    )

    assert saved_matches
    assert released[0] == (lobby_id, 'match_completed')
    assert released == [(lobby_id, 'match_completed')]
    assert lobby_id not in lobbies
    assert player_activity['alice']['status'] == 'authenticated'
    assert 'lobby_id' not in player_activity['alice']
    assert synced == [('alice', None)]
    assert socketio.server.left_rooms == [('alice-sid', lobby_id)]
    assert kicked == [('EOS_ALICE', 'Match complete.', lobby_id)]
    assert 'server_released' in [event_type for event_type, _payload in events]
    assert 'finalized_lobby_expired' in [event_type for event_type, _payload in events]
    assert saved_runtime
