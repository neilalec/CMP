from services.profile import build_elo_leaderboard, get_user_profile, normalize_display_name, update_display_name


def test_get_user_profile_prefers_display_name_then_steam_persona_then_username():
    records = {
        'steam_24553635': {
            'password': 'hash',
            'steam_id': '76561198124553635',
            'display_name': '',
            'steam_persona_name': 'neil',
            'display_name_source': 'steam'
        }
    }

    profile = get_user_profile(
        'steam_24553635',
        records.get,
        [],
        lambda username: False
    )

    assert profile['username'] == 'steam_24553635'
    assert profile['display_name'] == 'neil'
    assert profile['steam_persona_name'] == 'neil'
    assert profile['elo_rating'] == 1000
    assert profile['elo_matches'] == 0


def test_update_display_name_saves_manual_display_name():
    records = {
        'steam_24553635': {
            'password': 'hash',
            'steam_id': '76561198124553635',
            'display_name': 'neil',
            'steam_persona_name': 'neil',
            'display_name_source': 'steam'
        }
    }
    saved = []

    result = update_display_name(
        'steam_24553635',
        'Neil CMP',
        records.get,
        lambda: saved.append(True),
        records,
        lambda username: {'username': username, 'display_name': records[username]['display_name']}
    )

    assert result['success'] is True
    assert records['steam_24553635']['display_name'] == 'Neil CMP'
    assert records['steam_24553635']['display_name_source'] == 'manual'
    assert saved == [True]


def test_normalize_display_name_rejects_invalid_characters():
    try:
        normalize_display_name('Neil@CMP')
    except ValueError as e:
        assert 'letters, numbers' in str(e)
    else:
        raise AssertionError('Expected display name validation to fail')


def test_build_elo_leaderboard_sorts_players_by_rating_and_matches():
    records = {
        'alice': {
            'display_name': 'Alice',
            'elo_rating': 1100,
            'elo_matches': 4,
        },
        'bob': {
            'display_name': 'Bob',
            'elo_rating': 1200,
            'elo_matches': 2,
        },
        'cara': {
            'display_name': 'Cara',
            'elo_rating': 1200,
            'elo_matches': 7,
        },
    }

    leaderboard = build_elo_leaderboard(records)

    assert [player['username'] for player in leaderboard] == ['cara', 'bob', 'alice']
    assert [player['rank'] for player in leaderboard] == [1, 2, 3]
    assert leaderboard[0]['elo_rating'] == 1200


def test_build_elo_leaderboard_hides_seeded_players_unless_enabled():
    records = {
        'neil': {
            'display_name': 'Neil',
            'elo_rating': 1000,
            'elo_matches': 0,
        },
        'AlphaAce1': {
            'display_name': 'AlphaAce1',
            'elo_rating': 1300,
            'elo_matches': 4,
            'seeded_player': True,
        },
        'group_seed_001': {
            'display_name': 'group_seed_001',
            'elo_rating': 1200,
            'elo_matches': 2,
        },
    }

    production_board = build_elo_leaderboard(records)
    dev_board = build_elo_leaderboard(records, include_seeded_players=True)

    assert [player['username'] for player in production_board] == ['neil']
    assert [player['username'] for player in dev_board] == ['AlphaAce1', 'group_seed_001', 'neil']
