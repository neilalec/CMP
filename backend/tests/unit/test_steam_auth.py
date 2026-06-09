from urllib.parse import parse_qs, urlparse

from services.auth_security import is_password_hash
from services.steam_auth import (
    _safe_frontend_origin,
    _openid_items,
    build_frontend_callback_url,
    build_steam_login_url,
    extract_steam_id,
    get_or_create_steam_user,
    load_steam_state,
    parse_steam_openid_verification_payload
)


def test_extract_steam_id_from_claimed_id():
    steam_id = extract_steam_id('https://steamcommunity.com/openid/id/76561198124553635')

    assert steam_id == '76561198124553635'


def test_extract_steam_id_rejects_invalid_claimed_id():
    steam_id = extract_steam_id('https://example.com/openid/id/76561198124553635')

    assert steam_id is None


def test_steam_login_url_contains_signed_state():
    url = build_steam_login_url(
        return_to='https://cmp.example/api/auth/steam/callback',
        realm='https://cmp.example',
        state={'frontend_origin': 'https://cmp.example'},
        secret_key='test-secret'
    )

    parsed = urlparse(url)

    assert parsed.netloc == 'steamcommunity.com'
    assert 'openid.mode=checkid_setup' in parsed.query
    return_to = parse_qs(parsed.query)['openid.return_to'][0]
    assert 'state=' in return_to


def test_signed_steam_state_roundtrip():
    url = build_steam_login_url(
        return_to='https://cmp.example/api/auth/steam/callback',
        realm='https://cmp.example',
        state={'frontend_origin': 'https://cmp.example'},
        secret_key='test-secret'
    )
    signed_state = parse_qs(urlparse(url).query)['openid.return_to'][0].split('state=')[1]

    state = load_steam_state(signed_state, secret_key='test-secret')

    assert state['frontend_origin'] == 'https://cmp.example'


def test_get_or_create_steam_user_reuses_linked_user():
    users = {
        'neil': {
            'password': 'legacy',
            'steam_id': '76561198124553635'
        }
    }

    username, created = get_or_create_steam_user(
        '76561198124553635',
        users=users,
        save_users=lambda: None
    )

    assert username == 'neil'
    assert created is False


def test_get_or_create_steam_user_creates_hashed_password_user():
    users = {}
    saved = []

    username, created = get_or_create_steam_user(
        '76561198124553635',
        users=users,
        save_users=lambda: saved.append(True)
    )

    assert username == 'steam_24553635'
    assert created is True
    assert users[username]['steam_id'] == '76561198124553635'
    assert is_password_hash(users[username]['password'])
    assert saved == [True]


def test_frontend_callback_payload_is_fragment_only():
    url = build_frontend_callback_url('https://cmp.example', {
        'success': True,
        'username': 'neil'
    })
    parsed = urlparse(url)

    assert parsed.path == '/auth/steam/callback'
    assert parsed.query == ''
    assert parsed.fragment.startswith('payload=')


def test_safe_frontend_origin_falls_back_to_first_configured_origin():
    origin = _safe_frontend_origin(
        'http://localhost',
        [
            'http://localhost:5173',
            'http://localhost:8080'
        ]
    )

    assert origin == 'http://localhost:5173'


def test_openid_items_preserves_multidict_values():
    class FakeArgs:
        def lists(self):
            return [
                ('state', ['ignored']),
                ('openid.mode', ['id_res']),
                ('openid.return_to', ['http://localhost:5173/api/auth/steam/callback?state=abc']),
                ('openid.signed', ['signed,return_to'])
            ]

    assert list(_openid_items(FakeArgs())) == [
        ('openid.mode', 'id_res'),
        ('openid.return_to', 'http://localhost:5173/api/auth/steam/callback?state=abc'),
        ('openid.signed', 'signed,return_to')
    ]


def test_parse_steam_openid_verification_payload_reads_valid_response():
    result = parse_steam_openid_verification_payload(
        'ns:http://specs.openid.net/auth/2.0\nis_valid:true\n'
    )

    assert result['is_valid'] == 'true'


def test_parse_steam_openid_verification_payload_reads_invalid_response():
    result = parse_steam_openid_verification_payload(
        'ns:http://specs.openid.net/auth/2.0\nis_valid:false\n'
    )

    assert result['is_valid'] == 'false'
