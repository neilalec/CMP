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
    except Exception as error:
        return {
            'ok': False,
            'url': bridge_url,
            'error': str(error)
        }


def fetch_server_info(bridge_request):
    response = bridge_request('/server')
    return response or {}


def create_synthetic_lobby_join_url(bridge_request, session_id):
    response = bridge_request(
        '/join/synthetic-lobby',
        method='POST',
        payload={
            'sessionId': str(session_id or '').strip(),
        },
        timeout=15
    )
    return response or {}


def fetch_latest_round_result(bridge_request):
    response = bridge_request('/round/latest')
    return response.get('round') if response else None


def build_server_connection_details(
    bridge_request,
    configured_name='',
    password='',
    connect_address='',
    steam_lobby_id=''
):
    bridge_info = {}
    bridge_available = True
    bridge_error = None

    try:
        bridge_info = fetch_server_info(bridge_request)
    except Exception as error:
        bridge_available = False
        bridge_error = str(error)

    server_name = (
        configured_name
        or bridge_info.get('serverName')
        or bridge_info.get('name')
        or ''
    )
    resolved_steam_lobby_id = steam_lobby_id or ''

    return {
        'serverName': server_name,
        'password': password or '',
        'connectAddress': connect_address or '',
        'bridgeAvailable': bridge_available,
        'bridgeError': bridge_error,
        'steam_lobby_id': resolved_steam_lobby_id,
        'bridge': bridge_info
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
        'unauthorizedPlayers': [],
        'connected': [],
        'connectedSteamIds': [],
        'missing': [row['username'] for row in rows],
        'bridgeAvailable': False,
        'bridgeError': error_message
    }


def fetch_connected_server_players(bridge_request):
    response = bridge_request('/players')
    return response.get('players', [])


def force_team_change(steam_id, bridge_request):
    if not steam_id:
        raise RuntimeError('steam_id is required to force a team change.')
    return bridge_request('/players/force-team-change', method='POST', payload={
        'player': str(steam_id).strip()
    })


def kick_player(player_id, bridge_request, reason='Match complete.'):
    if not player_id:
        raise RuntimeError('player_id is required to kick a player.')
    return bridge_request('/players/kick', method='POST', payload={
        'player': str(player_id).strip(),
        'reason': str(reason or 'Match complete.').strip()
    })


def end_match(bridge_request):
    return bridge_request('/match/end', method='POST', payload={})


def fetch_layers_by_name(name, bridge_request):
    encoded_name = url_quote(str(name or '').strip(), safe='')
    response = bridge_request(f'/layers?name={encoded_name}')
    return response.get('layers', [])


def fetch_all_layers(bridge_request):
    response = bridge_request('/layers')
    return response.get('layers', [])


CURATED_LAYER_TEAM_LABELS = {
    'AlBasrah_Skirmish_v2': {
        'team1': 'USA',
        'team2': 'MEI'
    }
}


FACTION_CODE_LABELS = {
    'ADF': 'ADF',
    'BAF': 'BAF',
    'CAF': 'CAF',
    'GFI': 'GFI',
    'IMF': 'IMF',
    'INS': 'INS',
    'MEA': 'MEA',
    'MEI': 'MEI',
    'PLA': 'PLA',
    'PLANMC': 'PLANMC',
    'RGF': 'RGF',
    'TLF': 'TLF',
    'USA': 'USA',
    'USAF': 'USAF',
    'USMC': 'USMC',
    'VDV': 'VDV',
    'WPMC': 'WPMC'
}


FACTION_NAME_LABELS = {
    'australian defence force': 'ADF',
    'british armed forces': 'BAF',
    'canadian armed forces': 'CAF',
    'insurgent forces': 'INS',
    'irregular militia forces': 'IMF',
    'middle eastern alliance': 'MEA',
    'middle eastern insurgents': 'MEI',
    'people\'s liberation army': 'PLA',
    'pla navy marine corps': 'PLANMC',
    'russian ground forces': 'RGF',
    'turkish land forces': 'TLF',
    'united states army': 'USA',
    'united states air force': 'USAF',
    'united states marine corps': 'USMC',
    'russian airborne forces': 'VDV'
}


