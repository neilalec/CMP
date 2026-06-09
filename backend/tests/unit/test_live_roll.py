from services.live_roll import (
    round_result_has_layer_data,
    get_round_result_layer,
    get_live_roll_readiness,
    get_live_roll_retry_state,
    get_team_swap_retry_state,
    get_live_broadcast_retry_state,
    mark_live_roll_change_attempt,
    mark_live_broadcast_attempt,
    mark_team_swap_attempt,
    round_result_matches_selected_map,
    should_finalize_live_lobby,
    should_team_swap_block_live_roll,
    schedule_live_broadcast
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


def test_live_roll_not_ready_below_ninety_percent_after_grace_period():
    readiness = get_live_roll_readiness(
        {'server_details_provided_at': 1000},
        build_presence(total_players=60, connected_players=53, aligned_players=53),
        ready_ratio=0.9,
        ready_grace_seconds=600,
        now=2000
    )

    assert readiness['ready'] is False
    assert readiness['requiredAfterGrace'] == 54


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
