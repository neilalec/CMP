import json
import os
import re
import socket
import struct
import time
from base64 import b64encode
from urllib import request as urllib_request
from urllib import error as urllib_error
from urllib.parse import quote, urlparse

from itsdangerous import BadSignature, URLSafeSerializer

from services.bridge import (
    BridgeUnavailable,
    fetch_all_layers,
    fetch_connected_server_players,
    fetch_latest_round_result,
    fetch_server_info,
    get_bridge_health,
    squadjs_bridge_request,
)


def _to_json(value):
    return json.dumps(value or {}, ensure_ascii=True, sort_keys=True)


def _from_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _token_serializer(secret_key):
    return URLSafeSerializer(str(secret_key or 'cmp-dev-secret'), salt='server-bridge-token')


def encrypt_bridge_token(token, secret_key):
    token = str(token or '').strip()
    if not token:
        return ''
    return _token_serializer(secret_key).dumps(token)


def decrypt_bridge_token(token_encrypted, secret_key):
    token_encrypted = str(token_encrypted or '').strip()
    if not token_encrypted:
        return ''
    try:
        return str(_token_serializer(secret_key).loads(token_encrypted) or '')
    except BadSignature:
        return ''


def mask_secret(value):
    value = str(value or '')
    if len(value) <= 4:
        return '****' if value else ''
    return f"{value[:2]}{'*' * max(4, len(value) - 4)}{value[-2:]}"


def normalize_steam_lobby_id(value):
    value = str(value or '').strip()
    if value.isdigit() and 17 <= len(value) <= 20:
        return value
    return ''


def normalize_query_port(value):
    try:
        port = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= port <= 65535:
        return port
    return None


def build_external_server_key(host, query_port):
    host = str(host or '').strip()
    query_port = normalize_query_port(query_port)
    if not host or query_port is None:
        return ''
    return f"{host}:{query_port}"


def extract_session_target_id(value):
    text = str(value or '').strip()
    if not text:
        return ''
    if text.startswith('Session:'):
        return text.split(':', 1)[1].strip()
    return ''


def get_squad_client_log_path():
    configured_path = str(os.getenv('SQUAD_CLIENT_LOG_PATH', '')).strip()
    if configured_path:
        return configured_path
    local_app_data = str(os.getenv('LOCALAPPDATA', '')).strip()
    if not local_app_data:
        return ''
    return os.path.join(local_app_data, 'SquadGame', 'Saved', 'Logs', 'SquadGame.log')


def lookup_local_log_session_id(connect_address=''):
    connect_address = str(connect_address or '').strip()
    log_path = get_squad_client_log_path()
    details = {
        'attempted': False,
        'configured': bool(log_path),
        'logPath': log_path,
        'matched': False,
        'targetServerId': '',
        'sessionId': '',
        'roomId': '',
        'connectAddress': '',
        'matchedConnectAddress': False,
        'sourceField': '',
        'error': '',
    }
    if not log_path:
        details['error'] = 'Squad client log path is not configured'
        return '', details
    if not os.path.exists(log_path):
        details['error'] = f'Squad client log not found at {log_path}'
        return '', details

    details['attempted'] = True
    try:
        with open(log_path, 'r', encoding='utf-8', errors='replace') as handle:
            lines = handle.readlines()
    except Exception as error:
        details['error'] = str(error)
        return '', details

    latest_connect_address = ''
    latest_room_id = ''
    for line in reversed(lines):
        if not latest_connect_address:
            match = re.search(r"traveling to ([0-9\.]+:\d+)", line)
            if match:
                latest_connect_address = match.group(1).strip()
                details['connectAddress'] = latest_connect_address
        if not latest_room_id:
            match = re.search(r"RedpointEOSRoomId=Session:([0-9a-f]{32})", line, re.IGNORECASE)
            if match:
                latest_room_id = f"Session:{match.group(1).lower()}"
        if latest_connect_address and latest_room_id:
            break

    if not latest_room_id:
        details['error'] = 'No recent EOS room ID found in Squad client log'
        return '', details

    details['roomId'] = latest_room_id
    details['sessionId'] = latest_room_id
    details['targetServerId'] = extract_session_target_id(latest_room_id)
    details['sourceField'] = 'RedpointEOSRoomId'
    details['matchedConnectAddress'] = not connect_address or latest_connect_address == connect_address
    details['matched'] = bool(details['targetServerId']) and details['matchedConnectAddress']
    if not details['matched'] and connect_address and latest_connect_address:
        details['error'] = (
            f"Latest Squad join was {latest_connect_address}, not requested server {connect_address}"
        )
    elif not latest_connect_address:
        details['error'] = 'No recent connect address found in Squad client log'
    return details['targetServerId'] if details['matched'] else '', details


def get_eos_api_base_url():
    return str(os.getenv('EOS_API_BASE_URL', 'https://api.epicgames.dev')).rstrip('/')


def get_eos_deployment_id():
    return str(os.getenv('EOS_DEPLOYMENT_ID', '5dee4062a90b42cd98fcad618b6636c2')).strip()


def get_eos_access_token():
    return str(os.getenv('EOS_ACCESS_TOKEN', '')).strip()


def get_eos_client_id():
    return str(os.getenv('EOS_CLIENT_ID', '')).strip()


def get_eos_client_secret():
    return str(os.getenv('EOS_CLIENT_SECRET', '')).strip()


def get_eos_steam_session_ticket():
    return str(os.getenv('EOS_STEAM_SESSION_TICKET_HEX', '')).strip()


def get_live_session_freshness_seconds():
    try:
        value = int(str(os.getenv('LIVE_SESSION_FRESHNESS_SECONDS', '1800')).strip())
    except (TypeError, ValueError):
        return 1800
    return max(0, value)


def get_eos_runtime_status():
    access_token = get_eos_access_token()
    client_id = get_eos_client_id()
    client_secret = get_eos_client_secret()
    steam_session_ticket = get_eos_steam_session_ticket()
    deployment_id = get_eos_deployment_id()
    exchange_configured = bool(client_id and client_secret and steam_session_ticket and deployment_id)
    return {
        'configured': bool(access_token) or exchange_configured,
        'deploymentId': deployment_id,
        'apiBaseUrl': get_eos_api_base_url(),
        'accessTokenMasked': mask_secret(access_token),
        'clientIdConfigured': bool(client_id),
        'clientSecretConfigured': bool(client_secret),
        'steamSessionTicketConfigured': bool(steam_session_ticket),
        'exchangeConfigured': exchange_configured,
    }


