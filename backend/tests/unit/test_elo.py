import sqlite3

from services.elo import (
    apply_elo_for_completed_match,
    build_elo_update_payload,
    init_elo_tables,
)


def build_connection():
    conn = sqlite3.connect(':memory:')
    conn.row_factory = sqlite3.Row
    return conn


def test_equal_rating_match_uses_provisional_k_factor():
    users = {
        'alice': {'elo_rating': 1000, 'elo_matches': 0},
        'bob': {'elo_rating': 1000, 'elo_matches': 0},
    }

    payload = build_elo_update_payload({
        'teams': {'team1': ['alice'], 'team2': ['bob']},
        'round_result': {
            'winner': {'team': '1', 'tickets': 42},
            'loser': {'team': '2', 'tickets': 0},
        },
    }, users)

    assert payload['result'] == 'team1_win'
    assert payload['expectedScores'] == {'team1': 0.5, 'team2': 0.5}
    assert payload['updates'][0]['newRating'] == 1020
    assert payload['updates'][1]['newRating'] == 980


def test_underdog_win_moves_more_than_favourite_win():
    users = {
        'alice': {'elo_rating': 900, 'elo_matches': 12},
        'bob': {'elo_rating': 1100, 'elo_matches': 12},
    }

    payload = build_elo_update_payload({
        'teams': {'team1': ['alice'], 'team2': ['bob']},
        'round_result': {
            'winner': {'team': '1', 'tickets': 32},
            'loser': {'team': '2', 'tickets': 0},
        },
    }, users)

    alice_update = payload['updates'][0]
    bob_update = payload['updates'][1]
    assert alice_update['kFactor'] == 32
    assert alice_update['delta'] > 16
    assert bob_update['delta'] < -16


def test_draw_moves_ratings_toward_each_other():
    users = {
        'alice': {'elo_rating': 1200, 'elo_matches': 12},
        'bob': {'elo_rating': 1000, 'elo_matches': 12},
    }

    payload = build_elo_update_payload({
        'teams': {'team1': ['alice'], 'team2': ['bob']},
        'round_result': {'draw': True},
    }, users)

    assert payload['result'] == 'draw'
    assert payload['updates'][0]['delta'] < 0
    assert payload['updates'][1]['delta'] > 0


def test_apply_elo_for_completed_match_only_applies_once():
    conn = build_connection()

    def get_db_connection():
        return conn

    init_elo_tables(get_db_connection)
    users = {
        'alice': {'elo_rating': 1000, 'elo_matches': 0},
        'bob': {'elo_rating': 1000, 'elo_matches': 0},
    }
    saved = []
    lobby = {
        'teams': {'team1': ['alice'], 'team2': ['bob']},
        'round_result': {
            'winner': {'team': '1', 'tickets': 42},
            'loser': {'team': '2', 'tickets': 0},
        },
    }

    first = apply_elo_for_completed_match(
        get_db_connection,
        'lobby_1',
        lobby,
        users,
        lambda: saved.append(True),
        applied_at=1200,
    )
    second = apply_elo_for_completed_match(
        get_db_connection,
        'lobby_1',
        lobby,
        users,
        lambda: saved.append(True),
        applied_at=1201,
    )

    assert first is not None
    assert second is None
    assert users['alice']['elo_rating'] == 1020
    assert users['alice']['elo_matches'] == 1
    assert users['bob']['elo_rating'] == 980
    assert users['bob']['elo_matches'] == 1
    assert saved == [True]


def test_dev_solo_elo_smoke_allows_configured_player_to_lose_against_synthetic_opponent():
    conn = build_connection()

    def get_db_connection():
        return conn

    init_elo_tables(get_db_connection)
    users = {
        'neil': {'elo_rating': 1000, 'elo_matches': 0},
    }
    saved = []
    lobby = {
        'players': ['neil'],
        'teams': {'team1': ['neil'], 'team2': []},
        'round_result': {
            'winner': {'team': '2', 'tickets': 1},
            'loser': {'team': '1', 'tickets': 0},
        },
    }

    payload = apply_elo_for_completed_match(
        get_db_connection,
        'lobby_solo_loss',
        lobby,
        users,
        lambda: saved.append(True),
        applied_at=1200,
        dev_solo_smoke_enabled=True,
        dev_solo_smoke_username='neil',
    )

    assert payload is not None
    assert payload['result'] == 'team2_win'
    assert payload['devSoloEloSmoke']['username'] == 'neil'
    assert payload['devSoloEloSmoke']['syntheticOpponent'] == '__dev_solo_elo_opponent__'
    assert users['neil']['elo_rating'] == 980
    assert users['neil']['elo_matches'] == 1
    assert '__dev_solo_elo_opponent__' not in users
    assert saved == [True]


def test_dev_solo_elo_smoke_does_not_apply_when_disabled():
    conn = build_connection()

    def get_db_connection():
        return conn

    init_elo_tables(get_db_connection)
    users = {
        'neil': {'elo_rating': 1000, 'elo_matches': 0},
    }
    lobby = {
        'players': ['neil'],
        'teams': {'team1': ['neil'], 'team2': []},
        'round_result': {
            'winner': {'team': '2', 'tickets': 1},
            'loser': {'team': '1', 'tickets': 0},
        },
    }

    payload = apply_elo_for_completed_match(
        get_db_connection,
        'lobby_solo_disabled',
        lobby,
        users,
        lambda: None,
        applied_at=1200,
        dev_solo_smoke_enabled=False,
        dev_solo_smoke_username='neil',
    )

    assert payload is None
    assert users['neil']['elo_rating'] == 1000
    assert users['neil']['elo_matches'] == 0
