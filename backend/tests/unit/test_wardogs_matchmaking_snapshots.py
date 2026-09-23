from dataclasses import FrozenInstanceError, replace

import pytest

from app_state import QUEUE_MODES
from services.wardogs_matchmaking import (
    WardogsMatchmakingInputError,
    build_wardogs_matchmaking_input,
    validate_wardogs_matchmaking_input,
)

WARDOGS_TEST_MODES = {
    'wardogs-test': {'id': 'wardogs-test', 'game_type': 'wardogs'},
}


def _party(code, leader, members):
    return {'code': code, 'leader': leader, 'members': list(members)}


def _build(players, groups=None, user_to_group=None, **kwargs):
    match_id = kwargs.pop('match_id', 'match-123')
    queue_mode = kwargs.pop('queue_mode', 'wardogs-test')
    created_at = kwargs.pop('created_at', 100.0)
    queue_modes = kwargs.pop('queue_modes', WARDOGS_TEST_MODES)
    return build_wardogs_matchmaking_input(
        players,
        match_id=match_id,
        queue_mode=queue_mode,
        queue_modes=queue_modes,
        groups=groups or {},
        user_to_group=user_to_group or {},
        created_at=created_at,
        **kwargs,
    )


def _players(input_value):
    return [member.username for entry in input_value.entries for member in entry.members]


def test_single_and_multiple_unrelated_solos_make_individual_entries():
    one = _build(['alice'])
    assert [(entry.kind, [member.username for member in entry.members]) for entry in one.entries] == [
        ('solo', ['alice'])
    ]

    several = _build(['alice', 'bob', 'carol'])
    assert [(entry.kind, entry.members[0].username) for entry in several.entries] == [
        ('solo', 'alice'), ('solo', 'bob'), ('solo', 'carol')
    ]


def test_complete_party_and_several_parties_keep_party_order_and_leader():
    groups = {
        'ABC123': _party('ABC123', 'bob', ['alice', 'bob']),
        'XYZ789': _party('XYZ789', 'dave', ['carol', 'dave']),
    }
    user_map = {'alice': 'ABC123', 'bob': 'ABC123', 'carol': 'XYZ789', 'dave': 'XYZ789'}
    result = _build(['alice', 'carol', 'bob', 'dave'], groups, user_map)
    assert [(entry.source_party_code, entry.leader_username,
             [member.username for member in entry.members]) for entry in result.entries] == [
        ('ABC123', 'bob', ['alice', 'bob']),
        ('XYZ789', 'dave', ['carol', 'dave']),
    ]
    assert all(entry.kind == 'premade' for entry in result.entries)
    assert validate_wardogs_matchmaking_input(result) is True


def test_mixed_party_and_solo_entries_only_include_accepted_members():
    groups = {'ABC123': _party('ABC123', 'alice', ['alice', 'bob', 'carol'])}
    user_map = {'alice': 'ABC123', 'bob': 'ABC123', 'carol': 'ABC123'}
    result = _build(['alice', 'outside', 'bob'], groups, user_map)
    assert [(entry.kind, entry.leader_username, [m.username for m in entry.members])
            for entry in result.entries] == [
        ('premade', 'alice', ['alice', 'bob']),
        ('solo', None, ['outside']),
    ]
    assert set(_players(result)) == {'alice', 'outside', 'bob'}
    assert 'carol' not in _players(result)


def test_partial_party_without_accepted_leader_has_no_invented_leader():
    groups = {'ABC123': _party('ABC123', 'alice', ['alice', 'bob', 'carol'])}
    user_map = {'alice': 'ABC123', 'bob': 'ABC123', 'carol': 'ABC123'}
    result = _build(['bob', 'carol'], groups, user_map)
    entry = result.entries[0]
    assert entry.kind == 'premade'
    assert entry.leader_username is None
    assert [member.username for member in entry.members] == ['bob', 'carol']


def test_one_accepted_party_member_becomes_a_solo():
    groups = {'ABC123': _party('ABC123', 'alice', ['alice', 'bob'])}
    result = _build(['bob'], groups, {'alice': 'ABC123', 'bob': 'ABC123'})
    assert len(result.entries) == 1
    assert result.entries[0].kind == 'solo'
    assert result.entries[0].source_party_code is None
    assert result.entries[0].leader_username is None


def test_profile_snapshot_contains_only_identity_fields_and_is_defensively_copied():
    groups = {'ABC123': _party('ABC123', 'alice', ['alice', 'bob'])}
    group_members = groups['ABC123']['members']
    user_map = {'alice': 'ABC123', 'bob': 'ABC123'}
    profile = {'display_name': 'Alice A', 'steam_id': '76561198000000001', 'password': 'secret'}
    result = _build(['alice', 'bob'], groups, user_map, profiles={'alice': profile})
    entry = result.entries[0]
    assert entry.members[0].display_name == 'Alice A'
    assert entry.members[0].steam_id == '76561198000000001'
    assert not hasattr(entry.members[0], 'password')

    group_members.clear()
    groups['ABC123']['leader'] = 'bob'
    user_map['alice'] = 'MUTATED'
    profile['display_name'] = 'Changed'
    assert [member.username for member in entry.members] == ['alice', 'bob']
    assert entry.leader_username == 'alice'
    assert entry.members[0].display_name == 'Alice A'
    with pytest.raises(FrozenInstanceError):
        entry.leader_username = 'bob'


