"""Immutable WARDOGS matchmaking input built from CMP identity and parties."""

from dataclasses import dataclass
import hashlib
import math
import time
from typing import Mapping, Optional, Tuple

from services.queue import resolve_queue_game_type


GAME_TYPE = 'wardogs'
ENTRY_KINDS = frozenset({'solo', 'premade'})


class WardogsMatchmakingInputError(ValueError):
    """Raised when accepted players cannot form a valid matchmaking input."""


@dataclass(frozen=True)
class WardogsPlayerSnapshot:
    username: str
    display_name: Optional[str] = None
    steam_id: Optional[str] = None


@dataclass(frozen=True)
class WardogsQueueEntry:
    entry_id: str
    kind: str
    game_type: str
    queue_mode: str
    members: Tuple[WardogsPlayerSnapshot, ...]
    source_party_code: Optional[str] = None
    leader_username: Optional[str] = None

    @property
    def member_count(self):
        return len(self.members)


@dataclass(frozen=True)
class WardogsMatchmakingInput:
    match_id: str
    game_type: str
    queue_mode: str
    created_at: float
    accepted_players: Tuple[str, ...]
    entries: Tuple[WardogsQueueEntry, ...]


def _clean_identity(value):
    return value.strip() if isinstance(value, str) else ''


def _stable_entry_id(match_id, queue_mode, kind, source_party_code, members):
    member_ids = '\0'.join(member.username for member in members)
    identity = '\0'.join((GAME_TYPE, queue_mode, match_id, kind, source_party_code or '', member_ids))
    digest = hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]
    return f'wardogs_entry_{digest}'


def validate_wardogs_matchmaking_input(matchmaking_input):
    if not isinstance(matchmaking_input, WardogsMatchmakingInput):
        raise WardogsMatchmakingInputError('Expected a WARDOGS matchmaking input.')
    if (not isinstance(matchmaking_input.match_id, str) or not matchmaking_input.match_id.strip()
            or matchmaking_input.match_id != matchmaking_input.match_id.strip()):
        raise WardogsMatchmakingInputError('Match ID is required.')
    if matchmaking_input.game_type != GAME_TYPE:
        raise WardogsMatchmakingInputError('Matchmaking input must use game_type="wardogs".')
    if (not isinstance(matchmaking_input.queue_mode, str) or not matchmaking_input.queue_mode.strip()
            or matchmaking_input.queue_mode != matchmaking_input.queue_mode.strip()):
        raise WardogsMatchmakingInputError('Queue mode is required.')
    if not isinstance(matchmaking_input.created_at, (float, int)) or not math.isfinite(matchmaking_input.created_at):
        raise WardogsMatchmakingInputError('Snapshot timestamp must be finite.')
    if not isinstance(matchmaking_input.accepted_players, tuple) or not matchmaking_input.accepted_players:
        raise WardogsMatchmakingInputError('At least one accepted player is required.')
    if any(not isinstance(player, str) or not player.strip() or player != player.strip()
           for player in matchmaking_input.accepted_players):
        raise WardogsMatchmakingInputError('Accepted players must have valid CMP identities.')
    if len(set(matchmaking_input.accepted_players)) != len(matchmaking_input.accepted_players):
        raise WardogsMatchmakingInputError('Accepted player list contains duplicates.')
    if not isinstance(matchmaking_input.entries, tuple) or not matchmaking_input.entries:
        raise WardogsMatchmakingInputError('At least one queue entry is required.')

    entry_ids = set()
    player_ids = []
    for entry in matchmaking_input.entries:
        if not isinstance(entry, WardogsQueueEntry):
            raise WardogsMatchmakingInputError('Queue entries must use the immutable WARDOGS entry type.')
        if (entry.game_type != matchmaking_input.game_type
                or entry.queue_mode != matchmaking_input.queue_mode):
            raise WardogsMatchmakingInputError('All entries must use the input game and queue mode.')
        if not isinstance(entry.entry_id, str) or not entry.entry_id or entry.entry_id in entry_ids:
            raise WardogsMatchmakingInputError('Queue entry IDs must be present and unique.')
        entry_ids.add(entry.entry_id)
        if not isinstance(entry.kind, str) or entry.kind not in ENTRY_KINDS:
            raise WardogsMatchmakingInputError(f'Unsupported queue entry kind: {entry.kind!r}.')
        if not isinstance(entry.members, tuple) or not entry.members:
            raise WardogsMatchmakingInputError(f'Queue entry {entry.entry_id} is empty.')
        if any(not isinstance(member, WardogsPlayerSnapshot) for member in entry.members):
            raise WardogsMatchmakingInputError(f'Queue entry {entry.entry_id} has an invalid player snapshot.')
        member_names = [member.username for member in entry.members]
        if any(not isinstance(name, str) or not name.strip() or name != name.strip() for name in member_names):
            raise WardogsMatchmakingInputError(f'Queue entry {entry.entry_id} has an invalid CMP identity.')
        if entry.kind == 'solo':
            if (len(entry.members) != 1 or entry.source_party_code is not None
                    or entry.leader_username is not None):
                raise WardogsMatchmakingInputError('Solo entries must contain one player and no party metadata.')
        else:
            if len(entry.members) < 2:
                raise WardogsMatchmakingInputError('Premade entries must contain at least two accepted players.')
            if not isinstance(entry.source_party_code, str) or not entry.source_party_code.strip():
                raise WardogsMatchmakingInputError('Premade entries require a source CMP party code.')
            if entry.leader_username is not None and not isinstance(entry.leader_username, str):
                raise WardogsMatchmakingInputError('Premade leader identity must be a CMP username or null.')
            if entry.leader_username is not None and entry.leader_username not in member_names:
                raise WardogsMatchmakingInputError('Premade leader must be one of its accepted members or null.')
        if any(member.display_name is not None and not isinstance(member.display_name, str)
               or member.steam_id is not None and not isinstance(member.steam_id, str)
               for member in entry.members):
            raise WardogsMatchmakingInputError(f'Queue entry {entry.entry_id} has invalid profile identity fields.')
        player_ids.extend(member_names)

    if len(set(player_ids)) != len(player_ids):
        raise WardogsMatchmakingInputError('A CMP user appears in more than one queue entry.')
    if set(player_ids) != set(matchmaking_input.accepted_players):
        raise WardogsMatchmakingInputError('Queue entries must include every accepted player exactly once.')
    return True