def _build_eos_basic_auth_header(client_id, client_secret):
    raw = f"{str(client_id or '').strip()}:{str(client_secret or '').strip()}".encode('utf-8')
    return f"Basic {b64encode(raw).decode('ascii')}"


def fetch_eos_access_token(*, timeout=10):
    existing_access_token = get_eos_access_token()
    details = {
        'source': 'env_access_token' if existing_access_token else '',
        'attempted': False,
        'configured': bool(existing_access_token),
        'url': '',
        'error': '',
    }
    if existing_access_token:
        return existing_access_token, details

    client_id = get_eos_client_id()
    client_secret = get_eos_client_secret()
    steam_session_ticket = get_eos_steam_session_ticket()
    deployment_id = get_eos_deployment_id()
    if not client_id or not client_secret or not steam_session_ticket or not deployment_id:
        details['error'] = 'EOS access token not configured'
        details['configured'] = False
        return '', details

    details['configured'] = True
    details['attempted'] = True
    details['source'] = 'steam_ticket_exchange'
    details['url'] = f"{get_eos_api_base_url()}/auth/v1/oauth/token"
    request_body = (
        f"grant_type=external_auth&external_auth_type=steam_session_ticket"
        f"&external_auth_token={steam_session_ticket}"
        f"&deployment_id={deployment_id}"
    ).encode('utf-8')
    request = urllib_request.Request(
        details['url'],
        data=request_body,
        method='POST',
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': _build_eos_basic_auth_header(client_id, client_secret),
        },
    )
    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib_error.HTTPError as error:
        try:
            error_body = error.read().decode('utf-8')
        except Exception:
            error_body = ''
        details['error'] = error_body or f'HTTP {error.code}'
        return '', details
    except Exception as error:
        details['error'] = str(error)
        return '', details

    access_token = str(payload.get('access_token') or '').strip()
    if not access_token:
        details['error'] = 'EOS token response did not include access_token'
        return '', details
    return access_token, details


def _normalize_eos_attribute_value(value):
    if isinstance(value, dict):
        for key in ('value', 'Value', 'attributeValue'):
            nested = value.get(key)
            if nested is not None:
                return _normalize_eos_attribute_value(nested)
        return ''
    return '' if value is None else str(value).strip()


def _extract_eos_attributes(candidate):
    if not isinstance(candidate, dict):
        return {}
    attributes = candidate.get('attributes')
    if isinstance(attributes, dict):
        return attributes
    return candidate


def _iter_eos_candidates(value):
    if isinstance(value, dict):
        if isinstance(value.get('attributes'), dict):
            yield value
        for nested in value.values():
            yield from _iter_eos_candidates(nested)
    elif isinstance(value, list):
        for item in value:
            yield from _iter_eos_candidates(item)


def _extract_eos_server_name(attributes):
    for key in ('SERVERNAME_s', 'attributes.SERVERNAME_s', 'serverName', 'name'):
        value = _normalize_eos_attribute_value(attributes.get(key))
        if value:
            return value
    return ''


def _extract_eos_advertised_session(attributes):
    for key in (
        'ADVERTISEDSESSIONID_s',
        'attributes.ADVERTISEDSESSIONID_s',
        'advertisedSessionId',
        'sessionId',
    ):
        value = _normalize_eos_attribute_value(attributes.get(key))
        if value:
            return value, key
    return '', ''


def _normalize_ipv4_host(value):
    text = str(value or '').strip()
    if re.fullmatch(r"\d{1,3}(?:\.\d{1,3}){3}", text):
        return text
    return ''


def _normalize_port_number(value):
    text = str(value or '').strip()
    if not text.isdigit():
        return None
    port = int(text)
    if 0 < port <= 65535:
        return port
    return None


def _normalize_connect_address(value):
    text = str(value or '').strip()
    match = re.fullmatch(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d{1,5})", text)
    if not match:
        return ''
    port = _normalize_port_number(match.group(2))
    if port is None:
        return ''
    return f"{match.group(1)}:{port}"


def _extract_eos_network_identity(attributes):
    preferred_connect_keys = (
        'CONNECTIONADDRESS_s',
        'attributes.CONNECTIONADDRESS_s',
        'ServerConnectionUrl_s',
        'attributes.ServerConnectionUrl_s',
        'SERVERCONNECTIONURL_s',
        'attributes.SERVERCONNECTIONURL_s',
        'CONNECTADDRESS_s',
        'attributes.CONNECTADDRESS_s',
    )
    preferred_host_keys = (
        'HOST_s',
        'attributes.HOST_s',
        'HOSTADDRESS_s',
        'attributes.HOSTADDRESS_s',
        'SERVERIP_s',
        'attributes.SERVERIP_s',
        'IP_s',
        'attributes.IP_s',
    )
    preferred_query_keys = (
        'QUERYPORT_n',
        'attributes.QUERYPORT_n',
        'QUERYPORT_s',
        'attributes.QUERYPORT_s',
    )
    preferred_game_port_keys = (
        'PORT_n',
        'attributes.PORT_n',
        'PORT_s',
        'attributes.PORT_s',
        'GAMEPORT_n',
        'attributes.GAMEPORT_n',
        'GAMEPORT_s',
        'attributes.GAMEPORT_s',
    )

    connect_address = ''
    host = ''
    query_port = None
    game_port = None

    for key in preferred_connect_keys:
        normalized = _normalize_connect_address(_normalize_eos_attribute_value(attributes.get(key)))
        if normalized:
            connect_address = normalized
            break

    for key in preferred_host_keys:
        normalized = _normalize_ipv4_host(_normalize_eos_attribute_value(attributes.get(key)))
        if normalized:
            host = normalized
            break

    for key in preferred_query_keys:
        normalized = _normalize_port_number(_normalize_eos_attribute_value(attributes.get(key)))
        if normalized is not None:
            query_port = normalized
            break

    for key in preferred_game_port_keys:
        normalized = _normalize_port_number(_normalize_eos_attribute_value(attributes.get(key)))
        if normalized is not None:
            game_port = normalized
            break

    for key, raw_value in attributes.items():
        value = _normalize_eos_attribute_value(raw_value)
        if not value:
            continue
        lowered_key = str(key or '').strip().lower()

        if not connect_address:
            normalized_connect = _normalize_connect_address(value)
            if normalized_connect and any(
                token in lowered_key for token in ('connect', 'connection', 'serverconnection', 'address', 'host')
            ):
                connect_address = normalized_connect

        if not host:
            normalized_host = _normalize_ipv4_host(value)
            if normalized_host and any(token in lowered_key for token in ('host', 'ip', 'address')):
                host = normalized_host

        normalized_port = _normalize_port_number(value)
        if normalized_port is None:
            continue
        if query_port is None and 'query' in lowered_key and 'port' in lowered_key:
            query_port = normalized_port
        elif game_port is None and 'port' in lowered_key and 'query' not in lowered_key:
            game_port = normalized_port

    if not host and connect_address:
        host = connect_address.split(':', 1)[0]
    if game_port is None and connect_address:
        game_port = int(connect_address.split(':', 1)[1])

    return {
        'connectAddress': connect_address,
        'host': host,
        'queryPort': query_port,
        'gamePort': game_port,
    }


