from app_state import (
    ALL_BALT_26_MAPS,
    ALL_OCBT_MAPS,
    ALL_OCBT_VOTE_MAPS,
    ALL_OUT_OF_THE_BOX_40_MAPS,
    ALL_OSI_40_MAPS,
    ALL_RIVALS_36_MAPS,
    ALL_SEC_26_MAPS,
    ALL_SEC_36_MAPS,
    ALL_SEC_46_MAPS,
    ALL_SKIRMISH_MAPS,
    OCBT_MAP_VARIANTS,
    QUEUE_MODES,
)
from matchmaking import build_lobby_map_pool, select_map_from_votes


def test_skirmish_layer_pool_matches_comp_skirmish_listing():
    assert ALL_SKIRMISH_MAPS == [
        'CSL_AlBasrahSkirmishv1',
        'CSL_AlBasrahSkirmishv2',
        'CSL_AlBasrahSkirmishv3',
        'CSL_AnvilSkirmishv1',
        'CSL_BlackCoastSkirmishv1',
        'CSL_ChoraSkirmishv1',
        'CSL_FallujahSkirmishv1',
        'CSL_FallujahSkirmishv2',
        'CSL_FoolsRoadSkirmishv1',
        'CSL_FoolsRoadSkirmishv2',
        'CSL_GooseBaySkirmishv1',
        'CSL_GorodokSkirmishv1',
        'CSL_HarjuSkirmishv1',
        'CSL_HarjuSkirmishv2',
        'CSL_KamdeshSkirmishv1',
        'CSL_KohatSkirmishv1',
        'CSL_KokanSkirmishv1',
        'CSL_LashkarSkirmishv1',
        'CSL_LogarSkirmishv1',
        'CSL_ManicouaganSkirmishv1',
        'CSL_ManicouaganSkirmishv2',
        'CSL_ManicouaganSkirmishv3',
        'CSL_MestiaSkirmishv1',
        'CSL_MutahaSkirmishv1',
        'CSL_NarvaSkirmishv1',
        'CSL_SkorpoSkirmishv1',
        'CSL_SumariSkirmishv1',
        'CSL_TallilSkirmishv1',
        'CSL_TallilSkirmishv2',
        'CSL_TallilSkirmishv3',
        'CSL_YehorivkaSkirmishv1',
        'CSL_YehorivkaSkirmishv2',
    ]


def test_squad_esports_cup_layer_pools_match_command_ready_listing():
    assert ALL_SEC_26_MAPS == [
        'SEC_26_Mutaha_TC',
        'SEC_26_AlBasrah_AAS_v1',
        'SEC_26_Narva_AAS_v1',
        'SEC_26_Sumari_AAS_v1',
        'SEC_26_Logar_AAS_v1',
        'SEC_26_Harju_AAS_v1',
        'SEC_26_Yehorivka_AAS_v1',
        'SEC_26_Chora_AAS_v1',
        'SEC_26_Fallujah_AAS_v1',
        'SEC_26_BlackCoast_RAAS_v1',
        'SEC_26_Gorodok_RAAS_v1',
    ]
    assert ALL_SEC_36_MAPS == [
        'SEC_36_Narva_TC',
        'SEC_36_Mutaha_TC_v1',
        'SEC_36_FoolsRoad_AAS_v1',
        'SEC_36_Chora_AAS_v1',
        'SEC_36_Manicouagan_AAS_v1',
        'SEC_36_Logar_AAS_v1',
        'SEC_36_Gorodok_AAS_v2',
        'SEC_36_Mestia_AAS_v1',
        'SEC_36_Kohat_AAS_v1',
        'SEC_36_Yehorivka_RAAS_v1',
    ]
    assert ALL_SEC_46_MAPS == [
        'SEC_46_Narva_TC',
        'SEC_46_Mutaha_TC_v1',
        'SEC_46_FoolsRoad_AAS_v1',
        'SEC_46_Chora_AAS_v1',
        'SEC_46_Manicouagan_AAS_v1',
        'SEC_46_Logar_AAS_v1',
        'SEC_46_Gorodok_AAS_v2',
        'SEC_46_Mestia_AAS_v1',
        'SEC_46_Kohat_AAS_v1',
        'SEC_46_Yehorivka_RAAS_v1',
    ]


def test_rivals_and_osi_layer_pools_match_workshop_listing():
    assert ALL_RIVALS_36_MAPS == [
        'Rivals_W1_FoolsRoad',
        'Rivals_W2_BlackCoast',
        'Rivals_W3_Kokan',
        'Rivals_W4_Narva',
        'Rivals_W5_AlBasrah',
    ]
    assert ALL_OSI_40_MAPS == [
        'OSI_W1_Chora',
        'OSI_W2_Mutaha',
        'OSI_W3_Harju',
        'OSI_W4_Yehorivka',
        'OSI_W5_BlackCoast',
        'OSI_W6_AlBasrah',
    ]


def test_ocbt_and_balt_layer_pools_match_workshop_listing():
    assert ALL_OCBT_MAPS == [
        'OCBT_UrbanQuarter_AAS_v1',
        'OCBT_UrbanQuarter_AAS_v2',
        'OCBT_UrbanQuarter_AAS_v3',
        'OCBT_Oasis_AAS_v1',
        'OCBT_Oasis_AAS_v2',
        'OCBT_Oasis_AAS_v3',
        'OCBT_Kalinovo_AAS_v1',
        'OCBT_Kalinovo_AAS_v2',
        'OCBT_Kalinovo_AAS_v3',
        'OCBT_AzureIsland_AAS_v1',
        'OCBT_AzureIsland_AAS_v2',
        'OCBT_AzureIsland_AAS_v3',
        'OCBT_AzureIsland_AAS_v4',
        'OCBT_Shchyhliivka_AAS_v1',
        'OCBT_Shchyhliivka_AAS_v2',
        'OCBT_Shchyhliivka_AAS_v3',
        'OCBT_Shchyhliivka_AAS_v4',
    ]
    assert ALL_BALT_26_MAPS == [
        'BALT_26_AlBasrah_AAS_v1',
        'BALT_26_SANXIAN_PAAS_v1',
    ]


