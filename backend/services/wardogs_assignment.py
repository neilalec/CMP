"""Deterministic, isolated WARDOGS Hybrid faction assignment."""

from collections import Counter
from dataclasses import dataclass

from services.wardogs_lobby import FACTIONS
from services.wardogs_matchmaking import (
    GAME_TYPE,
    WardogsQueueEntry,
    WardogsMatchmakingInputError,
    validate_wardogs_matchmaking_input,
)


CANONICAL_FACTIONS = tuple(faction_id for faction_id, _label, _color in FACTIONS)
ASSIGNMENT_STATUSES = frozenset({'complete', 'partial', 'invalid'})


class WardogsAssignmentError(ValueError):
    """Raised when an assignment configuration or result violates its contract."""


@dataclass(frozen=True)
class WardogsAssignmentConfig:
    """Capacities supplied by the caller; no production size is assumed."""

    active_per_faction: int
    reserve_per_faction: int
    factions: tuple = CANONICAL_FACTIONS
    allow_premade_split: bool = False


@dataclass(frozen=True)
class WardogsFactionAssignment:
    faction_id: str
    active_entries: tuple = ()
    reserve_entries: tuple = ()

    @property
    def active_player_count(self):
        return sum(entry.member_count for entry in self.active_entries)

    @property
    def reserve_player_count(self):
        return sum(entry.member_count for entry in self.reserve_entries)


@dataclass(frozen=True)
class WardogsUnassignedEntry:
    entry: WardogsQueueEntry
    reason: str


@dataclass(frozen=True)
class WardogsAssignmentResult:
    match_id: str
    game_type: str
    queue_mode: str
    status: str
    factions: tuple
    unassigned: tuple = ()
    errors: tuple = ()

    @property
    def assigned_entries(self):
        return tuple(entry for faction in self.factions
                     for entry in faction.active_entries + faction.reserve_entries)

    @property
    def unassigned_entries(self):
        return tuple(item.entry for item in self.unassigned)


def validate_wardogs_assignment_config(config):
    if not isinstance(config, WardogsAssignmentConfig):
        raise WardogsAssignmentError('Expected a WARDOGS assignment configuration.')
    if config.factions != CANONICAL_FACTIONS:
        raise WardogsAssignmentError('Assignment must use the three canonical WARDOGS factions in canonical order.')
    if (isinstance(config.active_per_faction, bool)
            or not isinstance(config.active_per_faction, int)
            or config.active_per_faction <= 0):
        raise WardogsAssignmentError('Active capacity per faction must be a positive integer.')
    if (isinstance(config.reserve_per_faction, bool)
            or not isinstance(config.reserve_per_faction, int)
            or config.reserve_per_faction < 0):
        raise WardogsAssignmentError('Reserve capacity per faction must be a non-negative integer.')
    if config.allow_premade_split is not False:
        raise WardogsAssignmentError('Premade splitting must be disabled for WARDOGS assignment v1.')
    return True


def _empty_factions():
    return tuple(WardogsFactionAssignment(faction_id) for faction_id in CANONICAL_FACTIONS)


def _invalid_result(matchmaking_input, error):
    match_id = getattr(matchmaking_input, 'match_id', '')
    queue_mode = getattr(matchmaking_input, 'queue_mode', '')
    entries = getattr(matchmaking_input, 'entries', ())
    if not isinstance(entries, (tuple, list)):
        entries = ()
    unassigned = tuple(WardogsUnassignedEntry(entry, 'invalid_input')
                       for entry in entries if isinstance(entry, WardogsQueueEntry))
    return WardogsAssignmentResult(
        match_id=match_id if isinstance(match_id, str) else '',
        game_type=GAME_TYPE,
        queue_mode=queue_mode if isinstance(queue_mode, str) else '',
        status='invalid',
        factions=_empty_factions(),
        unassigned=unassigned,
        errors=(str(error),),
    )


def _entry_order(entry):
    # Place intact premades first, largest first; stable IDs make input order irrelevant.
    return (0 if entry.kind == 'premade' else 1, -entry.member_count, entry.entry_id)


def _choose_faction(factions, entry, capacity, *, reserve):
    counts = [faction.reserve_player_count if reserve else faction.active_player_count
              for faction in factions]
    candidates = [index for index, count in enumerate(counts)
                  if count + entry.member_count <= capacity]
    if not candidates:
        return None
    return min(candidates, key=lambda index: (
        counts[index] + entry.member_count,
        counts[index],
        len(factions[index].reserve_entries if reserve else factions[index].active_entries),
        index,
    ))