def _score_eos_candidate(candidate, *, server_name='', connect_address='', host='', query_port=None):
    requested_name = str(server_name or '').strip().casefold()
    requested_connect_address = _normalize_connect_address(connect_address)
    requested_host = _normalize_ipv4_host(host)
    requested_query_port = _normalize_port_number(query_port)

    candidate_name = str(candidate.get('serverName') or '').strip().casefold()
    candidate_connect_address = _normalize_connect_address(candidate.get('connectAddress'))
    candidate_host = _normalize_ipv4_host(candidate.get('host'))
    candidate_query_port = _normalize_port_number(candidate.get('queryPort'))

    name_matched = bool(requested_name and candidate_name == requested_name)
    connect_matched = bool(
        requested_connect_address
        and candidate_connect_address
        and candidate_connect_address == requested_connect_address
    )
    host_matched = bool(requested_host and candidate_host and candidate_host == requested_host)
    query_port_matched = bool(
        requested_query_port is not None
        and candidate_query_port is not None
        and candidate_query_port == requested_query_port
    )

    score = 0
    if connect_matched:
        score += 100
    if host_matched:
        score += 30
    if query_port_matched:
        score += 30
    if name_matched:
        score += 10
    if candidate.get('targetServerId'):
        score += 1

    return {
        'nameMatched': name_matched,
        'connectAddressMatched': connect_matched,
        'hostMatched': host_matched,
        'queryPortMatched': query_port_matched,
        'score': score,
    }


def lookup_eos_matchmaking_session(server_name, *, connect_address='', host='', query_port=None, timeout=5):
    details = {
        'attempted': False,
        'configured': False,
        'serverName': str(server_name or '').strip(),
        'connectAddress': _normalize_connect_address(connect_address),
        'host': _normalize_ipv4_host(host),
        'queryPort': _normalize_port_number(query_port),
        'deploymentId': get_eos_deployment_id(),
        'url': '',
        'matched': False,
        'matchedCount': 0,
        'sessionId': '',
        'targetServerId': '',
        'sourceField': '',
        'selectedServerName': '',
        'candidates': [],
        'error': '',
        'auth': {},
    }
    access_token, auth_details = fetch_eos_access_token(timeout=timeout)
    details['auth'] = auth_details
    if not access_token:
        details['configured'] = bool(auth_details.get('configured'))
        details['error'] = auth_details.get('error') or 'EOS access token not configured'
        return '', details

    server_name = details['serverName']
    if not server_name:
        details['error'] = 'Server name is required for EOS lookup'
        return '', details

    deployment_id = details['deploymentId']
    if not deployment_id:
        details['error'] = 'EOS deployment ID not configured'
        return '', details

    details['configured'] = True
    details['attempted'] = True
    details['url'] = f"{get_eos_api_base_url()}/matchmaking/v1/{deployment_id}/filter"
    request_payload = {
        'criteria': [
            {
                'key': 'attributes.SERVERNAME_s',
                'op': 'EQUAL',
                'value': server_name,
            }
        ],
        'maxResults': 25,
    }
    request_body = json.dumps(request_payload).encode('utf-8')
    request = urllib_request.Request(
        details['url'],
        data=request_body,
        method='POST',
        headers={
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}',
        },
    )

    try:
        with urllib_request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except urllib_error.HTTPError as error:
        try:
            error_body = error.read().decode('utf-8')
        except Exception:
            error_body = ''
        details['error'] = error_body or f'HTTP {error.code}'
        return '', details
    except Exception as error:
        details['error'] = str(error)
        return '', details

    candidates = []
    for candidate in _iter_eos_candidates(payload):
        attributes = _extract_eos_attributes(candidate)
        candidate_server_name = _extract_eos_server_name(attributes)
        session_id, source_field = _extract_eos_advertised_session(attributes)
        target_server_id = extract_session_target_id(session_id)
        identity = _extract_eos_network_identity(attributes)
        normalized_candidate = {
            'serverName': candidate_server_name,
            'sessionId': session_id,
            'targetServerId': target_server_id,
            'sourceField': source_field,
            'connectAddress': identity.get('connectAddress') or '',
            'host': identity.get('host') or '',
            'queryPort': identity.get('queryPort'),
            'gamePort': identity.get('gamePort'),
        }
        normalized_candidate.update(
            _score_eos_candidate(
                normalized_candidate,
                server_name=server_name,
                connect_address=connect_address,
                host=host,
                query_port=query_port,
            )
        )
        if any(normalized_candidate.values()):
            candidates.append(normalized_candidate)

    details['matchedCount'] = len(candidates)
    details['candidates'] = candidates[:10]

    scored_candidates = [
        candidate for candidate in candidates
        if candidate.get('sessionId')
    ]
    scored_candidates.sort(
        key=lambda value: (
            int(value.get('score') or 0),
            1 if value.get('connectAddressMatched') else 0,
            1 if value.get('hostMatched') and value.get('queryPortMatched') else 0,
            1 if value.get('nameMatched') else 0,
        ),
        reverse=True,
    )

    if scored_candidates:
        best_candidate = scored_candidates[0]
        strongest_identity_match = bool(
            best_candidate.get('connectAddressMatched')
            or (best_candidate.get('hostMatched') and best_candidate.get('queryPortMatched'))
            or best_candidate.get('nameMatched')
        )
        if strongest_identity_match:
            details['matched'] = True
            details['sessionId'] = best_candidate['sessionId']
            details['targetServerId'] = (
                best_candidate.get('targetServerId')
                or extract_session_target_id(best_candidate['sessionId'])
            )
            details['sourceField'] = best_candidate.get('sourceField') or 'ADVERTISEDSESSIONID_s'
            details['selectedServerName'] = best_candidate.get('serverName') or ''
            return details['targetServerId'], details

    if len(candidates) == 1 and candidates[0].get('sessionId'):
        candidate = candidates[0]
        details['matched'] = True
        details['sessionId'] = candidate['sessionId']
        details['targetServerId'] = candidate.get('targetServerId') or extract_session_target_id(candidate['sessionId'])
        details['sourceField'] = candidate.get('sourceField') or 'ADVERTISEDSESSIONID_s'
        details['selectedServerName'] = candidate.get('serverName') or ''
        return details['targetServerId'], details

    return '', details


