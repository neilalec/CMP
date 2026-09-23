from dataclasses import replace

import pytest

from services.wardogs_assignment import (
    CANONICAL_FACTIONS,
    WardogsAssignmentConfig,
    WardogsAssignmentError,
    assign_wardogs_factions,
    validate_wardogs_assignment_config,
    validate_wardogs_assignment_result,
)
from services.wardogs_matchmaking import build_wardogs_matchmaking_input


MODES = {'hybrid-test': {'id': 'hybrid-test', 'game_type': 'wardogs'}}


def _input(solos=(), premades=(), match_id='match-a'):
    accepted = []
    groups = {}
    user_to_group = {}
    for index, members in enumerate(premades):
        code = f'party-{index}'
        groups[code] = {'code': code, 'leader': members[0], 'members': list(members)}
        for member in members:
            user_to_group[member] = code
            accepted.append(member)
    accepted.extend(solos)
    return build_wardogs_matchmaking_input(
        accepted,
        match_id=match_id,
        queue_mode='hybrid-test',
        queue_modes=MODES,
        groups=groups,
        user_to_group=user_to_group,
        created_at=1,
    )


def _counts(result, field='active_player_count'):
    return tuple(getattr(faction, field) for faction in result.factions)


def _config(active=2, reserve=1, **kwargs):
    return WardogsAssignmentConfig(active, reserve, **kwargs)


def test_three_solos_fill_three_factions_deterministically():
    value = _input(solos=('alice', 'bob', 'carol'))
    config = _config()
    result = assign_wardogs_factions(value, config)
    assert result.status == 'complete'
    assert tuple(faction.faction_id for faction in result.factions) == CANONICAL_FACTIONS
    assert _counts(result) == (1, 1, 1)
    assert validate_wardogs_assignment_result(value, config, result)


def test_equal_sized_inputs_balance_and_repeated_calls_match():
    value = _input(solos=tuple(f'p{i}' for i in range(9)))
    config = _config(active=3, reserve=0)
    first = assign_wardogs_factions(value, config)
    second = assign_wardogs_factions(value, config)
    assert first == second
    assert _counts(first) == (3, 3, 3)


def test_more_solos_than_active_slots_fill_reserves_without_loss():
    value = _input(solos=tuple(f'p{i}' for i in range(7)))
    result = assign_wardogs_factions(value, _config(active=2, reserve=1))
    assert result.status == 'complete'
    assert _counts(result) == (2, 2, 2)
    assert _counts(result, 'reserve_player_count') == (1, 0, 0)
    assert len(result.assigned_entries) == 7


def test_reserve_counts_are_balanced_where_capacity_allows():
    value = _input(solos=tuple(f'p{i}' for i in range(8)))
    result = assign_wardogs_factions(value, _config(active=1, reserve=2))
    assert _counts(result) == (1, 1, 1)
    assert sorted(_counts(result, 'reserve_player_count')) == [1, 2, 2]


def test_premades_remain_whole_and_are_placed_before_solos():
    value = _input(solos=('solo-a', 'solo-b'), premades=(('a', 'b', 'c'), ('d', 'e')))
    result = assign_wardogs_factions(value, _config(active=4, reserve=0))
    assert result.status == 'complete'
    premade_factions = [faction for faction in result.factions
                        if any(entry.kind == 'premade' for entry in faction.active_entries)]
    assert len(premade_factions) == 2
    for faction in premade_factions:
        assert sum(entry.member_count for entry in faction.active_entries if entry.kind == 'premade') in (2, 3)
    assert len([entry for entry in result.assigned_entries if entry.kind == 'premade']) == 2
    assert sum(_counts(result)) == 7


def test_larger_premades_are_considered_before_smaller_premades():
    value = _input(premades=(('a', 'b'), ('c', 'd', 'e'), ('f', 'g', 'h', 'i')))
    result = assign_wardogs_factions(value, _config(active=4, reserve=4))
    # The largest premade occupies one active faction; smaller premades fill the others.
    assert sorted(_counts(result)) == [2, 3, 4]
    assert all(len([entry for entry in faction.active_entries if entry.kind == 'premade']) == 1
               for faction in result.factions)


def test_premade_that_does_not_fit_active_is_wholly_reserved():
    value = _input(premades=(('a', 'b', 'c'),))
    result = assign_wardogs_factions(value, _config(active=2, reserve=3))
    assert result.status == 'complete'
    assert sum(_counts(result)) == 0
    assert _counts(result, 'reserve_player_count') == (3, 0, 0)
    assert result.factions[0].reserve_entries == value.entries