def build_wardogs_matchmaking_input(
    accepted_players,
    *,
    match_id,
    queue_mode,
    queue_modes,
    groups,
    user_to_group,
    profiles=None,
    created_at=None,
):
    """Snapshot accepted CMP users into immutable solo and premade entries.

    A valid party requires a matching code, a unique list of at least two
    members, a leader in that list, and consistent reverse membership links.
    Any stale or conflicting party state is treated as solos so accepted users
    are never lost or silently combined under ambiguous ownership.
    """
    match_id = _clean_identity(match_id)
    queue_mode = _clean_identity(queue_mode)
    if not match_id:
        raise WardogsMatchmakingInputError('Match ID is required.')
    if not queue_mode:
        raise WardogsMatchmakingInputError('Queue mode is required.')
    if resolve_queue_game_type(queue_modes, queue_mode, GAME_TYPE) != GAME_TYPE:
        raise WardogsMatchmakingInputError('Queue mode is not configured for game_type="wardogs".')

    accepted = tuple(_clean_identity(player) for player in (accepted_players or ()))
    if any(not player for player in accepted):
        raise WardogsMatchmakingInputError('Accepted players must have valid CMP identities.')
    if len(set(accepted)) != len(accepted):
        raise WardogsMatchmakingInputError('Accepted player list contains duplicates.')
    if not accepted:
        raise WardogsMatchmakingInputError('At least one accepted player is required.')

    groups = groups if isinstance(groups, Mapping) else {}
    user_to_group = user_to_group if isinstance(user_to_group, Mapping) else {}
    profiles = profiles if isinstance(profiles, Mapping) else {}

    normalized_groups = {}
    memberships = {}
    invalid_codes = set()
    for mapping_code, raw_group in groups.items():
        code = _clean_identity(mapping_code)
        group = raw_group if isinstance(raw_group, Mapping) else {}
        stored_code = _clean_identity(group.get('code'))
        raw_members = group.get('members')
        members = tuple(_clean_identity(member) for member in raw_members) if isinstance(raw_members, (list, tuple)) else ()
        leader = _clean_identity(group.get('leader'))
        structurally_valid = (
            bool(code)
            and stored_code == code
            and len(members) >= 2
            and all(members)
            and len(set(members)) == len(members)
            and leader in members
        )
        if code:
            for member in set(members):
                memberships.setdefault(member, set()).add(code)
        if structurally_valid:
            normalized_groups[code] = (leader, members)
        else:
            invalid_codes.add(code)

    for member, codes in memberships.items():
        if len(codes) > 1:
            invalid_codes.update(codes)

    # A reverse mapping that disagrees with group membership invalidates every
    # implicated party. The affected accepted players become individual solos.
    for player in set(memberships) | set(user_to_group):
        mapped_code = _clean_identity(user_to_group.get(player))
        member_codes = memberships.get(player, set())
        if member_codes and (not mapped_code or mapped_code not in normalized_groups or member_codes != {mapped_code}):
            invalid_codes.update(member_codes)
            if mapped_code:
                invalid_codes.add(mapped_code)
        elif mapped_code and mapped_code in normalized_groups and member_codes != {mapped_code}:
            invalid_codes.add(mapped_code)

    member_snapshots = {}
    for player in accepted:
        profile = profiles.get(player)
        profile = profile if isinstance(profile, Mapping) else {}
        display_name = _clean_identity(profile.get('display_name')) or None
        steam_id = _clean_identity(profile.get('steam_id')) or None
        member_snapshots[player] = WardogsPlayerSnapshot(
            username=player,
            display_name=display_name,
            steam_id=steam_id,
        )

    accepted_set = set(accepted)
    grouped_players = {}
    entry_specs = []
    emitted_codes = set()
    for player in accepted:
        code = _clean_identity(user_to_group.get(player))
        valid_party = code in normalized_groups and code not in invalid_codes
        if valid_party:
            leader, party_members = normalized_groups[code]
            if code not in emitted_codes:
                eligible_members = tuple(member for member in party_members if member in accepted_set)
                if len(eligible_members) >= 2:
                    emitted_codes.add(code)
                    grouped_players.update({member: code for member in eligible_members})
                    entry_specs.append((
                        'premade', code, leader if leader in eligible_members else None,
                        tuple(member_snapshots[member] for member in eligible_members),
                    ))
                else:
                    # A one-person accepted remnant is a solo queue entry.
                    emitted_codes.add(code)
                    for member in eligible_members:
                        grouped_players[member] = code
                        entry_specs.append(('solo', None, None, (member_snapshots[member],)))
            if grouped_players.get(player) == code:
                continue
        entry_specs.append(('solo', None, None, (member_snapshots[player],)))

    entries = tuple(
        WardogsQueueEntry(
            entry_id=_stable_entry_id(match_id, queue_mode, kind, party_code, members),
            kind=kind,
            game_type=GAME_TYPE,
            queue_mode=queue_mode,
            members=members,
            source_party_code=party_code,
            leader_username=leader,
        )
        for kind, party_code, leader, members in entry_specs
    )
    try:
        snapshot_time = float(time.time() if created_at is None else created_at)
    except (TypeError, ValueError, OverflowError) as exc:
        raise WardogsMatchmakingInputError('Snapshot timestamp must be numeric.') from exc
    if not math.isfinite(snapshot_time):
        raise WardogsMatchmakingInputError('Snapshot timestamp must be finite.')

    result = WardogsMatchmakingInput(
        match_id=match_id,
        game_type=GAME_TYPE,
        queue_mode=queue_mode,
        created_at=snapshot_time,
        accepted_players=accepted,
        entries=entries,
    )
    validate_wardogs_matchmaking_input(result)
    return result