def build_live_session_snapshot(result, *, checked_at=None, now=None):
    result = result or {}
    session_discovery = result.get('sessionDiscovery') or {}
    eos_discovery = result.get('eosDiscovery') or {}
    client_log = eos_discovery.get('clientLog') or {}
    live_session = {
        'matched': False,
        'targetServerId': '',
        'source': '',
        'sourceField': '',
        'sessionId': '',
        'roomId': '',
        'connectAddress': '',
        'lastSeenAt': float(checked_at or 0),
        'freshnessSeconds': get_live_session_freshness_seconds(),
        'fresh': False,
    }
    if not session_discovery.get('matched') or not session_discovery.get('targetServerId'):
        return live_session

    live_session['matched'] = True
    live_session['targetServerId'] = str(session_discovery.get('targetServerId') or '').strip()
    live_session['sourceField'] = str(session_discovery.get('sourceField') or '').strip()

    if live_session['sourceField'].startswith('local_squad_log.'):
        live_session['source'] = 'local_squad_log'
        live_session['sessionId'] = str(client_log.get('sessionId') or '').strip()
        live_session['roomId'] = str(client_log.get('roomId') or live_session['sessionId'] or '').strip()
        live_session['connectAddress'] = str(client_log.get('connectAddress') or '').strip()
    elif live_session['sourceField'].startswith('eos_matchmaking.'):
        live_session['source'] = 'eos_matchmaking'
        live_session['sessionId'] = str(eos_discovery.get('sessionId') or '').strip()
        live_session['roomId'] = str(eos_discovery.get('sessionId') or '').strip()
        live_session['connectAddress'] = str(
            client_log.get('connectAddress')
            or (result.get('joinStrategy') or {}).get('target')
            or ''
        ).strip()
    else:
        live_session['source'] = 'bridge_payload'
        live_session['sessionId'] = str(session_discovery.get('targetServerId') or '').strip()
        live_session['roomId'] = str(session_discovery.get('targetServerId') or '').strip()
        live_session['connectAddress'] = str(
            client_log.get('connectAddress')
            or (result.get('joinStrategy') or {}).get('target')
            or ''
        ).strip()

    comparison_now = float(now if now is not None else time.time())
    if live_session['lastSeenAt'] > 0:
        live_session['fresh'] = (
            comparison_now - live_session['lastSeenAt']
        ) <= live_session['freshnessSeconds']
    return live_session


def select_preferred_live_session(*candidates):
    matched_candidates = [
        candidate for candidate in candidates
        if isinstance(candidate, dict) and candidate.get('matched')
    ]
    if matched_candidates:
        return max(matched_candidates, key=lambda value: float(value.get('lastSeenAt') or 0))
    for candidate in candidates:
        if isinstance(candidate, dict) and candidate:
            return candidate
    return {}


def _read_cstring(payload, offset):
    end = payload.find(b'\x00', offset)
    if end == -1:
        raise ValueError('Unterminated A2S string field')
    return payload[offset:end].decode('utf-8', errors='replace'), end + 1


def parse_a2s_info_steam_id(payload):
    data = bytes(payload or b'')
    if len(data) < 6:
        return ''
    if data[:4] != b'\xff\xff\xff\xff':
        return ''
    header = data[4]
    if header != 0x49:
        return ''

    offset = 6  # skip 0xFFFFFFFF, header, protocol
    try:
        for _ in range(4):  # name, map, folder, game
            _, offset = _read_cstring(data, offset)
        offset += 2  # app id
        offset += 4  # players, max players, bots, server type
        offset += 2  # environment, visibility
        _, offset = _read_cstring(data, offset)  # version
        if offset >= len(data):
            return ''
        edf = data[offset]
        offset += 1
        if edf & 0x80:
            offset += 2
        if edf & 0x10:
            if offset + 8 > len(data):
                return ''
            steam_id = struct.unpack_from('<Q', data, offset)[0]
            return normalize_steam_lobby_id(str(steam_id))
    except (ValueError, struct.error, UnicodeDecodeError):
        return ''
    return ''


def query_a2s_info_steam_id(host, query_port, timeout=3):
    host = str(host or '').strip()
    query_port = normalize_query_port(query_port)
    if not host or query_port is None:
        return ''

    request_payload = b'\xff\xff\xff\xffTSource Engine Query\x00'
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(timeout)
        sock.sendto(request_payload, (host, query_port))
        response, _ = sock.recvfrom(4096)
    return parse_a2s_info_steam_id(response)


def extract_connect_port(connect_address):
    connect_address = str(connect_address or '').strip()
    if not connect_address or ':' not in connect_address:
        return None
    _, _, port = connect_address.rpartition(':')
    return normalize_query_port(port)


def build_join_strategy(
    *,
    discovered_steam_lobby_id='',
    discovered_source='',
    stored_steam_lobby_id='',
    connect_address='',
):
    live_steam_lobby_id = normalize_steam_lobby_id(discovered_steam_lobby_id)
    cached_steam_lobby_id = normalize_steam_lobby_id(stored_steam_lobby_id)
    connect_address = str(connect_address or '').strip()

    if live_steam_lobby_id:
        return {
            'joinMethod': 'steam_lobby',
            'source': discovered_source or 'live_lookup',
            'target': live_steam_lobby_id,
            'ready': True,
        }
    if cached_steam_lobby_id:
        return {
            'joinMethod': 'steam_lobby',
            'source': 'stored_cache',
            'target': cached_steam_lobby_id,
            'ready': True,
        }
    if connect_address:
        return {
            'joinMethod': 'direct_connect',
            'source': 'connect_address',
            'target': connect_address,
            'ready': True,
        }
    return {
        'joinMethod': 'unavailable',
        'source': 'none',
        'target': '',
        'ready': False,
    }


