import sqlite3

from services.history import (
    fetch_completed_matches,
    fetch_lobby_audit_events,
    get_history_counts,
    init_history_tables,
    record_lobby_event,
    save_completed_match
)


def build_connection():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    return conn


def test_record_lobby_event_and_fetch_recent_events():
    conn = build_connection()

    def get_db_connection():
        return conn

    init_history_tables(get_db_connection)
    record_lobby_event(get_db_connection, 'lobby_1', 'lobby_created', {'players': ['a', 'b']}, created_at=1000)

    events = fetch_lobby_audit_events(get_db_connection, lobby_id='lobby_1', limit=10)

    assert len(events) == 1
    assert events[0]['event_type'] == 'lobby_created'
    assert events[0]['payload']['players'] == ['a', 'b']


def test_save_completed_match_and_fetch_history():
    conn = build_connection()

    def get_db_connection():
        return conn

    init_history_tables(get_db_connection)
    save_completed_match(
        get_db_connection,
        'lobby_2',
        {
            'created_at': 1000,
            'live_started_at': 1100,
            'selected_map': 'Chora Skirmish v1',
            'players': ['a', 'b'],
            'teams': {'team1': ['a'], 'team2': ['b']},
            'server_details': {'serverName': '4K War Server'},
            'round_result': {
                'winner': {'faction': 'USA', 'tickets': '12'},
                'loser': {'faction': 'RGF', 'tickets': '0'}
            }
        },
        completed_at=1200
    )

    matches = fetch_completed_matches(get_db_connection, limit=10)
    counts = get_history_counts(get_db_connection)

    assert len(matches) == 1
    assert matches[0]['selected_map'] == 'Chora Skirmish v1'
    assert matches[0]['server_name'] == '4K War Server'
    assert matches[0]['round_result']['winner']['faction'] == 'USA'
    assert counts['completedMatches'] == 1