def decode_server_info_team_label(value):
    text = str(value or '').strip()
    if not text:
        return ''

    natural = text.lower()
    if natural in FACTION_NAME_LABELS:
        return FACTION_NAME_LABELS[natural]

    code = text.split('_', 1)[0].strip().upper()
    return FACTION_CODE_LABELS.get(code, code)


def build_team_labels_from_server_info_teams(server_info_teams):
    if not isinstance(server_info_teams, dict):
        return {}

    team_one = decode_server_info_team_label(
        server_info_teams.get('teamOne') or server_info_teams.get('rawTeamOne')
    )
    team_two = decode_server_info_team_label(
        server_info_teams.get('teamTwo') or server_info_teams.get('rawTeamTwo')
    )
    labels = {}
    if team_one:
        labels['team1'] = team_one
    if team_two:
        labels['team2'] = team_two
    return labels


def build_team_labels_from_squad_team_names(squad_team_names):
    if not isinstance(squad_team_names, dict):
        return {}

    labels = {}
    for key in ('team1', 'team2'):
        label = decode_server_info_team_label(squad_team_names.get(key))
        if label:
            labels[key] = label
    return labels


def labels_are_complete(labels):
    return bool(labels.get('team1') and labels.get('team2'))


def build_verified_live_team_labels(server_info):
    if not isinstance(server_info, dict):
        return {}

    server_info_labels = build_team_labels_from_server_info_teams(
        server_info.get('serverInfoTeams')
    )
    squad_team_labels = build_team_labels_from_squad_team_names(
        server_info.get('squadTeamNames')
    )

    if not labels_are_complete(server_info_labels) or not labels_are_complete(squad_team_labels):
        return {}
    if server_info_labels != squad_team_labels:
        return {}
    return server_info_labels


def build_team_labels_from_layer_info(layer_info):
    teams = layer_info.get('teams') if isinstance(layer_info, dict) else []
    if not isinstance(teams, list):
        return {}

    labels = {}
    for index, team in enumerate(teams[:2], start=1):
        if not isinstance(team, dict):
            continue
        label = str(team.get('faction') or team.get('name') or '').strip()
        if label:
            labels[f'team{index}'] = label
    return labels


def get_curated_team_labels(selected_map):
    resolved_name = resolve_selected_map_name(selected_map)
    for layer_name, labels in CURATED_LAYER_TEAM_LABELS.items():
        if layer_matches_selected_map(resolved_name, layer_name) or layer_matches_selected_map(selected_map, layer_name):
            return dict(labels)
    return {}


def get_live_server_team_labels(selected_map, bridge_request):
    try:
        info = fetch_server_info(bridge_request)
    except Exception:
        return {}

    current_layer_info = info.get('currentLayerInfo')
    current_matches = (
        layer_info_matches_selected_map(current_layer_info, selected_map)
        or layer_info_matches_selected_map(info.get('currentLayer'), selected_map)
        or layer_matches_selected_map(info.get('currentLayerRaw'), selected_map)
        or layer_matches_selected_map(info.get('currentLayerName'), selected_map)
        or layer_matches_selected_map(info.get('currentLayerClassname'), selected_map)
        or layer_matches_selected_map(info.get('currentLayerId'), selected_map)
    )
    if current_matches:
        labels = build_verified_live_team_labels(info)
        if labels:
            return labels

    next_layer_info = info.get('nextLayerInfo')
    if layer_info_matches_selected_map(next_layer_info, selected_map):
        labels = build_team_labels_from_layer_info(next_layer_info)
        if labels:
            return labels
    return {}


def get_selected_map_team_labels(selected_map, bridge_request):
    labels = get_curated_team_labels(selected_map)
    if labels:
        return labels

    labels = get_live_server_team_labels(selected_map, bridge_request)
    if labels:
        return labels

    layer_info = resolve_selected_map_layer_info(selected_map, bridge_request)
    return build_team_labels_from_layer_info(layer_info)


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


def is_hotdrop_layer_name(name):
    normalized = normalize_hotdrop_layer_name(name)
    return normalized.startswith('hotdrop ')


def normalize_hotdrop_layer_name(name):
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
    return ' '.join(normalized)