def build_join_url_from_strategy(strategy, *, join_password=''):
    strategy = strategy or {}
    join_method = str(strategy.get('joinMethod') or '').strip()
    target = str(strategy.get('target') or '').strip()
    if join_method == 'steam_lobby' and normalize_steam_lobby_id(target):
        return build_steam_lobby_join_url(target)
    if join_method == 'direct_connect' and target:
        return build_squad_join_url(target, join_password)
    return ''


def build_join_url_from_server_details(server_details):
    details = server_details or {}
    explicit_join_url = str(details.get('joinUrl') or details.get('join_url') or '').strip()
    if explicit_join_url:
        return explicit_join_url
    strategy = details.get('joinStrategy') or details.get('join_strategy') or {}
    join_url = build_join_url_from_strategy(strategy, join_password=str(details.get('password') or '').strip())
    if join_url:
        return join_url
    potential_steam_lobby_id = details.get('steamLobbyId') or details.get('steam_lobby_id') or ''
    steam_lobby_id = normalize_steam_lobby_id(potential_steam_lobby_id)
    if steam_lobby_id:
        return build_steam_lobby_join_url(steam_lobby_id)
    connect_address = str(details.get('connectAddress') or details.get('ip') or '').strip()
    if connect_address:
        return build_squad_join_url(connect_address, str(details.get('password') or '').strip())
    return ''


def lookup_steam_web_api_steam_id(addr, *, connect_address='', timeout=3):
    details = {
        'attempted': False,
        'address': '',
        'connectPort': extract_connect_port(connect_address),
        'steamLobbyId': '',
        'matchedCount': 0,
        'matchedServer': {},
        'error': '',
        'url': '',
    }
    host = str(addr or '').strip()
    if not host:
        return '', details

    details['attempted'] = True
    details['address'] = host
    details['url'] = f"https://api.steampowered.com/ISteamApps/GetServersAtAddress/v1/?addr={host}"

    try:
        with urllib_request.urlopen(details['url'], timeout=timeout) as response:
            api_data = json.loads(response.read().decode('utf-8'))
        api_servers = [
            server
            for server in api_data.get('response', {}).get('servers', [])
            if server.get('appid') == 393380
        ]
        details['matchedCount'] = len(api_servers)

        selected_server = None
        connect_port = details['connectPort']
        if connect_port is not None:
            for server in api_servers:
                if normalize_query_port(server.get('gameport')) == connect_port:
                    selected_server = server
                    break
                if normalize_query_port(server.get('port')) == connect_port:
                    selected_server = server
                    break
        if not selected_server and api_servers:
            selected_server = api_servers[0]

        if selected_server:
            details['matchedServer'] = {
                key: selected_server.get(key)
                for key in ('name', 'addr', 'gameport', 'port', 'steamid', 'gmsindex', 'appid')
                if key in selected_server
            }
            discovered_steam_id = normalize_steam_lobby_id(selected_server.get('steamid'))
            details['steamLobbyId'] = discovered_steam_id
            return discovered_steam_id, details
    except Exception as error:
        details['error'] = str(error)

    return '', details


