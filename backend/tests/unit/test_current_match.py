from services.current_match import resolve_current_match_location
from services.profile import build_profile_status


def test_current_match_location_uses_explicit_game_and_lobby_identity():
    assert resolve_current_match_location(
        'alice', lambda _user: 'squad-room', lambda _user: {'lobbyId': 'wardogs-room'}
    ) == {'gameType': 'wardogs', 'lobbyId': 'wardogs-room'}
    assert resolve_current_match_location(
        'alice', lambda _user: 'squad-room', lambda _user: None
    ) == {'gameType': 'squad', 'lobbyId': 'squad-room'}


def test_current_match_location_has_no_match_for_missing_user_or_domain_state():
    assert resolve_current_match_location('', lambda _user: 'squad-room', lambda _user: None) is None
    assert resolve_current_match_location('alice', lambda _user: None, lambda _user: None) is None


def test_current_match_location_ignores_invalid_wardogs_descriptor_and_uses_squad():
    assert resolve_current_match_location(
        'alice', lambda _user: 'squad-room', lambda _user: {'lobbyId': ''}
    ) == {'gameType': 'squad', 'lobbyId': 'squad-room'}


def test_profile_status_exposes_the_shared_current_match_descriptor():
    response = build_profile_status(
        'alice', lambda _user: {'username': 'alice'}, lambda _user: 'squad-room',
        lambda _user: {'gameType': 'wardogs', 'lobbyId': 'wardogs-room'},
    )
    assert response['profile']['active_lobby'] == 'squad-room'
    assert response['profile']['current_match'] == {
        'gameType': 'wardogs', 'lobbyId': 'wardogs-room'
    }