def layer_matches_selected_map(layer_value, selected_map):
    if not layer_value or not selected_map:
        return False

    resolved_selected_map = resolve_selected_map_name(selected_map)

    if is_hotdrop_layer_name(selected_map) or is_hotdrop_layer_name(resolved_selected_map):
        if not is_hotdrop_layer_name(layer_value):
            return False
        return normalize_hotdrop_layer_name(layer_value) in {
            normalize_hotdrop_layer_name(selected_map),
            normalize_hotdrop_layer_name(resolved_selected_map)
        }

    normalized_layer = normalize_layer_name(layer_value)
    selected_candidates = {
        normalize_layer_name(selected_map),
        normalize_layer_name(resolved_selected_map)
    }
    return normalized_layer in selected_candidates


def layer_info_matches_selected_map(layer_info, selected_map):
    if not layer_info or not selected_map:
        return False

    if isinstance(layer_info, dict):
        candidates = [
            layer_info.get('layerId'),
            layer_info.get('layerid'),
            layer_info.get('classname'),
            layer_info.get('layerClassname'),
            layer_info.get('name')
        ]
        return any(
            layer_matches_selected_map(candidate, selected_map)
            for candidate in candidates
            if candidate
        )

    return layer_matches_selected_map(layer_info, selected_map)


def resolve_selected_map_layer_id(selected_map, bridge_request):
    layer_info = resolve_selected_map_layer_info(selected_map, bridge_request)
    if layer_info:
        return layer_info.get('layerId') or layer_info.get('classname')

    resolved_name = resolve_selected_map_name(selected_map)
    if isinstance(resolved_name, str) and ' ' not in resolved_name and '_' in resolved_name:
        return resolved_name
    raise RuntimeError(f'Could not resolve selected map "{selected_map}" to a Squad layer id.')


def resolve_selected_map_name(selected_map):
    map_aliases = {
        'Al Basrah Skirmish v1': 'AlBasrah_Skirmish_v1',
        'Al Basrah Skirmish v2': 'AlBasrah_Skirmish_v2',
        "Fool's Road Skirmish v1": 'FoolsRoad_Skirmish_v1',
        "Fool's Road Skirmish v2": 'FoolsRoad_Skirmish_v2',
        'Kohat Skirmish v1': 'Kohat_Skirmish_v1',
        'Kohat Toi Skirmish v1': 'Kohat_Skirmish_v1',
        'Logar Valley Skirmish v1': 'Logar_Skirmish_v1',
        'Sumari Skirmish v1': 'Sumari_Skirmish_v1',
        'Sumari Bala Skirmish v1': 'Sumari_Skirmish_v1',
        'Tallil Outskirts Skirmish v1': 'Tallil_Skirmish_v1',
        'Tallil Outskirts Skirmish v2': 'Tallil_Skirmish_v2'
    }
    return map_aliases.get(selected_map, selected_map)


def resolve_selected_map_layer_info(selected_map, bridge_request):
    resolved_name = resolve_selected_map_name(selected_map)

    # Workshop and command-ready layer identifiers can already be valid RCON targets.
    # HotDrop layers are selected in this exact form, e.g. "HotDrop_Fallujah".
    if isinstance(resolved_name, str) and resolved_name.startswith('HotDrop_'):
        layers = fetch_layers_by_name(resolved_name, bridge_request)
        return layers[0] if layers else None

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
        return None
    return layers[0]


def change_server_to_selected_map(selected_map, bridge_request):
    layer_id = resolve_selected_map_layer_id(selected_map, bridge_request)
    return bridge_request('/layer/change', method='POST', payload={
        'layer': layer_id
    })


def set_next_server_map(selected_map, bridge_request):
    layer_id = resolve_selected_map_layer_id(selected_map, bridge_request)
    return bridge_request('/layer/next', method='POST', payload={
        'layer': layer_id
    })