def test_out_of_the_box_layer_pool_matches_command_ready_listing():
    assert ALL_OUT_OF_THE_BOX_40_MAPS == [
        'OutoftheBox_Tallil',
        'OutoftheBox_Skorpo',
        'OutoftheBox_Sanxian',
        'OutoftheBox_PacificProvingGrounds',
        'OutoftheBox_Mestia',
        'OutoftheBox_Lashkar',
        'OutoftheBox_Kohat',
        'OutoftheBox_AlBasrah',
    ]


def test_ocbt_map_vote_uses_base_maps_then_resolves_variant(monkeypatch):
    assert ALL_OCBT_VOTE_MAPS == [
        'OCBT_UrbanQuarter',
        'OCBT_Oasis',
        'OCBT_Kalinovo',
        'OCBT_AzureIsland',
        'OCBT_Shchyhliivka',
    ]
    assert build_lobby_map_pool(QUEUE_MODES['ocbt15']) == ALL_OCBT_VOTE_MAPS

    monkeypatch.setattr('matchmaking.random.choice', lambda options: list(options)[0])
    selected_map, vote_counts = select_map_from_votes({
        'queue_mode': 'ocbt15',
        'map_votes': {
            'alice': 'OCBT_AzureIsland',
            'bob': 'OCBT_AzureIsland',
            'cara': 'OCBT_Oasis',
        },
    })

    assert selected_map in OCBT_MAP_VARIANTS['OCBT_AzureIsland']
    assert selected_map == 'OCBT_AzureIsland_AAS_v1'
    assert vote_counts == {
        'OCBT_AzureIsland': 2,
        'OCBT_Oasis': 1,
    }


def test_queue_modes_expose_each_tournament_format():
    assert QUEUE_MODES['skirmish']['label'] == '20v20 Skirmish Layers'
    assert QUEUE_MODES['skirmish']['team_size'] == 20
    assert QUEUE_MODES['skirmish']['max_players'] == 40
    assert QUEUE_MODES['skirmish']['map_pool'] is ALL_SKIRMISH_MAPS

    assert QUEUE_MODES['sec26']['team_size'] == 26
    assert QUEUE_MODES['sec26']['max_players'] == 52
    assert QUEUE_MODES['sec26']['map_pool'] is ALL_SEC_26_MAPS

    assert QUEUE_MODES['sec36']['team_size'] == 36
    assert QUEUE_MODES['sec36']['max_players'] == 72
    assert QUEUE_MODES['sec36']['map_pool'] is ALL_SEC_36_MAPS

    assert QUEUE_MODES['sec46']['team_size'] == 46
    assert QUEUE_MODES['sec46']['max_players'] == 92
    assert QUEUE_MODES['sec46']['map_pool'] is ALL_SEC_46_MAPS

    assert QUEUE_MODES['rivals36']['label'] == '36v36 Squad Rivals'
    assert QUEUE_MODES['rivals36']['team_size'] == 36
    assert QUEUE_MODES['rivals36']['max_players'] == 72
    assert QUEUE_MODES['rivals36']['map_pool'] is ALL_RIVALS_36_MAPS

    assert QUEUE_MODES['osi40']['label'] == '40v40 Offworld Squad Invitational'
    assert QUEUE_MODES['osi40']['team_size'] == 40
    assert QUEUE_MODES['osi40']['max_players'] == 80
    assert QUEUE_MODES['osi40']['map_pool'] is ALL_OSI_40_MAPS

    assert QUEUE_MODES['ocbt15']['label'] == '10v10 Open Clan Battle'
    assert QUEUE_MODES['ocbt15']['team_size'] == 10
    assert QUEUE_MODES['ocbt15']['max_players'] == 20
    assert QUEUE_MODES['ocbt15']['map_pool'] is ALL_OCBT_MAPS
    assert QUEUE_MODES['ocbt15']['vote_pool'] is ALL_OCBT_VOTE_MAPS
    assert QUEUE_MODES['ocbt15']['map_variants'] is OCBT_MAP_VARIANTS

    assert QUEUE_MODES['balt26']['label'] == '26v26 Balt Layers'
    assert QUEUE_MODES['balt26']['team_size'] == 26
    assert QUEUE_MODES['balt26']['max_players'] == 52
    assert QUEUE_MODES['balt26']['map_pool'] is ALL_BALT_26_MAPS

    assert QUEUE_MODES['outofthebox40']['label'] == '30v30 Out of The Box Layers'
    assert QUEUE_MODES['outofthebox40']['team_size'] == 30
    assert QUEUE_MODES['outofthebox40']['max_players'] == 60
    assert QUEUE_MODES['outofthebox40']['map_pool'] is ALL_OUT_OF_THE_BOX_40_MAPS

    tournament_layer_count = (
        len(ALL_SKIRMISH_MAPS)
        + len(ALL_SEC_26_MAPS)
        + len(ALL_SEC_36_MAPS)
        + len(ALL_SEC_46_MAPS)
        + len(ALL_RIVALS_36_MAPS)
        + len(ALL_OSI_40_MAPS)
        + len(ALL_OCBT_MAPS)
        + len(ALL_BALT_26_MAPS)
        + len(ALL_OUT_OF_THE_BOX_40_MAPS)
    )
    assert tournament_layer_count == 101
