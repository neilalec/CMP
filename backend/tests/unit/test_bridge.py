from services.bridge import (
    build_lobby_server_presence,
    build_server_connection_details,
    build_team_labels_from_server_info_teams,
    build_verified_live_team_labels,
    resolve_selected_map_layer_id,
    get_selected_map_team_labels,
    get_server_layer_status,
)
from services.server_registry import (
    _extract_eos_advertised_session,
    _extract_eos_network_identity,
    _extract_eos_server_name,
    _build_eos_basic_auth_header,
    build_live_session_snapshot,
    build_join_url_from_server_details,
    fetch_eos_access_token,
    extract_session_target_id,
    lookup_eos_matchmaking_session,
    lookup_local_log_session_id,
    parse_a2s_info_steam_id,
)


def test_build_server_connection_details_uses_provided_steam_lobby_id():
    details = build_server_connection_details(
        bridge_request=lambda path: {'serverName': '4K War Server', 'host': '164.152.123.232', 'queryPort': 27165},
        configured_name='4K War Server',
        password='secretpass',
        connect_address='164.152.123.232:7787',
        steam_lobby_id='109775243617917159',
    )

    assert details['serverName'] == '4K War Server'
    assert details['steam_lobby_id'] == '109775243617917159'


def test_lobby_presence_includes_raw_connected_steam_ids():
    lobbies = {
        'lobby_1': {
            'players': ['alice'],
            'teams': {'team1': ['alice'], 'team2': []},
        }
    }

    presence = build_lobby_server_presence(
        'lobby_1',
        lobbies,
        get_user_profile=lambda username: {'steam_id': '76561198000000001'},
        bridge_request=lambda path: {
            'players': [
                {'name': 'alice', 'steamID': '76561198000000001', 'teamID': 1},
                {'name': 'neil', 'steamID': '76561198124553635', 'teamID': 1},
            ]
        }
    )

    assert presence['connected'] == ['alice']
    assert presence['connectedSteamIds'] == ['76561198000000001', '76561198124553635']
    assert presence['unauthorizedPlayers'] == [
        {
            'steam_id': '76561198124553635',
            'eosID': None,
            'serverName': 'neil',
            'actualTeamId': 1,
            'actualSquadId': None
        }
    ]


def test_selected_map_team_labels_use_layer_factions():
    def bridge_request(path):
        if path.startswith('/layers?name='):
            return {
                'layers': [
                    {
                        'name': 'S3O_36_Harju_AAS_v3',
                        'layerId': 'S3O_36_Harju_AAS_v3',
                        'teams': [
                            {'faction': 'USA', 'name': 'United States Army'},
                            {'faction': 'RGF', 'name': 'Russian Ground Forces'},
                        ],
                    }
                ]
            }
        raise AssertionError(f'unexpected bridge path: {path}')

    assert get_selected_map_team_labels('S3O_36_Harju_AAS_v3', bridge_request) == {
        'team1': 'USA',
        'team2': 'RGF',
    }


def test_selected_map_team_labels_use_curated_override_before_layer_metadata():
    def bridge_request(path):
        raise AssertionError(f'curated faction labels should not call bridge: {path}')

    assert get_selected_map_team_labels('Al Basrah Skirmish v2', bridge_request) == {
        'team1': 'USA',
        'team2': 'MEI',
    }


def test_selected_map_team_labels_can_use_verified_live_server_info():
    def bridge_request(path):
        if path == '/server':
            return {
                'currentLayer': 'Narva_Skirmish_v1',
                'currentLayerInfo': {
                    'layerId': 'Narva_Skirmish_v1',
                    'teams': [
                        {'faction': 'BAF', 'name': 'British Army'},
                        {'faction': 'RGF', 'name': 'Russian Ground Forces'},
                    ],
                },
                'serverInfoTeams': {
                    'teamOne': 'BAF_S_CombinedArms_Skirmish',
                    'teamTwo': 'RGF_S_CombinedArms_Skirmish',
                },
                'squadTeamNames': {
                    'team1': 'British Armed Forces',
                    'team2': 'Russian Ground Forces',
                },
            }
        raise AssertionError(f'unexpected bridge path: {path}')

    assert get_selected_map_team_labels('Narva Skirmish v1', bridge_request) == {
        'team1': 'BAF',
        'team2': 'RGF',
    }