def get_server_layer_status(selected_map, bridge_request):
    info = fetch_server_info(bridge_request)
    current_layer = info.get('currentLayer')
    next_layer = info.get('nextLayer')
    current_layer_info = info.get('currentLayerInfo') or {}
    next_layer_info = info.get('nextLayerInfo') or {}
    current_matches = (
        layer_info_matches_selected_map(current_layer_info, selected_map)
        or layer_info_matches_selected_map(current_layer, selected_map)
        or layer_matches_selected_map(info.get('currentLayerRaw'), selected_map)
        or layer_matches_selected_map(info.get('currentLayerName'), selected_map)
        or layer_matches_selected_map(info.get('currentLayerClassname'), selected_map)
        or layer_matches_selected_map(info.get('currentLayerId'), selected_map)
    )
    next_matches = (
        layer_info_matches_selected_map(next_layer_info, selected_map)
        or layer_info_matches_selected_map(next_layer, selected_map)
        or layer_matches_selected_map(info.get('nextLayerRaw'), selected_map)
        or layer_matches_selected_map(info.get('nextLayerName'), selected_map)
        or layer_matches_selected_map(info.get('nextLayerClassname'), selected_map)
        or layer_matches_selected_map(info.get('nextLayerId'), selected_map)
    )
    live_team_labels = build_verified_live_team_labels(info) if current_matches else {}
    return {
        'serverInfo': info,
        'currentLayer': current_layer,
        'nextLayer': next_layer,
        'currentLayerInfo': current_layer_info,
        'nextLayerInfo': next_layer_info,
        'teamLabels': live_team_labels,
        'currentMatches': current_matches,
        'nextMatches': next_matches
    }


def broadcast_server_message(message, bridge_request):
    return bridge_request('/broadcast', method='POST', payload={
        'message': message
    })


def build_lobby_server_presence(
    lobby_id,
    lobbies,
    get_user_profile,
    bridge_request,
    is_bypass_steam_id=None,
    is_team_bypass_steam_id=None,
    tolerate_bridge_unavailable=False
):
    lobby = lobbies.get(lobby_id)
    if not lobby:
        raise ValueError('Lobby not found')

    try:
        connected_players = fetch_connected_server_players(bridge_request)
    except Exception as error:
        if tolerate_bridge_unavailable:
            return build_bridge_unavailable_presence(lobby_id, lobby, str(error))
        raise

    players_by_steam_id = {
        str(player.get('steamID') or '').strip(): player
        for player in connected_players
        if player.get('steamID')
    }
    connected_steam_ids = [
        str(player.get('steamID') or '').strip()
        for player in connected_players
        if player.get('steamID')
    ]

    team1_players = set(lobby.get('teams', {}).get('team1', []))
    team2_players = set(lobby.get('teams', {}).get('team2', []))

    presence = []
    expected_steam_ids = set()
    connected_usernames = []
    missing_usernames = []
    aligned_usernames = []
    mismatched_usernames = []

    for username in lobby.get('players', []):
        profile = get_user_profile(username) or {}
        steam_id = str(profile.get('steam_id') or '').strip()
        admin_bypass = bool(is_bypass_steam_id and steam_id and is_bypass_steam_id(steam_id))
        team_bypass = (
            bool(is_team_bypass_steam_id and steam_id and is_team_bypass_steam_id(steam_id))
            if is_team_bypass_steam_id is not None
            else admin_bypass
        )
        if steam_id:
            expected_steam_ids.add(steam_id)
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
            'serverName': connected_player.get('name') if connected_player else None,
            'adminBypass': admin_bypass,
            'teamBypass': team_bypass,
            'teamAligned': bool(
                connected_player
                and (
                    team_bypass
                    or
                    expected_team_id is None
                    or connected_player.get('teamID') == expected_team_id
                )
            )
        }
        presence.append(row)

        if row['connected']:
            connected_usernames.append(username)
            if row['teamAligned']:
                aligned_usernames.append(username)
            else:
                mismatched_usernames.append(username)
        else:
            missing_usernames.append(username)

    unauthorized_players = [
        {
            'steam_id': str(player.get('steamID') or '').strip(),
            'eosID': player.get('eosID'),
            'serverName': player.get('name'),
            'actualTeamId': player.get('teamID'),
            'actualSquadId': player.get('squadID')
        }
        for player in connected_players
        if (
            str(player.get('steamID') or '').strip() not in expected_steam_ids
            and not (
                is_bypass_steam_id
                and str(player.get('steamID') or '').strip()
                and is_bypass_steam_id(str(player.get('steamID') or '').strip())
            )
        )
    ]

    return {
        'lobby_id': lobby_id,
        'players': presence,
        'unauthorizedPlayers': unauthorized_players,
        'connected': connected_usernames,
        'connectedSteamIds': connected_steam_ids,
        'aligned': aligned_usernames,
        'mismatched': mismatched_usernames,
        'missing': missing_usernames,
        'bridgeAvailable': True,
        'bridgeError': None
    }