def enrich_server_result_with_discovery(result, server_like, *, status='healthy', error_message=''):
    server_like = server_like or {}
    info = result.get('serverInfo') or {}
    bridge_details = (result.get('bridge') or {}).get('details', {})
    connect_address = str(server_like.get('connect_address') or '').strip()
    stored_steam_lobby_id = str(server_like.get('steam_lobby_id') or '').strip()

    network_identity = {
        'host': str(info.get('host') or bridge_details.get('host') or '').strip(),
        'queryPort': normalize_query_port(info.get('queryPort') or bridge_details.get('queryPort')),
    }
    network_identity['externalKey'] = build_external_server_key(
        network_identity.get('host'),
        network_identity.get('queryPort')
    )
    result['networkIdentity'] = network_identity

    discovery = {
        'bridge': {
            'attempted': status != 'offline',
            'matched': False,
            'steamLobbyId': '',
            'sourceField': '',
            'error': error_message if status == 'offline' else '',
        },
        'a2s': {
            'attempted': False,
            'matched': False,
            'host': network_identity.get('host') or '',
            'queryPort': network_identity.get('queryPort'),
            'steamLobbyId': '',
            'error': '',
        },
        'steamWebApi': {
            'attempted': False,
            'address': '',
            'connectPort': extract_connect_port(connect_address),
            'steamLobbyId': '',
            'matchedCount': 0,
            'matchedServer': {},
            'error': '',
            'url': '',
        },
        'final': {},
    }
    session_discovery = {
        'attempted': status != 'offline',
        'matched': False,
        'targetServerId': '',
        'sourceField': '',
        'candidates': [],
    }
    eos_discovery = {
        'attempted': False,
        'configured': False,
        'serverName': str(info.get('serverName') or bridge_details.get('serverName') or '').strip(),
        'deploymentId': get_eos_deployment_id(),
        'url': '',
        'matched': False,
        'matchedCount': 0,
        'sessionId': '',
        'targetServerId': '',
        'sourceField': '',
        'selectedServerName': '',
        'candidates': [],
        'error': '',
        'clientLog': {
            'attempted': False,
            'configured': False,
            'logPath': '',
            'matched': False,
            'targetServerId': '',
            'sessionId': '',
            'roomId': '',
            'connectAddress': '',
            'matchedConnectAddress': False,
            'sourceField': '',
            'error': '',
        },
    }

    discovered_steam_id = ''
    discovered_source = ''
    if status != 'offline':
        candidate_fields = (
            ('serverInfo.steamLobbyId', info.get('steamLobbyId')),
            ('serverInfo.steam_lobby_id', info.get('steam_lobby_id')),
            ('serverInfo.id', info.get('id')),
            ('serverInfo.steamid', info.get('steamid')),
            ('serverInfo.steamID', info.get('steamID')),
            ('serverInfo.serverID', info.get('serverID')),
            ('serverInfo.steamid64', info.get('steamid64')),
            ('result.steamLobbyId', result.get('steamLobbyId')),
            ('result.steam_lobby_id', result.get('steam_lobby_id')),
            ('result.steamID', result.get('steamID')),
            ('result.steamid', result.get('steamid')),
            ('bridge.steamLobbyId', bridge_details.get('steamLobbyId')),
            ('bridge.steam_lobby_id', bridge_details.get('steam_lobby_id')),
            ('bridge.id', bridge_details.get('id')),
            ('bridge.steamid', bridge_details.get('steamid')),
            ('bridge.steamID', bridge_details.get('steamID')),
        )
        for field_name, candidate in candidate_fields:
            normalized = normalize_steam_lobby_id(candidate)
            if normalized:
                discovered_steam_id = normalized
                discovered_source = 'bridge_payload'
                discovery['bridge']['matched'] = True
                discovery['bridge']['steamLobbyId'] = normalized
                discovery['bridge']['sourceField'] = field_name
                break

        raw_session_candidates = info.get('sessionCandidates') or bridge_details.get('sessionCandidates') or []
        if isinstance(raw_session_candidates, list):
            for candidate in raw_session_candidates:
                key = str((candidate or {}).get('key') or '').strip()
                value = str((candidate or {}).get('value') or '').strip()
                if not key or not value:
                    continue
                session_discovery['candidates'].append({
                    'key': key,
                    'value': value,
                })
                target_server_id = extract_session_target_id(value)
                if target_server_id and not session_discovery['matched']:
                    session_discovery['matched'] = True
                    session_discovery['targetServerId'] = target_server_id
                    session_discovery['sourceField'] = key

    if not session_discovery['matched'] and status != 'offline':
        target_server_id, eos_discovery = lookup_eos_matchmaking_session(
            info.get('serverName') or bridge_details.get('serverName') or '',
            connect_address=connect_address,
            host=network_identity.get('host'),
            query_port=network_identity.get('queryPort'),
        )
        if target_server_id:
            session_discovery['matched'] = True
            session_discovery['targetServerId'] = target_server_id
            session_discovery['sourceField'] = f"eos_matchmaking.{eos_discovery.get('sourceField') or 'ADVERTISEDSESSIONID_s'}"

    if status != 'offline':
        local_log_target_server_id, local_log_discovery = lookup_local_log_session_id(connect_address)
        eos_discovery['clientLog'] = local_log_discovery
        if not session_discovery['matched'] and local_log_target_server_id:
            session_discovery['matched'] = True
            session_discovery['targetServerId'] = local_log_target_server_id
            session_discovery['sourceField'] = (
                f"local_squad_log.{local_log_discovery.get('sourceField') or 'RedpointEOSRoomId'}"
            )

    if not discovered_steam_id and status != 'offline':
        discovery['a2s']['attempted'] = bool(
            network_identity.get('host') and network_identity.get('queryPort') is not None
        )
        if discovery['a2s']['attempted']:
            try:
                discovered_steam_id = query_a2s_info_steam_id(
                    network_identity.get('host'),
                    network_identity.get('queryPort')
                )
                if discovered_steam_id:
                    discovered_source = 'a2s_info'
                    discovery['a2s']['matched'] = True
                    discovery['a2s']['steamLobbyId'] = discovered_steam_id
            except (OSError, ValueError) as error:
                discovery['a2s']['error'] = str(error)

    if not discovered_steam_id and status != 'offline':
        discovered_steam_id, steam_web_details = lookup_steam_web_api_steam_id(
            network_identity.get('host'),
            connect_address=connect_address,
        )
        discovery['steamWebApi'] = steam_web_details
        if discovered_steam_id:
            discovered_source = 'steam_web_api'

    join_strategy = build_join_strategy(
        discovered_steam_lobby_id=discovered_steam_id,
        discovered_source=discovered_source,
        stored_steam_lobby_id=stored_steam_lobby_id,
        connect_address=connect_address,
    )
    discovery['final'] = join_strategy
    result['steamLobbyDiscovery'] = discovery
    result['sessionDiscovery'] = session_discovery
    result['eosDiscovery'] = eos_discovery
    result['joinStrategy'] = join_strategy
    result['liveSession'] = build_live_session_snapshot(result)
    return discovered_steam_id, discovery, join_strategy