def test_server_info_team_labels_decode_faction_prefixes():
    assert build_team_labels_from_server_info_teams({
        'teamOne': 'USA_S_CombinedArms_Skirmish',
        'teamTwo': 'MEI_S_LightInfantry_Skirmish',
    }) == {
        'team1': 'USA',
        'team2': 'MEI',
    }


def test_selected_map_team_labels_prefer_live_server_info_for_current_layer():
    def bridge_request(path):
        if path == '/server':
            return {
                'currentLayer': 'Kohat_Skirmish_v1',
                'currentLayerInfo': {
                    'layerId': 'Kohat_Skirmish_v1',
                    'teams': [
                        {'faction': 'United States Army', 'name': '149th Brigade'},
                        {'faction': 'British Armed Forces', 'name': 'Grenadier Guards'},
                    ],
                },
                'serverInfoTeams': {
                    'teamOne': 'USA_S_CombinedArms_Skirmish',
                    'teamTwo': 'MEI_S_LightInfantry_Skirmish',
                },
                'squadTeamNames': {
                    'team1': 'United States Army',
                    'team2': 'Middle Eastern Insurgents',
                }
            }
        raise AssertionError(f'unexpected bridge path: {path}')

    assert get_selected_map_team_labels('Kohat Skirmish v1', bridge_request) == {
        'team1': 'USA',
        'team2': 'MEI',
    }


def test_server_layer_status_includes_live_team_labels_for_current_match():
    def bridge_request(path):
        assert path == '/server'
        return {
            'currentLayer': 'Tallil_Skirmish_v2',
            'serverInfoTeams': {
                'teamOne': 'BAF_S_CombinedArms_Skirmish',
                'teamTwo': 'GFI_S_CombinedArms_Skirmish',
            },
            'squadTeamNames': {
                'team1': 'British Armed Forces',
                'team2': 'GFI',
            }
        }

    status = get_server_layer_status('Tallil Outskirts Skirmish v2', bridge_request)

    assert status['currentMatches'] is True
    assert status['teamLabels'] == {
        'team1': 'BAF',
        'team2': 'GFI',
    }


def test_verified_live_team_labels_require_sources_to_agree():
    assert build_verified_live_team_labels({
        'serverInfoTeams': {
            'teamOne': 'GFI_S_CombinedArms_Skirmish',
            'teamTwo': 'MEI_S_CombinedArms_Skirmish',
        },
        'squadTeamNames': {
            'team1': 'MEI',
            'team2': 'GFI',
        }
    }) == {}


def test_server_layer_status_omits_unverified_live_team_labels():
    def bridge_request(path):
        assert path == '/server'
        return {
            'currentLayer': 'Kokan_Skirmish_v1',
            'serverInfoTeams': {
                'teamOne': 'GFI_S_CombinedArms_Skirmish',
                'teamTwo': 'MEI_S_CombinedArms_Skirmish',
            },
            'squadTeamNames': {
                'team1': 'MEI',
                'team2': 'GFI',
            }
        }

    status = get_server_layer_status('Kokan Skirmish v1', bridge_request)

    assert status['currentMatches'] is True
    assert status['teamLabels'] == {}


def test_skirmish_display_names_resolve_to_rcon_layer_ids():
    aliases = {
        'Al Basrah Skirmish v1': 'AlBasrah_Skirmish_v1',
        'Al Basrah Skirmish v2': 'AlBasrah_Skirmish_v2',
        "Fool's Road Skirmish v1": 'FoolsRoad_Skirmish_v1',
        "Fool's Road Skirmish v2": 'FoolsRoad_Skirmish_v2',
        'Kohat Toi Skirmish v1': 'Kohat_Skirmish_v1',
        'Logar Valley Skirmish v1': 'Logar_Skirmish_v1',
        'Sumari Skirmish v1': 'Sumari_Skirmish_v1',
        'Tallil Outskirts Skirmish v1': 'Tallil_Skirmish_v1',
        'Tallil Outskirts Skirmish v2': 'Tallil_Skirmish_v2',
    }

    for display_name, layer_id in aliases.items():
        assert resolve_selected_map_layer_id(
            display_name,
            bridge_request=lambda path: {'layers': []}
        ) == layer_id


