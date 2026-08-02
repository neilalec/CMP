from services.profile import get_user_profile, normalize_display_name, update_display_name


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
