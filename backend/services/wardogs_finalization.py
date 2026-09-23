"""Build one CMP-owned WARDOGS lobby from a fully accepted pending match."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import sqlite3

from services.wardogs_assignment import (
    WardogsAssignmentConfig,
    WardogsAssignmentResult,
    assign_wardogs_factions,
    validate_wardogs_assignment_result,
)
from services.wardogs_lobby import (
    build_wardogs_read_model,
    create_wardogs_lobby,
    get_wardogs_lobby,
    validate_lobby,
)
from services.wardogs_matchmaking import build_wardogs_matchmaking_input


@dataclass(frozen=True)
class WardogsFinalizationResult:
    status: str
    lobby_id: str | None = None
    read_model: dict | None = None
    unassigned: tuple = ()
    errors: tuple = ()

    @property
    def success(self):
        return self.status == 'complete' and self.lobby_id is not None


def _lobby_id(match_id):
    digest = hashlib.sha256(match_id.encode('utf-8')).hexdigest()[:24]
    return f'wardogs_lobby_{digest}'


def _mapped_group(entry, roster_status):
    return {
        'id': entry.entry_id,
        'type': 'solo' if entry.kind == 'solo' else 'premade',
        'name': 'Solo' if entry.kind == 'solo' else 'Premade',
        'leaderId': entry.leader_username,
        'players': [{
            'id': member.username,
            'displayName': member.display_name or member.username,
            'steamId': member.steam_id,
            'registered': True,
            'rosterStatus': roster_status,
            'ready': False,
        } for member in entry.members],
    }


def _planned_lobby(snapshot, assignment, config, created_at):
    return {
        'id': _lobby_id(snapshot.match_id),
        'phase': 'assembling',
        'label': 'WARDOGS lobby',
        'serverId': None,
        'provenance': {
            'pendingMatchId': snapshot.match_id,
            'queueMode': snapshot.queue_mode,
            'gameType': snapshot.game_type,
            'snapshotSource': 'accepted_cmp_party_snapshot',
            'snapshotCreatedAt': snapshot.created_at,
            'createdAt': created_at.isoformat(),
            'assignmentConfiguration': {
                'factions': list(config.factions),
                'activePerFaction': config.active_per_faction,
                'reservePerFaction': config.reserve_per_faction,
                'allowPremadeSplit': config.allow_premade_split,
            },
        },
        'factions': [{
            'id': faction.faction_id,
            'commanderId': None,
            'groups': ([_mapped_group(entry, 'active') for entry in faction.active_entries]
                       + [_mapped_group(entry, 'reserve') for entry in faction.reserve_entries]),
        } for faction in assignment.factions],
    }


def _same_finalization(existing, planned):
    old_source = existing.get('provenance') or {}
    new_source = planned['provenance']
    return (existing.get('factions') == planned['factions']
            and old_source.get('pendingMatchId') == new_source['pendingMatchId']
            and old_source.get('queueMode') == new_source['queueMode']
            and old_source.get('gameType') == new_source['gameType']
            and old_source.get('assignmentConfiguration') == new_source['assignmentConfiguration'])


def finalize_wardogs_accepted_match(
    pending_match, *, queue_modes, groups, user_to_group, profiles,
    config: WardogsAssignmentConfig, get_db_connection, created_at=None,
):
    """Return a complete lobby or diagnostics; persist only after full validation."""
    if (not isinstance(pending_match, dict) or pending_match.get('game_type') != 'wardogs'
            or not isinstance(pending_match.get('id'), str)
            or not isinstance(pending_match.get('queue_mode'), str)):
        return WardogsFinalizationResult('invalid', errors=('Invalid WARDOGS pending match context.',))
    players = pending_match.get('players')
    accepted = pending_match.get('accepted')
    if (not isinstance(players, (list, tuple)) or not players
            or any(not isinstance(player, str) or not player for player in players)
            or not isinstance(accepted, dict)
            or any(accepted.get(player) is not True for player in players)):
        return WardogsFinalizationResult('invalid', errors=('Every pending-match player must accept before finalization.',))

    try:
        timestamp = created_at or datetime.now(timezone.utc)
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise ValueError('Creation timestamp must include a timezone.')
        snapshot = build_wardogs_matchmaking_input(
            players, match_id=pending_match['id'], queue_mode=pending_match['queue_mode'],
            queue_modes=queue_modes, groups=groups, user_to_group=user_to_group,
            profiles=profiles, created_at=timestamp.timestamp(),
        )
        assignment = assign_wardogs_factions(snapshot, config)
    except (ValueError, TypeError, AttributeError) as exc:
        return WardogsFinalizationResult('invalid', errors=(str(exc),))

    if not isinstance(assignment, WardogsAssignmentResult):
        return WardogsFinalizationResult('invalid', errors=('WARDOGS assignment returned an invalid result.',))
    if assignment.status == 'partial':
        return WardogsFinalizationResult(
            'partial', unassigned=assignment.unassigned,
            errors=('Some accepted entries cannot fit in active or reserve capacity.',),
        )
    if assignment.status != 'complete':
        return WardogsFinalizationResult('invalid', errors=assignment.errors or ('WARDOGS assignment is invalid.',))

    try:
        validate_wardogs_assignment_result(snapshot, config, assignment)
        lobby = _planned_lobby(snapshot, assignment, config, timestamp)
        validate_lobby(lobby)
        roster_players = [player['id'] for faction in lobby['factions']
                          for group in faction['groups'] for player in group['players']]
        if Counter(roster_players) != Counter(snapshot.accepted_players):
            raise ValueError('Finalized WARDOGS roster does not cover accepted players exactly once.')
        read_model = build_wardogs_read_model(lobby, now=timestamp)
    except (ValueError, TypeError, AttributeError) as exc:
        return WardogsFinalizationResult('invalid', errors=(str(exc),))

    try:
        create_wardogs_lobby(get_db_connection, lobby)
    except sqlite3.IntegrityError:
        try:
            existing = get_wardogs_lobby(get_db_connection, lobby['id'])
        except Exception:
            existing = None
        if existing is None:
            return WardogsFinalizationResult('persistence_failed', errors=('WARDOGS lobby persistence failed.',))
        if not _same_finalization(existing, lobby):
            return WardogsFinalizationResult('invalid', errors=('A different WARDOGS roster already exists for this pending match.',))
        return WardogsFinalizationResult(
            'complete', lobby_id=lobby['id'],
            read_model=build_wardogs_read_model(existing, now=timestamp),
        )
    except Exception:
        return WardogsFinalizationResult('persistence_failed', errors=('WARDOGS lobby persistence failed.',))
    return WardogsFinalizationResult('complete', lobby_id=lobby['id'], read_model=read_model)