def test_parse_a2s_info_extracts_steam_id_from_edf():
    steam_id = 109775243617917159
    payload = (
        b'\xff\xff\xff\xff'
        + bytes([0x49, 0x11])
        + b'4K War Server\x00'
        + b'AlBasrah_Invasion_v1\x00'
        + b'SquadGame\x00'
        + b'Squad\x00'
        + b'\x84\x00'
        + bytes([0, 100, 0])
        + b'd'
        + b'l'
        + bytes([0, 1])
        + b'8.2.0.0\x00'
        + bytes([0x10])
        + steam_id.to_bytes(8, 'little')
    )

    assert parse_a2s_info_steam_id(payload) == str(steam_id)


def test_extract_session_target_id_from_redpoint_format():
    assert extract_session_target_id('Session:4K-WAR-LIVE-ID') == '4K-WAR-LIVE-ID'
    assert extract_session_target_id('not-a-session-value') == ''


def test_extract_eos_helpers_from_attributes():
    attributes = {
        'SERVERNAME_s': '4K War Server',
        'ADVERTISEDSESSIONID_s': 'Session:EOS-SESSION-12345',
    }

    assert _extract_eos_server_name(attributes) == '4K War Server'
    assert _extract_eos_advertised_session(attributes) == (
        'Session:EOS-SESSION-12345',
        'ADVERTISEDSESSIONID_s',
    )


def test_extract_eos_network_identity_from_generic_attributes():
    attributes = {
        'SERVERIP_s': '164.152.123.232',
        'QUERYPORT_n': 27052,
        'ServerConnectionUrl_s': '164.152.123.232:27050',
    }

    assert _extract_eos_network_identity(attributes) == {
        'connectAddress': '164.152.123.232:27050',
        'host': '164.152.123.232',
        'queryPort': 27052,
        'gamePort': 27050,
    }


def test_lookup_eos_matchmaking_session_prefers_connect_address(monkeypatch):
    payload = {
        'sessions': [
            {
                'attributes': {
                    'SERVERNAME_s': '4K War Server',
                    'ADVERTISEDSESSIONID_s': 'Session:WRONG-SESSION',
                    'ServerConnectionUrl_s': '10.0.0.10:27050',
                    'QUERYPORT_n': 27052,
                }
            },
            {
                'attributes': {
                    'SERVERNAME_s': '4K War Server',
                    'ADVERTISEDSESSIONID_s': 'Session:RIGHT-SESSION',
                    'ServerConnectionUrl_s': '164.152.123.232:27050',
                    'QUERYPORT_n': 27052,
                }
            },
        ]
    }

    monkeypatch.setattr(
        'services.server_registry.fetch_eos_access_token',
        lambda timeout=5: ('live-token', {'configured': True}),
    )

    class _FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            import json
            return json.dumps(payload).encode('utf-8')

    monkeypatch.setattr('services.server_registry.urllib_request.urlopen', lambda request, timeout=5: _FakeResponse())

    target_server_id, details = lookup_eos_matchmaking_session(
        '4K War Server',
        connect_address='164.152.123.232:27050',
        host='164.152.123.232',
        query_port=27052,
    )

    assert target_server_id == 'RIGHT-SESSION'
    assert details['matched'] is True
    assert details['selectedServerName'] == '4K War Server'
    assert details['candidates'][1]['connectAddressMatched'] is True


def test_build_join_url_from_server_details_prefers_strategy_then_connect():
    assert build_join_url_from_server_details({
        'joinStrategy': {
            'joinMethod': 'steam_lobby',
            'target': '109775243617917159',
        },
        'password': 'secretpass',
        'connectAddress': '127.0.0.1:7787',
    }) == 'steam://joinlobby/393380/109775243617917159'

    assert build_join_url_from_server_details({
        'joinStrategy': {
            'joinMethod': 'direct_connect',
            'target': '127.0.0.1:7787',
        },
        'password': 'secretpass',
    }) == 'steam://connect/127.0.0.1:7787/secretpass'


def test_build_eos_basic_auth_header():
    assert _build_eos_basic_auth_header('client', 'secret') == 'Basic Y2xpZW50OnNlY3JldA=='