def assign_wardogs_factions(matchmaking_input, config):
    """Assign whole entries to active rosters, then reserves, else explicit overflow.

    Entries are considered premade-first, larger-first, then by stable entry ID.
    A fitting faction is chosen by lowest resulting player count, then current
    count, entry count, and canonical faction order. Reserves use the same rule.
    """
    try:
        validate_wardogs_assignment_config(config)
        validate_wardogs_matchmaking_input(matchmaking_input)
    except (WardogsAssignmentError, WardogsMatchmakingInputError, TypeError, AttributeError) as exc:
        return _invalid_result(matchmaking_input, exc)

    factions = list(_empty_factions())
    unassigned = []
    for entry in sorted(matchmaking_input.entries, key=_entry_order):
        faction_index = _choose_faction(factions, entry, config.active_per_faction, reserve=False)
        if faction_index is not None:
            current = factions[faction_index]
            factions[faction_index] = WardogsFactionAssignment(
                current.faction_id, current.active_entries + (entry,), current.reserve_entries)
            continue

        faction_index = _choose_faction(factions, entry, config.reserve_per_faction, reserve=True)
        if faction_index is not None:
            current = factions[faction_index]
            factions[faction_index] = WardogsFactionAssignment(
                current.faction_id, current.active_entries, current.reserve_entries + (entry,))
            continue

        max_capacity = max(config.active_per_faction, config.reserve_per_faction)
        reason = ('entry_exceeds_all_faction_capacities' if entry.member_count > max_capacity
                  else 'active_and_reserve_capacity_exhausted')
        unassigned.append(WardogsUnassignedEntry(entry, reason))

    result = WardogsAssignmentResult(
        match_id=matchmaking_input.match_id,
        game_type=GAME_TYPE,
        queue_mode=matchmaking_input.queue_mode,
        status='partial' if unassigned else 'complete',
        factions=tuple(factions),
        unassigned=tuple(unassigned),
    )
    validate_wardogs_assignment_result(matchmaking_input, config, result)
    return result


def validate_wardogs_assignment_result(matchmaking_input, config, result):
    """Check capacities, entry/player coverage, and output shape for a valid input."""
    validate_wardogs_assignment_config(config)
    validate_wardogs_matchmaking_input(matchmaking_input)
    if not isinstance(result, WardogsAssignmentResult) or result.status not in {'complete', 'partial'}:
        raise WardogsAssignmentError('Expected a complete or partial WARDOGS assignment result.')
    if (result.match_id != matchmaking_input.match_id or result.game_type != GAME_TYPE
            or result.queue_mode != matchmaking_input.queue_mode):
        raise WardogsAssignmentError('Assignment result context does not match its input.')
    if not isinstance(result.factions, tuple) or tuple(item.faction_id for item in result.factions) != CANONICAL_FACTIONS:
        raise WardogsAssignmentError('Assignment result must include each canonical faction exactly once.')
    if not isinstance(result.unassigned, tuple):
        raise WardogsAssignmentError('Unassigned entries must be immutable.')

    seen_entry_ids = []
    assigned_players = []
    for faction in result.factions:
        if not isinstance(faction.active_entries, tuple) or not isinstance(faction.reserve_entries, tuple):
            raise WardogsAssignmentError('Faction entry collections must be immutable tuples.')
        if faction.active_player_count > config.active_per_faction:
            raise WardogsAssignmentError(f'{faction.faction_id} exceeds active capacity.')
        if faction.reserve_player_count > config.reserve_per_faction:
            raise WardogsAssignmentError(f'{faction.faction_id} exceeds reserve capacity.')
        for entry in faction.active_entries + faction.reserve_entries:
            if not isinstance(entry, WardogsQueueEntry):
                raise WardogsAssignmentError('Assigned entries must preserve immutable queue-entry snapshots.')
            seen_entry_ids.append(entry.entry_id)
            assigned_players.extend(member.username for member in entry.members)
    for item in result.unassigned:
        if not isinstance(item, WardogsUnassignedEntry) or not isinstance(item.entry, WardogsQueueEntry):
            raise WardogsAssignmentError('Unassigned entries must preserve their queue-entry snapshot and reason.')
        if not item.reason:
            raise WardogsAssignmentError('Unassigned entries require an explicit overflow reason.')
        seen_entry_ids.append(item.entry.entry_id)
        assigned_players.extend(member.username for member in item.entry.members)

    expected_ids = [entry.entry_id for entry in matchmaking_input.entries]
    if Counter(seen_entry_ids) != Counter(expected_ids):
        raise WardogsAssignmentError('Every input entry must appear exactly once in assigned or unassigned output.')
    expected_players = list(matchmaking_input.accepted_players)
    if Counter(assigned_players) != Counter(expected_players):
        raise WardogsAssignmentError('Every accepted player must appear exactly once in assigned or unassigned output.')
    if (result.status == 'complete') != (not result.unassigned):
        raise WardogsAssignmentError('Assignment status must reflect whether entries remain unassigned.')
    return True