def test_entry_ids_are_stable_for_the_same_match_snapshot():
    groups = {'ABC123': _party('ABC123', 'alice', ['alice', 'bob'])}
    user_map = {'alice': 'ABC123', 'bob': 'ABC123'}
    first = _build(['alice', 'bob'], groups, user_map)
    second = _build(['alice', 'bob'], groups, user_map)
    assert [entry.entry_id for entry in first.entries] == [entry.entry_id for entry in second.entries]
    assert first.created_at == 100.0
    assert first.game_type == 'wardogs'
    assert first.queue_mode == 'wardogs-test'


def test_snapshot_contract_does_not_register_or_enable_a_wardogs_queue():
    assert QUEUE_MODES
    assert all(config.get('game_type') == 'squad' for config in QUEUE_MODES.values())


@pytest.mark.parametrize('groups,user_map', [
    ({}, {'alice': 'MISSING'}),
    ({'ABC123': _party('ABC123', 'alice', ['alice', 'bob'])}, {'alice': 'ABC123'}),
    ({'ABC123': _party('ABC123', 'alice', ['alice', 'bob'])},
     {'alice': 'ABC123', 'bob': 'OTHER'}),
])
def test_stale_or_conflicting_group_state_falls_back_to_solos(groups, user_map):
    result = _build(['alice', 'bob'], groups, user_map)
    assert [entry.kind for entry in result.entries] == ['solo', 'solo']
    assert sorted(_players(result)) == ['alice', 'bob']


def test_duplicate_group_membership_invalidates_conflicting_parties_without_loss():
    groups = {
        'ABC123': _party('ABC123', 'alice', ['alice', 'bob']),
        'XYZ789': _party('XYZ789', 'carol', ['bob', 'carol']),
    }
    user_map = {'alice': 'ABC123', 'bob': 'ABC123', 'carol': 'XYZ789'}
    result = _build(['alice', 'bob', 'carol'], groups, user_map)
    assert [entry.kind for entry in result.entries] == ['solo', 'solo', 'solo']
    assert sorted(_players(result)) == ['alice', 'bob', 'carol']


def test_malformed_group_falls_back_to_solos():
    groups = {'ABC123': _party('ABC123', 'not-a-member', ['alice', 'bob'])}
    result = _build(['alice', 'bob'], groups, {'alice': 'ABC123', 'bob': 'ABC123'})
    assert [entry.kind for entry in result.entries] == ['solo', 'solo']


def test_unaccepted_member_with_stale_reverse_mapping_invalidates_party_safely():
    groups = {'ABC123': _party('ABC123', 'alice', ['alice', 'bob', 'carol'])}
    user_map = {'alice': 'ABC123', 'bob': 'ABC123', 'carol': 'OTHER'}
    result = _build(['alice', 'bob'], groups, user_map)
    assert [entry.kind for entry in result.entries] == ['solo', 'solo']
    assert sorted(_players(result)) == ['alice', 'bob']


def test_duplicate_accepted_players_are_rejected():
    with pytest.raises(WardogsMatchmakingInputError, match='duplicates'):
        _build(['alice', 'alice'])


def test_validation_rejects_duplicate_empty_malformed_and_wrong_context_entries():
    result = _build(['alice', 'bob'])
    solo = result.entries[0]
    with pytest.raises(WardogsMatchmakingInputError, match='more than one'):
        validate_wardogs_matchmaking_input(replace(result, entries=(solo, replace(solo, entry_id='entry-2'))))
    with pytest.raises(WardogsMatchmakingInputError, match='empty'):
        validate_wardogs_matchmaking_input(replace(result, entries=(replace(solo, members=()),)))
    with pytest.raises(WardogsMatchmakingInputError, match='Solo entries'):
        validate_wardogs_matchmaking_input(replace(result, entries=(replace(solo, members=solo.members * 2),)))
    with pytest.raises(WardogsMatchmakingInputError, match='All entries'):
        validate_wardogs_matchmaking_input(replace(result, entries=(replace(solo, queue_mode='other'),)))


def test_invalid_input_context_and_empty_entry_are_rejected():
    with pytest.raises(WardogsMatchmakingInputError, match='Match ID'):
        _build(['alice'], match_id='')
    with pytest.raises(WardogsMatchmakingInputError, match='Queue mode'):
        _build(['alice'], queue_mode=' ')
    with pytest.raises(WardogsMatchmakingInputError, match='not configured'):
        _build(['alice'], queue_mode='skirmish', queue_modes=QUEUE_MODES)
    with pytest.raises(WardogsMatchmakingInputError, match='At least one accepted'):
        _build([])
    result = _build(['alice'])
    with pytest.raises(WardogsMatchmakingInputError, match='game_type="wardogs"'):
        validate_wardogs_matchmaking_input(replace(result, game_type='squad'))