def test_fetch_eos_access_token_prefers_env_token(monkeypatch):
    monkeypatch.setenv('EOS_ACCESS_TOKEN', 'live-token')
    token, details = fetch_eos_access_token()
    assert token == 'live-token'
    assert details['source'] == 'env_access_token'
    assert details['configured'] is True


def test_fetch_eos_access_token_reports_missing_config(monkeypatch):
    monkeypatch.delenv('EOS_ACCESS_TOKEN', raising=False)
    monkeypatch.delenv('EOS_CLIENT_ID', raising=False)
    monkeypatch.delenv('EOS_CLIENT_SECRET', raising=False)
    monkeypatch.delenv('EOS_STEAM_SESSION_TICKET_HEX', raising=False)
    token, details = fetch_eos_access_token()
    assert token == ''
    assert details['configured'] is False
    assert details['error'] == 'EOS access token not configured'


def test_build_live_session_snapshot_marks_local_log_match_fresh(monkeypatch):
    monkeypatch.setenv('LIVE_SESSION_FRESHNESS_SECONDS', '1800')
    snapshot = build_live_session_snapshot(
        {
            'sessionDiscovery': {
                'matched': True,
                'targetServerId': '10afa1f20f534c248561dd53a25356e2',
                'sourceField': 'local_squad_log.RedpointEOSRoomId',
            },
            'eosDiscovery': {
                'clientLog': {
                    'sessionId': 'Session:10afa1f20f534c248561dd53a25356e2',
                    'roomId': 'Session:10afa1f20f534c248561dd53a25356e2',
                    'connectAddress': '164.152.123.232:27050',
                }
            },
            'joinStrategy': {
                'target': '164.152.123.232:27050',
            },
        },
        checked_at=1000,
        now=1005,
    )

    assert snapshot['matched'] is True
    assert snapshot['targetServerId'] == '10afa1f20f534c248561dd53a25356e2'
    assert snapshot['source'] == 'local_squad_log'
    assert snapshot['roomId'] == 'Session:10afa1f20f534c248561dd53a25356e2'
    assert snapshot['connectAddress'] == '164.152.123.232:27050'
    assert snapshot['fresh'] is True


def test_lookup_local_log_session_id_matches_connect_address(tmp_path, monkeypatch):
    log_path = tmp_path / 'SquadGame.log'
    log_path.write_text(
        "\n".join([
            "[2026.06.17-16.30.22:234][936]LogOnlineSession: Verbose: OSS:           RedpointEOSRoomId=Session:10afa1f20f534c248561dd53a25356e2 : OnlineServiceAndPing",
            "[2026.06.17-16.30.22:234][936]LogOnline: Join session: traveling to 164.152.123.232:27050",
        ]),
        encoding='utf-8',
    )
    monkeypatch.setenv('SQUAD_CLIENT_LOG_PATH', str(log_path))

    target_server_id, details = lookup_local_log_session_id('164.152.123.232:27050')

    assert target_server_id == '10afa1f20f534c248561dd53a25356e2'
    assert details['matched'] is True
    assert details['matchedConnectAddress'] is True
    assert details['roomId'] == 'Session:10afa1f20f534c248561dd53a25356e2'


def test_lookup_local_log_session_id_rejects_other_server(tmp_path, monkeypatch):
    log_path = tmp_path / 'SquadGame.log'
    log_path.write_text(
        "\n".join([
            "[2026.06.17-16.30.22:234][936]LogOnlineSession: Verbose: OSS:           RedpointEOSRoomId=Session:10afa1f20f534c248561dd53a25356e2 : OnlineServiceAndPing",
            "[2026.06.17-16.30.22:234][936]LogOnline: Join session: traveling to 164.152.123.232:27050",
        ]),
        encoding='utf-8',
    )
    monkeypatch.setenv('SQUAD_CLIENT_LOG_PATH', str(log_path))

    target_server_id, details = lookup_local_log_session_id('10.0.0.1:7787')

    assert target_server_id == ''
    assert details['matched'] is False
    assert details['matchedConnectAddress'] is False
    assert 'Latest Squad join was 164.152.123.232:27050' in details['error']
