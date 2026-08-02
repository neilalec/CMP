import sqlite3

from services.state_persistence import (
    init_runtime_state_tables,
    load_active_groups,
    load_active_lobbies,
    save_runtime_state,
)


def build_connection():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    return conn


def test_runtime_state_round_trips_lobbies_and_groups():
    conn = build_connection()

    def get_db_connection():
        return conn

    init_runtime_state_tables(get_db_connection)

    save_runtime_state(
        get_db_connection,
        {
            'lobby_1': {
                'players': ['alice', 'bob'],
                'teams': {'team1': ['alice'], 'team2': ['bob']},
                'step': 3,
                'selected_map': 'Kokan Skirmish v1',
                'map_votes': {'alice': 'Kokan Skirmish v1'},
                'disconnected_players': {'bob'},
                'live_roll_team_swap_attempts': {'bob': 1234},
            }
        },
        {
            'ABC123': {
                'code': 'ABC123',
                'leader': 'alice',
                'members': ['alice', 'bob']
            }
        },
        now=1000
    )

    lobbies = load_active_lobbies(get_db_connection)
    groups = load_active_groups(get_db_connection)

    assert lobbies['lobby_1']['players'] == ['alice', 'bob']
    assert lobbies['lobby_1']['teams'] == {'team1': ['alice'], 'team2': ['bob']}
    assert lobbies['lobby_1']['disconnected_players'] == {'bob'}
    assert lobbies['lobby_1']['live_roll_team_swap_attempts'] == {'bob': 1234}
    assert groups['ABC123']['members'] == ['alice', 'bob']


def test_runtime_state_snapshot_removes_deleted_lobbies_and_groups():
    conn = build_connection()

    def get_db_connection():
        return conn

    init_runtime_state_tables(get_db_connection)
    save_runtime_state(
        get_db_connection,
        {'lobby_1': {'players': ['alice']}},
        {'ABC123': {'code': 'ABC123', 'leader': 'alice', 'members': ['alice']}},
        now=1000
    )
    save_runtime_state(get_db_connection, {}, {}, now=1001)

    assert load_active_lobbies(get_db_connection) == {}
    assert load_active_groups(get_db_connection) == {}
