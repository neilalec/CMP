import base64
import json
import re
import secrets
import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from services.auth_security import hash_password


STEAM_OPENID_PROVIDER = 'https://steamcommunity.com/openid/login'
STEAM_PLAYER_SUMMARIES_URL = 'https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/'
STEAM_COMMUNITY_PROFILE_XML_URL = 'https://steamcommunity.com/profiles/{steam_id}/?xml=1'
STEAM_CLAIMED_ID_RE = re.compile(r'^https?://steamcommunity\.com/openid/id/(\d{17})/?$')
STEAM_FALLBACK_USERNAME_RE = re.compile(r'^steam_\d{8}(?:_\d+)?$')
USERNAME_SAFE_RE = re.compile(r'[^A-Za-z0-9_]+')


def _serializer(secret_key):
    return URLSafeTimedSerializer(secret_key, salt='steam-openid-state')


def _safe_frontend_origin(origin, frontend_origins):
    origin = str(origin or '').rstrip('/')
    allowed = [item.rstrip('/') for item in frontend_origins]
    return origin if origin in allowed else next(iter(allowed), 'http://localhost:5173')


def build_steam_login_url(*, return_to, realm, state, secret_key):
    signed_state = _serializer(secret_key).dumps(state)
    separator = '&' if '?' in return_to else '?'
    return_to_with_state = f"{return_to}{separator}{urlencode({'state': signed_state})}"
    params = {
        'openid.ns': 'http://specs.openid.net/auth/2.0',
        'openid.mode': 'checkid_setup',
        'openid.return_to': return_to_with_state,
        'openid.realm': realm,
        'openid.identity': 'http://specs.openid.net/auth/2.0/identifier_select',
        'openid.claimed_id': 'http://specs.openid.net/auth/2.0/identifier_select'
    }
    return f"{STEAM_OPENID_PROVIDER}?{urlencode(params)}"


def load_steam_state(signed_state, *, secret_key, max_age_seconds=600):
    try:
        return _serializer(secret_key).loads(signed_state, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None


def extract_steam_id(claimed_id):
    match = STEAM_CLAIMED_ID_RE.match(str(claimed_id or ''))
    return match.group(1) if match else None


def _openid_items(args):
    if hasattr(args, 'lists'):
        for key, values in args.lists():
            if not key.startswith('openid.'):
                continue
            for value in values:
                yield key, value
        return

    for key, value in args.items():
        if key.startswith('openid.'):
            yield key, value


def get_steam_openid_verification_result(args, *, timeout=8):
    params = [
        (key, value)
        for key, value in _openid_items(args)
    ]
    params = [
        (key, 'check_authentication' if key == 'openid.mode' else value)
        for key, value in params
    ]
    if not any(key == 'openid.mode' for key, _ in params):
        params.append(('openid.mode', 'check_authentication'))

    encoded = urlencode(params).encode('utf-8')
    request = Request(
        STEAM_OPENID_PROVIDER,
        data=encoded,
        headers={'Content-Type': 'application/x-www-form-urlencoded'},
        method='POST'
    )
    with urlopen(request, timeout=timeout) as response:
        payload = response.read().decode('utf-8')

    result = parse_steam_openid_verification_payload(payload)
    return {
        'valid': str(result.get('is_valid', 'false')).lower() == 'true',
        'raw': payload,
        'result': result
    }


def verify_steam_openid_response(args, *, timeout=8):
    return get_steam_openid_verification_result(args, timeout=timeout)['valid']


def parse_steam_openid_verification_payload(payload):
    result = {}
    for line in str(payload or '').splitlines():
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        result[key.strip()] = value.strip()
    return result


def _steam_fallback_username(steam_id):
    return f"steam_{steam_id[-8:]}"


def _is_steam_fallback_username(username):
    return bool(STEAM_FALLBACK_USERNAME_RE.match(str(username or '')))


def normalize_steam_persona_username(persona_name, steam_id):
    normalized = USERNAME_SAFE_RE.sub('_', str(persona_name or '').strip())
    normalized = re.sub(r'_+', '_', normalized).strip('_')
    if not normalized:
        return _steam_fallback_username(steam_id)
    if normalized[0].isdigit():
        normalized = f'player_{normalized}'
    return normalized[:32]


def _unique_username(base_username, users, current_username=None):
    username = base_username
    suffix = 2
    while username in users and username != current_username:
        username = f"{base_username}_{suffix}"
        suffix += 1
    return username


def apply_steam_persona_to_user_record(record, persona_name):
    persona_name = str(persona_name or '').strip()
    if not persona_name:
        return False

    changed = False
    if record.get('steam_persona_name') != persona_name:
        record['steam_persona_name'] = persona_name
        changed = True

    display_name_source = str(record.get('display_name_source') or '').strip()
    display_name = str(record.get('display_name') or '').strip()
    if not display_name or display_name_source in ('', 'legacy', 'steam', 'fallback'):
        if record.get('display_name') != persona_name:
            record['display_name'] = persona_name
            changed = True
        if record.get('display_name_source') != 'steam':
            record['display_name_source'] = 'steam'
            changed = True

    return changed


def fetch_steam_persona_name(steam_id, *, api_key='', timeout=5):
    steam_id = str(steam_id or '').strip()
    api_key = str(api_key or '').strip()
    if api_key:
        url = f"{STEAM_PLAYER_SUMMARIES_URL}?{urlencode({'key': api_key, 'steamids': steam_id})}"
        with urlopen(Request(url), timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
        players = payload.get('response', {}).get('players', [])
        if players:
            return str(players[0].get('personaname') or '').strip()

    with urlopen(Request(STEAM_COMMUNITY_PROFILE_XML_URL.format(steam_id=steam_id)), timeout=timeout) as response:
        payload = response.read().decode('utf-8')
    root = ET.fromstring(payload)
    return str(root.findtext('steamID') or '').strip()


def get_or_create_steam_user(steam_id, *, users, save_users, persona_name=''):
    preferred_username = normalize_steam_persona_username(persona_name, steam_id)
    for username, record in users.items():
        if str(record.get('steam_id', '') or '').strip() == steam_id:
            if apply_steam_persona_to_user_record(record, persona_name):
                users[username] = record
                save_users()
            return username, False

    username = _unique_username(preferred_username, users)
    persona_name = str(persona_name or '').strip()

    users[username] = {
        'password': hash_password(secrets.token_urlsafe(32)),
        'steam_id': steam_id,
        'display_name': persona_name or username,
        'steam_persona_name': persona_name,
        'display_name_source': 'steam' if persona_name else 'fallback'
    }
    save_users()
    return username, True


def encode_callback_payload(payload):
    raw = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    return base64.urlsafe_b64encode(raw).decode('ascii').rstrip('=')


def build_frontend_callback_url(frontend_origin, payload):
    encoded_payload = encode_callback_payload(payload)
    return f"{frontend_origin.rstrip('/')}/auth/steam/callback#payload={encoded_payload}"


def request_base_url(request):
    parsed = urlparse(request.url_root)
    return f"{parsed.scheme}://{parsed.netloc}".rstrip('/')


def frontend_origin_from_request(request, frontend_origins):
    requested = request.args.get('frontend_origin') or request.headers.get('Origin') or ''
    return _safe_frontend_origin(requested, frontend_origins)