def test_unplaceable_premade_is_visible_with_reason_and_players_preserved():
    value = _input(premades=(('a', 'b', 'c', 'd'),))
    result = assign_wardogs_factions(value, _config(active=2, reserve=3))
    assert result.status == 'partial'
    assert result.unassigned_entries == value.entries
    assert result.unassigned[0].reason == 'entry_exceeds_all_faction_capacities'
    assert validate_wardogs_assignment_result(value, _config(active=2, reserve=3), result)


def test_full_active_and_reserve_capacity_returns_overflow_not_exception():
    value = _input(solos=tuple(f'p{i}' for i in range(10)))
    result = assign_wardogs_factions(value, _config(active=2, reserve=1))
    assert result.status == 'partial'
    assert len(result.unassigned_entries) == 1
    assert result.unassigned[0].reason == 'active_and_reserve_capacity_exhausted'
    assert len(result.assigned_entries) + len(result.unassigned_entries) == len(value.entries)


@pytest.mark.parametrize('config', [
    _config(active=0),
    _config(active=True),
    _config(active=2, reserve=-1),
    _config(active=2, reserve=True),
    _config(active=2, factions=('valkyra', 'lonestar')),
    _config(active=2, factions=('lonestar', 'valkyra', 'manticore')),
    _config(active=2, allow_premade_split=True),
])
def test_invalid_config_is_a_controlled_invalid_result(config):
    result = assign_wardogs_factions(_input(solos=('a',)), config)
    assert result.status == 'invalid'
    assert result.errors


def test_config_validator_explains_invalid_capacity():
    with pytest.raises(WardogsAssignmentError, match='positive integer'):
        validate_wardogs_assignment_config(_config(active=0))


def test_duplicate_entry_ids_and_duplicate_players_are_invalid_inputs():
    value = _input(solos=('alice', 'bob'))
    duplicated_id = replace(value, entries=(value.entries[0], replace(value.entries[1], entry_id=value.entries[0].entry_id)))
    assert assign_wardogs_factions(duplicated_id, _config()).status == 'invalid'

    duplicate_member = replace(value.entries[1], members=value.entries[0].members)
    duplicate_players = replace(value, entries=(value.entries[0], duplicate_member))
    assert assign_wardogs_factions(duplicate_players, _config()).status == 'invalid'


def test_malformed_input_is_invalid_and_all_recognizable_entries_are_retained():
    value = _input(solos=('alice',))
    malformed = replace(value, game_type='squad')
    result = assign_wardogs_factions(malformed, _config())
    assert result.status == 'invalid'
    assert result.unassigned_entries == value.entries


def test_input_snapshots_are_unchanged_and_player_coverage_is_exact():
    value = _input(solos=('s1', 's2'), premades=(('p1', 'p2'),))
    before = value
    result = assign_wardogs_factions(value, _config(active=1, reserve=1))
    assert value == before
    actual = [member.username for entry in result.assigned_entries + result.unassigned_entries
              for member in entry.members]
    assert sorted(actual) == sorted(value.accepted_players)
    assert len(actual) == len(set(actual))


def test_result_validator_rejects_capacity_violation_or_duplicate_output_entry():
    value = _input(solos=('a', 'b', 'c'))
    config = _config(active=2, reserve=0)
    result = assign_wardogs_factions(value, config)
    over_capacity = replace(result.factions[0], active_entries=result.factions[0].active_entries * 3)
    with pytest.raises(WardogsAssignmentError, match='active capacity'):
        validate_wardogs_assignment_result(value, config, replace(result, factions=(over_capacity,) + result.factions[1:]))

    duplicated = replace(result.factions[1], active_entries=result.factions[1].active_entries + result.factions[0].active_entries)
    with pytest.raises(WardogsAssignmentError, match='exactly once'):
        validate_wardogs_assignment_result(value, config, replace(result, factions=(result.factions[0], duplicated, result.factions[2])))


def test_active_and_reserve_placement_never_splits_a_premade():
    value = _input(premades=(('a', 'b', 'c'), ('d', 'e')))
    result = assign_wardogs_factions(value, _config(active=2, reserve=3))
    locations = {}
    for faction in result.factions:
        for entry in faction.active_entries:
            locations[entry.entry_id] = ('active', faction.faction_id, entry.members)
        for entry in faction.reserve_entries:
            locations[entry.entry_id] = ('reserve', faction.faction_id, entry.members)
    assert len(locations) == 2
    assert all(location[0] in {'active', 'reserve'} for location in locations.values())
    assert all(len(location[2]) in {2, 3} for location in locations.values())
