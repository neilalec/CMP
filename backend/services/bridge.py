import json
import logging
import time
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import quote as url_quote


class BridgeUnavailable(RuntimeError):
    pass


def log_bridge_unavailable(bridge_status, error_message, interval_seconds):
    now = time.time()
    should_log = (
        bridge_status['last_logged_error'] != error_message
        or (now - bridge_status['last_logged_at']) >= interval_seconds
    )
    bridge_status['available'] = False
    bridge_status['last_error'] = error_message
    if should_log:
        logging.getLogger(__name__).warning(error_message)
        bridge_status['last_logged_error'] = error_message
        bridge_status['last_logged_at'] = now


def mark_bridge_available(bridge_status, bridge_url):
    if bridge_status['available'] is False:
        logging.getLogger(__name__).info(f"SquadJS bridge reachable again at {bridge_url}")
    bridge_status['available'] = True
    bridge_status['last_error'] = None


def squadjs_bridge_request(
    path,
    bridge_url,
    bridge_token='',
    payload=None,
    method='GET',
    timeout=5,
    bridge_status=None,
    error_log_interval_seconds=30
):
    url = f"{bridge_url}{path}"
    body = None
    headers = {
        'Accept': 'application/json'
    }

    if bridge_token:
        headers['Authorization'] = f"Bearer {bridge_token}"

    if payload is not None:
        body = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'

    req = urllib_request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib_request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode('utf-8')
            if bridge_status is not None:
                mark_bridge_available(bridge_status, bridge_url)
            return json.loads(raw) if raw else {}
    except urllib_error.HTTPError as e:
        if bridge_status is not None:
            mark_bridge_available(bridge_status, bridge_url)
        raw = e.read().decode('utf-8') if e.fp else ''
        try:
            details = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            details = {'error': raw or str(e)}
        raise RuntimeError(details.get('error') or f"Bridge request failed with HTTP {e.code}")
    except urllib_error.URLError as e:
        message = f"Unable to reach SquadJS bridge at {bridge_url}: {e.reason}"
        if bridge_status is not None:
            log_bridge_unavailable(bridge_status, message, error_log_interval_seconds)
        raise BridgeUnavailable(message)
    except json.JSONDecodeError as e:
        if bridge_status is not None:
            mark_bridge_available(bridge_status, bridge_url)
        raise RuntimeError(f"Invalid JSON from SquadJS bridge: {e}")


def get_database_health(get_db_connection, database_path):
    try:
        with get_db_connection() as conn:
            conn.execute('SELECT 1').fetchone()
        return {'ok': True, 'path': database_path}
    except Exception as e:
        return {'ok': False, 'path': database_path, 'error': str(e)}


def get_bridge_health(bridge_request, bridge_url):
    try:
        response = bridge_request('/health', timeout=2)
        return {
            'ok': True,
            'url': bridge_url,
            'details': response
        }
    except BridgeUnavailable as e:
        return {
            'ok': False,
            'url': bridge_url,
            'error': str(e)
        }
    except Exception as e:
        return {
            'ok': False,
            'url': bridge_url,
            'error': str(e)
        }


def build_bridge_unavailable_presence(lobby_id, lobby, error_message):
    team1_players = set(lobby.get('teams', {}).get('team1', []))
    team2_players = set(lobby.get('teams', {}).get('team2', []))
    rows = []

    for username in lobby.get('players', []):
        expected_team_id = None
        if username in team1_players:
            expected_team_id = 1
        elif username in team2_players:
            expected_team_id = 2

        rows.append({
            'username': username,
            'steam_id': '',
            'expectedTeamId': expected_team_id,
            'connected': False,
            'actualTeamId': None,
            'actualSquadId': None,
            'eosID': None,
            'serverName': None
        })

    return {
        'lobby_id': lobby_id,
        'players': rows,
        'connected': [],
        'missing': [row['username'] for row in rows],
        'bridgeAvailable': False,
        'bridgeError': error_message
    }


def fetch_connected_server_players(bridge_request):
    response = bridge_request('/players')
    return response.get('players', [])