def validate_bridge_url(bridge_url):
    parsed = urlparse(str(bridge_url or '').strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('Bridge URL must be a valid http or https URL')
    return parsed.geturl().rstrip('/')


def init_server_registry_tables(get_db_connection):
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                owner_label TEXT NOT NULL DEFAULT '',
                steam_lobby_id TEXT NOT NULL DEFAULT '',
                connect_address TEXT NOT NULL DEFAULT '',
                join_password TEXT NOT NULL DEFAULT '',
                bridge_url TEXT NOT NULL,
                bridge_token_encrypted TEXT NOT NULL DEFAULT '',
                submitted_by TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                approved_at REAL,
                status TEXT NOT NULL DEFAULT 'pending',
                enabled INTEGER NOT NULL DEFAULT 0,
                current_lobby_id TEXT,
                reserved_at REAL,
                last_health_check_at REAL,
                last_health_status TEXT,
                last_health_error TEXT,
                cap_players INTEGER NOT NULL DEFAULT 0,
                cap_layer_change INTEGER NOT NULL DEFAULT 0,
                cap_broadcast INTEGER NOT NULL DEFAULT 0,
                cap_round_result INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL,
                result TEXT NOT NULL,
                error TEXT,
                health_payload_json TEXT NOT NULL DEFAULT '{}',
                checked_at REAL NOT NULL,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL,
                lobby_id TEXT NOT NULL,
                state TEXT NOT NULL,
                reserved_at REAL NOT NULL,
                released_at REAL,
                release_reason TEXT,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
            """
        )
        columns = {row['name'] for row in conn.execute("PRAGMA table_info(completed_matches)").fetchall()}
        if columns and 'server_id' not in columns:
            conn.execute("ALTER TABLE completed_matches ADD COLUMN server_id INTEGER")
        server_columns = {row['name'] for row in conn.execute("PRAGMA table_info(servers)").fetchall()}
        if 'submitted_by' not in server_columns:
            conn.execute("ALTER TABLE servers ADD COLUMN submitted_by TEXT NOT NULL DEFAULT ''")
        if 'approved_by' not in server_columns:
            conn.execute("ALTER TABLE servers ADD COLUMN approved_by TEXT NOT NULL DEFAULT ''")
        if 'approved_at' not in server_columns:
            conn.execute("ALTER TABLE servers ADD COLUMN approved_at REAL")
        if 'steam_lobby_id' not in server_columns:
            conn.execute("ALTER TABLE servers ADD COLUMN steam_lobby_id TEXT NOT NULL DEFAULT ''")
        conn.commit()


def slugify_server_name(display_name):
    text = ''.join(ch.lower() if ch.isalnum() else '-' for ch in str(display_name or '').strip())
    parts = [part for part in text.split('-') if part]
    slug = '-'.join(parts)[:80]
    return slug or f"server-{int(time.time())}"


def _row_to_server_payload(row, secret_key=None, include_secret=False):
    if not row:
        return None
    payload = {
        'id': row['id'],
        'slug': row['slug'],
        'display_name': row['display_name'],
        'owner_label': row['owner_label'],
        'steam_lobby_id': row['steam_lobby_id'],
        'connect_address': row['connect_address'],
        'join_password': row['join_password'],
        'bridge_url': row['bridge_url'],
        'bridge_token_masked': mask_secret(decrypt_bridge_token(row['bridge_token_encrypted'], secret_key)),
        'submitted_by': row['submitted_by'],
        'approved_by': row['approved_by'],
        'approved_at': row['approved_at'],
        'status': row['status'],
        'enabled': bool(row['enabled']),
        'current_lobby_id': row['current_lobby_id'],
        'reserved_at': row['reserved_at'],
        'last_health_check_at': row['last_health_check_at'],
        'last_health_status': row['last_health_status'],
        'last_health_error': row['last_health_error'],
        'capabilities': {
            'players': bool(row['cap_players']),
            'layer_change': bool(row['cap_layer_change']),
            'broadcast': bool(row['cap_broadcast']),
            'round_result': bool(row['cap_round_result']),
        },
        'metadata': _from_json(row['metadata_json'], {}),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }
    if include_secret:
        payload['bridge_token'] = decrypt_bridge_token(row['bridge_token_encrypted'], secret_key)
    return payload


def list_servers(get_db_connection, secret_key):
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM servers ORDER BY enabled DESC, display_name ASC").fetchall()
    return [_row_to_server_payload(row, secret_key) for row in rows]


def get_server_by_id(get_db_connection, server_id, secret_key, include_secret=False):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    return _row_to_server_payload(row, secret_key, include_secret=include_secret)


def create_server(get_db_connection, secret_key, payload, submitted_by=''):
    display_name = str(payload.get('display_name') or '').strip()
    if not display_name:
        raise ValueError('display_name is required')
    bridge_url = validate_bridge_url(payload.get('bridge_url'))
    now = time.time()
    slug = slugify_server_name(display_name)
    bridge_token_encrypted = encrypt_bridge_token(payload.get('bridge_token'), secret_key)

    with get_db_connection() as conn:
        existing = conn.execute("SELECT 1 FROM servers WHERE slug = ?", (slug,)).fetchone()
        if existing:
            slug = f"{slug}-{int(now)}"
        cursor = conn.execute(
            """
            INSERT INTO servers (
                slug, display_name, owner_label, connect_address, join_password,
                steam_lobby_id, bridge_url, bridge_token_encrypted, submitted_by, approved_by, approved_at,
                status, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', NULL, 'pending', 0, ?, ?)
            """,
            (
                slug,
                display_name,
                str(payload.get('owner_label') or '').strip(),
                str(payload.get('connect_address') or '').strip(),
                str(payload.get('join_password') or '').strip(),
                str(payload.get('steam_lobby_id') or '').strip(),
                bridge_url,
                bridge_token_encrypted,
                str(submitted_by or '').strip(),
                now,
                now,
            )
        )
        conn.commit()
        server_id = cursor.lastrowid
    return get_server_by_id(get_db_connection, server_id, secret_key)


def update_server_record(
    get_db_connection,
    secret_key,
    server_id,
    *,
    status=None,
    enabled=None,
    current_lobby_id=None,
    reserved_at=None,
    last_health_check_at=None,
    last_health_status=None,
    last_health_error=None,
    submitted_by=None,
    approved_by=None,
    approved_at=None,
    steam_lobby_id=None,
    capabilities=None,
    metadata=None,
):
    updates = []
    values = []
    if status is not None:
        updates.append("status = ?")
        values.append(status)
    if enabled is not None:
        updates.append("enabled = ?")
        values.append(1 if enabled else 0)
    if current_lobby_id is not None:
        updates.append("current_lobby_id = ?")
        values.append(current_lobby_id)
    if reserved_at is not None:
        updates.append("reserved_at = ?")
        values.append(reserved_at)
    if last_health_check_at is not None:
        updates.append("last_health_check_at = ?")
        values.append(last_health_check_at)
    if last_health_status is not None:
        updates.append("last_health_status = ?")
        values.append(last_health_status)
    if last_health_error is not None:
        updates.append("last_health_error = ?")
        values.append(last_health_error)
    if submitted_by is not None:
        updates.append("submitted_by = ?")
        values.append(submitted_by)
    if approved_by is not None:
        updates.append("approved_by = ?")
        values.append(approved_by)
    if approved_at is not None:
        updates.append("approved_at = ?")
        values.append(approved_at)
    if steam_lobby_id is not None:
        updates.append("steam_lobby_id = ?")
        values.append(steam_lobby_id)
    if capabilities is not None:
        updates.extend([
            "cap_players = ?",
            "cap_layer_change = ?",
            "cap_broadcast = ?",
            "cap_round_result = ?",
        ])
        values.extend([
            1 if capabilities.get('players') else 0,
            1 if capabilities.get('layer_change') else 0,
            1 if capabilities.get('broadcast') else 0,
            1 if capabilities.get('round_result') else 0,
        ])
    if metadata is not None:
        updates.append("metadata_json = ?")
        values.append(_to_json(metadata))
    updates.append("updated_at = ?")
    values.append(time.time())
    values.append(server_id)
    with get_db_connection() as conn:
        conn.execute(f"UPDATE servers SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
    return get_server_by_id(get_db_connection, server_id, secret_key)


def record_server_health_check(get_db_connection, server_id, result, error_message, health_payload):
    checked_at = time.time()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO server_health_checks (server_id, result, error, health_payload_json, checked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (server_id, result, error_message, _to_json(health_payload), checked_at)
        )
        conn.commit()
    return checked_at


def build_bridge_request_for_server(server_record):
    bridge_url = validate_bridge_url(server_record.get('bridge_url'))
    bridge_token = str(server_record.get('bridge_token') or '').strip()

    def request(path, method='GET', payload=None, timeout=5):
        return squadjs_bridge_request(
            path=path,
            bridge_url=bridge_url,
            bridge_token=bridge_token,
            payload=payload,
            method=method,
            timeout=timeout,
        )

    return request


def test_server_connection(server_payload):
    server_payload = server_payload or {}
    bridge_url = validate_bridge_url(server_payload.get('bridge_url'))
    bridge_request = build_bridge_request_for_server(server_payload)

    warnings = []
    bridge_health = get_bridge_health(bridge_request, bridge_url)
    if not bridge_health.get('ok'):
        raise BridgeUnavailable(bridge_health.get('error') or 'Bridge health check failed')

    server_info = fetch_server_info(bridge_request)
    players = fetch_connected_server_players(bridge_request)
    capabilities = {
        'players': isinstance(players, list),
        'layer_change': False,
        'broadcast': True,
        'round_result': False,
    }

    try:
        layers = fetch_all_layers(bridge_request)
        capabilities['layer_change'] = isinstance(layers, list)
        if not capabilities['layer_change']:
            warnings.append('Layer listing is unavailable.')
    except Exception as error:
        layers = []
        warnings.append(str(error))

    try:
        round_result = fetch_latest_round_result(bridge_request)
        capabilities['round_result'] = True
    except Exception as error:
        round_result = None
        warnings.append(f'Round result unavailable: {error}')

    result = {
        'bridgeReachable': True,
        'bridge': bridge_health,
        'serverInfo': server_info,
        'playerCount': len(players),
        'capabilities': capabilities,
        'warnings': warnings,
        'roundResult': round_result,
    }
    status = 'healthy' if all(capabilities.values()) else 'degraded'
    enrich_server_result_with_discovery(result, server_payload, status=status)
    return result


def run_server_health_check(get_db_connection, secret_key, server_id):
    server = get_server_by_id(get_db_connection, server_id, secret_key, include_secret=True)
    if not server:
        raise ValueError('Server not found')

    error_message = None
    try:
        result = test_server_connection(server)
        status = 'healthy' if all(result['capabilities'].values()) else 'degraded'
    except Exception as error:
        result = {
            'bridgeReachable': False,
            'capabilities': {
                'players': False,
                'layer_change': False,
                'broadcast': False,
                'round_result': False,
            },
            'warnings': [],
        }
        status = 'offline'
        error_message = str(error)

    discovered_steam_id, _, _ = enrich_server_result_with_discovery(
        result,
        server,
        status=status,
        error_message=error_message or '',
    )

    checked_at = record_server_health_check(get_db_connection, server_id, status, error_message, result)
    result['liveSession'] = build_live_session_snapshot(result, checked_at=checked_at)
    updated = update_server_record(
        get_db_connection,
        secret_key,
        server_id,
        status=status,
        last_health_check_at=checked_at,
        last_health_status=status,
        last_health_error=error_message or '',
        steam_lobby_id=str(discovered_steam_id).strip() if discovered_steam_id else None,
        capabilities=result.get('capabilities') or {},
        metadata=result,
    )
    return updated, result


def set_server_enabled(get_db_connection, secret_key, server_id, enabled):
    server = get_server_by_id(get_db_connection, server_id, secret_key)
    if not server:
        raise ValueError('Server not found')
    if enabled and server.get('status') == 'pending':
        raise ValueError('Server must be approved before it can be enabled')
    if enabled and server.get('last_health_status') not in {'healthy', 'degraded'}:
        raise ValueError('Run a successful health check before enabling this server')
    status = server.get('status')
    if enabled and status == 'offline':
        raise ValueError('Offline servers cannot be enabled')
    if not enabled and server.get('current_lobby_id'):
        raise ValueError('Cannot disable a server that is currently allocated to a lobby')
    return update_server_record(
        get_db_connection,
        secret_key,
        server_id,
        enabled=enabled,
        status=('disabled' if not enabled else server.get('last_health_status') or 'healthy')
    )


def approve_server(get_db_connection, secret_key, server_id, approved_by):
    server = get_server_by_id(get_db_connection, server_id, secret_key)
    if not server:
        raise ValueError('Server not found')
    if server.get('current_lobby_id'):
        raise ValueError('Cannot change approval while server is allocated')
    return update_server_record(
        get_db_connection,
        secret_key,
        server_id,
        status='approved',
        approved_by=str(approved_by or '').strip(),
        approved_at=time.time(),
    )


def list_available_servers(get_db_connection, secret_key):
    return [
        server for server in list_servers(get_db_connection, secret_key)
        if server.get('enabled') and server.get('status') in {'healthy', 'degraded', 'approved'} and not server.get('current_lobby_id')
    ]


def get_server_pool_capacity(get_db_connection, secret_key):
    servers = list_servers(get_db_connection, secret_key)
    if not servers:
        return 1
    capacity = len([
        server for server in servers
        if server.get('enabled') and server.get('status') in {'healthy', 'degraded', 'approved', 'reserved'}
    ])
    return max(0, capacity)


def allocate_server_for_lobby(get_db_connection, secret_key, lobby_id):
    available = list_available_servers(get_db_connection, secret_key)
    if not available:
        return None
    server = available[0]
    reserved_at = time.time()
    updated = update_server_record(
        get_db_connection,
        secret_key,
        server['id'],
        status='reserved',
        current_lobby_id=lobby_id,
        reserved_at=reserved_at,
    )
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO server_allocations (server_id, lobby_id, state, reserved_at)
            VALUES (?, ?, 'reserved', ?)
            """,
            (server['id'], lobby_id, reserved_at)
        )
        conn.commit()
    return updated


def release_server_allocation(get_db_connection, secret_key, lobby_id, reason='released'):
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM servers WHERE current_lobby_id = ?",
            (lobby_id,)
        ).fetchone()
        if not row:
            return None
        server_id = row['id']
        release_time = time.time()
        conn.execute(
            """
            UPDATE server_allocations
            SET state = 'released', released_at = ?, release_reason = ?
            WHERE server_id = ? AND lobby_id = ? AND state = 'reserved'
            """,
            (release_time, reason, server_id, lobby_id)
        )
        conn.commit()
    status = row['last_health_status'] or 'healthy'
    return update_server_record(
        get_db_connection,
        secret_key,
        server_id,
        status=status if row['enabled'] else 'disabled',
        current_lobby_id='',
        reserved_at=0,
    )


def build_squad_join_url(connect_address, join_password=''):
    connect_address = str(connect_address or '').strip()
    join_password = str(join_password or '').strip()
    if not connect_address:
        return ''
    if join_password:
        return f"steam://connect/{connect_address}/{quote(join_password, safe='')}"
    return f"steam://connect/{connect_address}"


def build_steam_lobby_join_url(steam_lobby_id):
    steam_lobby_id = str(steam_lobby_id or '').strip()
    if not steam_lobby_id:
        return ''
    return f"steam://joinlobby/393380/{steam_lobby_id}"