def fetch_layers_by_name(name, bridge_request):
    encoded_name = url_quote(str(name or '').strip(), safe='')
    response = bridge_request(f'/layers?name={encoded_name}')
    return response.get('layers', [])


def fetch_all_layers(bridge_request):
    response = bridge_request('/layers')
    return response.get('layers', [])


def normalize_layer_name(name):
    text = str(name or '').strip().lower().replace('_', ' ')
    normalized = []
    token = []
    for char in text:
        if char.isalnum():
            token.append(char)
        elif token:
            normalized.append(''.join(token))
            token = []
    if token:
        normalized.append(''.join(token))

    ignored_tokens = {'bala', 'toi'}
    return ' '.join(part for part in normalized if part not in ignored_tokens)


def resolve_selected_map_layer_id(selected_map, bridge_request):
    map_aliases = {
        'Kohat Skirmish v1': 'Kohat Toi Skirmish v1',
        'Sumari Skirmish v1': 'Sumari Bala Skirmish v1'
    }
    resolved_name = map_aliases.get(selected_map, selected_map)
    layers = fetch_layers_by_name(resolved_name, bridge_request)
    if not layers:
        all_layers = fetch_all_layers(bridge_request)
        exact_name = [
            layer for layer in all_layers
            if (layer.get('name') or '').strip().lower() == str(resolved_name).strip().lower()
        ]
        if exact_name:
            layers = exact_name
        else:
            target = normalize_layer_name(resolved_name)
            normalized_matches = []
            for layer in all_layers:
                candidates = {
                    normalize_layer_name(layer.get('name')),
                    normalize_layer_name(layer.get('layerId')),
                    normalize_layer_name(layer.get('classname'))
                }
                if target in candidates:
                    normalized_matches.append(layer)
            layers = normalized_matches

    if not layers:
        raise RuntimeError(f'Could not resolve selected map "{selected_map}" to a Squad layer id.')
    return layers[0].get('layerId') or layers[0].get('classname')


def change_server_to_selected_map(selected_map, bridge_request):
    layer_id = resolve_selected_map_layer_id(selected_map, bridge_request)
    return bridge_request('/layer/change', method='POST', payload={
        'layer': layer_id
    })


def broadcast_server_message(message, bridge_request):
    return bridge_request('/broadcast', method='POST', payload={
        'message': message
    })


def build_lobby_server_presence(
    lobby_id,
    lobbies,
    get_user_profile,
    bridge_request,
    tolerate_bridge_unavailable=False
):
    lobby = lobbies.get(lobby_id)
    if not lobby:
        raise ValueError('Lobby not found')

    try:
        connected_players = fetch_connected_server_players(bridge_request)
    except BridgeUnavailable as e:
        if tolerate_bridge_unavailable:
            return build_bridge_unavailable_presence(lobby_id, lobby, str(e))
        raise

    players_by_steam_id = {
        str(player.get('steamID') or '').strip(): player
        for player in connected_players
        if player.get('steamID')
    }

    team1_players = set(lobby.get('teams', {}).get('team1', []))
    team2_players = set(lobby.get('teams', {}).get('team2', []))

    presence = []
    connected_usernames = []
    missing_usernames = []

    for username in lobby.get('players', []):
        profile = get_user_profile(username) or {}
        steam_id = profile.get('steam_id', '')
        connected_player = players_by_steam_id.get(steam_id) if steam_id else None

        expected_team_id = None
        if username in team1_players:
            expected_team_id = 1
        elif username in team2_players:
            expected_team_id = 2

        row = {
            'username': username,
            'steam_id': steam_id,
            'expectedTeamId': expected_team_id,
            'connected': bool(connected_player),
            'actualTeamId': connected_player.get('teamID') if connected_player else None,
            'actualSquadId': connected_player.get('squadID') if connected_player else None,
            'eosID': connected_player.get('eosID') if connected_player else None,
            'serverName': connected_player.get('name') if connected_player else None
        }
        presence.append(row)

        if row['connected']:
            connected_usernames.append(username)
        else:
            missing_usernames.append(username)

    return {
        'lobby_id': lobby_id,
        'players': presence,
        'connected': connected_usernames,
        'missing': missing_usernames,
        'bridgeAvailable': True,
        'bridgeError': None
    }
