"""CMP-owned WARDOGS roster and read-only server observation projection.

This table is populated by explicit service calls only. It is separate from the
two-team Squad runtime and contains no WDRCON credentials or server snapshots.
"""

from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone

from services.game_server_adapter import AdapterError
from services.game_server_contracts import PlayerSnapshot, ServerStatus


FACTIONS = (
    ("valkyra", "Valkyra", "#8b5568"),
    ("lonestar", "Lonestar", "#4b7186"),
    ("manticore", "Manticore", "#62754e"),
)
FACTION_IDS = {item[0] for item in FACTIONS}
GROUP_TYPES = {"solo", "premade", "squad", "clan"}
ROSTER_STATUSES = {"active", "reserve"}
PHASES = {"assembling", "live"}
OBSERVATION_MAX_AGE_SECONDS = 60
_JOIN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


def init_wardogs_lobby_tables(get_db_connection):
    with get_db_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS wardogs_lobbies (
            lobby_id TEXT PRIMARY KEY,
            schema_version INTEGER NOT NULL,
            roster_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        conn.commit()


def _player_ids(lobby):
    return {
        player["id"]
        for faction in lobby["factions"]
        for group in faction["groups"]
        for player in group["players"] if player["registered"]
    }


def latest_wardogs_lobby_for_user(get_db_connection, username):
    if not username:
        return None
    with get_db_connection() as conn:
        rows = conn.execute(
            'SELECT lobby_id, roster_json FROM wardogs_lobbies ORDER BY updated_at DESC'
        ).fetchall()
    for lobby_id, roster_json in rows:
        try:
            if username in _player_ids(json.loads(roster_json)):
                return lobby_id
        except (TypeError, ValueError, KeyError):
            continue
    return None


def validate_lobby(lobby):
    if not isinstance(lobby, dict) or not isinstance(lobby.get("id"), str) or not lobby["id"]:
        raise ValueError("WARDOGS lobby ID is required")
    if lobby.get("phase") not in PHASES:
        raise ValueError("Invalid WARDOGS lobby phase")
    if not isinstance(lobby.get("factions"), list) or len(lobby["factions"]) != 3:
        raise ValueError("WARDOGS lobby requires exactly three factions")
    if {faction.get("id") for faction in lobby["factions"]} != FACTION_IDS:
        raise ValueError("Invalid WARDOGS faction set")
    group_ids, player_ids = set(), set()
    for faction in lobby["factions"]:
        if not isinstance(faction.get("groups"), list):
            raise ValueError("Faction groups are required")
        faction_players = set()
        for group in faction["groups"]:
            group_id = group.get("id")
            if not isinstance(group_id, str) or not group_id or group_id in group_ids:
                raise ValueError("Group IDs must be stable and unique")
            group_ids.add(group_id)
            if group.get("type") not in GROUP_TYPES or not isinstance(group.get("players"), list):
                raise ValueError("Invalid WARDOGS group")
            if group["type"] == "solo" and len(group["players"]) != 1:
                raise ValueError("Solo groups require one player")
            for player in group["players"]:
                player_id = player.get("id")
                if not isinstance(player_id, str) or not player_id or player_id in player_ids:
                    raise ValueError("Player IDs must be stable and unique")
                if player.get("rosterStatus") not in ROSTER_STATUSES or not isinstance(player.get("ready"), bool):
                    raise ValueError("Invalid WARDOGS player roster or readiness")
                if not isinstance(player.get("registered"), bool):
                    raise ValueError("Registration state is required")
                player_ids.add(player_id)
                faction_players.add(player_id)
            if group.get("leaderId") is not None and group["leaderId"] not in {item["id"] for item in group["players"]}:
                raise ValueError("Group leader must belong to the group")
        if faction.get("commanderId") is not None and faction["commanderId"] not in faction_players:
            raise ValueError("Faction commander must belong to the faction")
    server_id = lobby.get("serverId")
    if server_id is not None and (isinstance(server_id, bool) or not isinstance(server_id, int) or server_id <= 0):
        raise ValueError("Invalid WARDOGS server association")
    provenance = lobby.get("provenance")
    if provenance is not None:
        if (not isinstance(provenance, dict)
                or not isinstance(provenance.get("pendingMatchId"), str) or not provenance["pendingMatchId"]
                or not isinstance(provenance.get("queueMode"), str) or not provenance["queueMode"]
                or provenance.get("gameType") != "wardogs"
                or provenance.get("snapshotSource") != "accepted_cmp_party_snapshot"
                or not isinstance(provenance.get("createdAt"), str) or not provenance["createdAt"]):
            raise ValueError("Invalid WARDOGS lobby provenance")
        assignment = provenance.get("assignmentConfiguration")
        if (not isinstance(assignment, dict)
                or assignment.get("factions") != [item[0] for item in FACTIONS]
                or isinstance(assignment.get("activePerFaction"), bool)
                or not isinstance(assignment.get("activePerFaction"), int)
                or assignment["activePerFaction"] <= 0
                or isinstance(assignment.get("reservePerFaction"), bool)
                or not isinstance(assignment.get("reservePerFaction"), int)
                or assignment["reservePerFaction"] < 0
                or assignment.get("allowPremadeSplit") is not False):
            raise ValueError("Invalid WARDOGS assignment provenance")
    return lobby


def _owned_lobby(lobby):
    validate_lobby(lobby)
    return {
        "id": lobby["id"], "phase": lobby["phase"], "label": lobby.get("label"),
        "serverId": lobby.get("serverId"),
        "provenance": lobby.get("provenance"),
        "factions": [{
            "id": faction["id"], "commanderId": faction.get("commanderId"),
            "groups": [{
                "id": group["id"], "type": group["type"], "name": group.get("name"),
                "leaderId": group.get("leaderId"),
                "players": [{
                    "id": player["id"], "displayName": player.get("displayName"),
                    "steamId": player.get("steamId"), "registered": player["registered"],
                    "rosterStatus": player["rosterStatus"], "ready": player["ready"],
                } for player in group["players"]],
            } for group in faction["groups"]],
        } for faction in lobby["factions"]],
    }


def _write_wardogs_lobby(get_db_connection, lobby, *, create_only):
    roster = json.dumps(_owned_lobby(lobby), ensure_ascii=True, sort_keys=True)
    now = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        sql = """INSERT INTO wardogs_lobbies (lobby_id, schema_version, roster_json, updated_at)
            VALUES (?, 1, ?, ?)"""
        if not create_only:
            sql += """ ON CONFLICT(lobby_id) DO UPDATE SET
                schema_version=excluded.schema_version, roster_json=excluded.roster_json,
                updated_at=excluded.updated_at"""
        conn.execute(sql, (lobby["id"], roster, now))
        conn.commit()


def save_wardogs_lobby(get_db_connection, lobby):
    """Internal/seed upsert API; no public mutation route is registered."""
    _write_wardogs_lobby(get_db_connection, lobby, create_only=False)


def create_wardogs_lobby(get_db_connection, lobby):
    """Atomically insert a finalized lobby without replacing an existing roster."""
    _write_wardogs_lobby(get_db_connection, lobby, create_only=True)


def get_wardogs_lobby(get_db_connection, lobby_id):
    with get_db_connection() as conn:
        row = conn.execute("SELECT schema_version, roster_json FROM wardogs_lobbies WHERE lobby_id=?",
                           (lobby_id,)).fetchone()
    if row is None:
        return None
    if row["schema_version"] != 1:
        raise ValueError("Unsupported WARDOGS lobby version")
    lobby = json.loads(row["roster_json"])
    return validate_lobby(lobby)


def can_read_lobby(lobby, username, is_admin=False):
    return bool(is_admin or username in _player_ids(lobby))


def _faction_id(name):
    if not isinstance(name, str):
        return None
    normalized = name.strip().casefold()
    return next((identifier for identifier, label, _ in FACTIONS if label.casefold() == normalized), None)


def _valid_steam_id(value):
    return isinstance(value, str) and len(value) == 17 and value.isdigit()


def _iso(value):
    return value.isoformat() if value is not None else None


def build_wardogs_join_state(lobby, server=None, *, join_id=None, observed_server_name=None):
    """Expose only the verified manual Join By ID workflow."""
    if lobby.get('serverId') is None:
        return {'state': 'waiting_for_server', 'serverName': None, 'joinId': None,
                'instructions': None, 'directJoinUrl': None}
    name = None
    if server and server.get('game_type') == 'wardogs':
        metadata = server.get('metadata') or {}
        server_info = metadata.get('serverInfo') if isinstance(metadata, dict) else None
        server_info = server_info if isinstance(server_info, dict) else {}
        candidate = str(observed_server_name or server_info.get('serverName')
                        or server.get('display_name') or '').strip()
        secret_ref = server.get('wdrcon_secret_env')
        forbidden = (server.get('bridge_url'), secret_ref,
                     os.environ.get(secret_ref) if secret_ref else None)
        if (candidate and len(candidate) <= 128 and not any(ord(char) < 32 for char in candidate)
                and not any(value and str(value).casefold() in candidate.casefold() for value in forbidden)):
            name = candidate
    normalized_join_id = join_id.strip() if isinstance(join_id, str) else None
    if normalized_join_id and (len(normalized_join_id) > 128 or not _JOIN_ID.fullmatch(normalized_join_id)):
        normalized_join_id = None
    if normalized_join_id:
        return {
            'state': 'manual_join_available', 'serverName': name,
            'joinId': normalized_join_id,
            'instructions': [
                'Open WARDOGS.',
                'Select Deploy.',
                'Open Community.',
                'Choose Join By ID.',
                'Enter the Join ID.',
                'Select Lookup.',
                'Join the resolved server.',
            ],
            'directJoinUrl': None,
        }
    return {'state': 'server_allocated_join_unavailable', 'serverName': name,
            'joinId': None, 'instructions': None, 'directJoinUrl': None}


def build_wardogs_read_model(lobby, *, players: PlayerSnapshot | None = None,
                             status: ServerStatus | None = None,
                             observed_at: datetime | None = None,
                             now: datetime | None = None, stale=False,
                             poll_state='not_attempted', attempted_at: datetime | None = None):
    """Combine durable roster and optional normalized observations without mutation."""
    validate_lobby(lobby)
    now = now or datetime.now(timezone.utc)
    observed_at = observed_at or (players.observed_at if players else None)
    observation_state = ("unavailable" if poll_state == "error" else "none") if observed_at is None else (
        "stale" if stale or (now - observed_at).total_seconds() > OBSERVATION_MAX_AGE_SECONDS else "fresh"
    )
    roster_observed = players is not None
    observed_by_steam = {}
    duplicates = set()
    if roster_observed:
        for item in players.players:
            if _valid_steam_id(item.steam_id):
                if item.steam_id in observed_by_steam:
                    duplicates.add(item.steam_id)
                observed_by_steam[item.steam_id] = item
    planned_steam = set()
    planned_steam_counts = Counter(
        player.get("steamId") for faction in lobby["factions"]
        for group in faction["groups"] for player in group["players"]
        if _valid_steam_id(player.get("steamId"))
    )
    factions = []
    for faction_id, label, color in FACTIONS:
        owned = next(item for item in lobby["factions"] if item["id"] == faction_id)
        groups = []
        active, reserve, connected, ready, aligned, mismatched = 0, 0, 0, 0, 0, 0
        for group in owned["groups"]:
            members = []
            for player in group["players"]:
                steam_id = player.get("steamId") or None
                if steam_id:
                    planned_steam.add(steam_id)
                unique_identity = (_valid_steam_id(steam_id) and steam_id not in duplicates
                                   and planned_steam_counts[steam_id] == 1)
                observed = observed_by_steam.get(steam_id) if roster_observed and unique_identity else None
                is_connected = (observed is not None if roster_observed and unique_identity else None)
                observed_faction = _faction_id(observed.faction) if observed else None
                alignment = ("unknown" if is_connected is not True or observed_faction is None
                             else "aligned" if observed_faction == faction_id else "mismatch")
                role = player["rosterStatus"]
                if role == "active":
                    active += 1
                    ready += int(player["ready"])
                    connected += int(is_connected is True)
                    aligned += int(alignment == "aligned")
                    mismatched += int(alignment == "mismatch")
                else:
                    reserve += 1
                members.append({
                    "id": player["id"], "displayName": player.get("displayName") or player["id"],
                    "steamId": steam_id, "groupId": group["id"], "registered": player["registered"],
                    "rosterStatus": role, "ready": player["ready"],
                    "plannedFactionId": faction_id, "connected": is_connected,
                    "observedFactionId": observed_faction,
                    "observedFactionName": observed.faction if observed else None,
                    "alignmentState": alignment, "isLeader": group.get("leaderId") == player["id"],
                })
            groups.append({"id": group["id"], "name": group.get("name") or ("Solo" if group["type"] == "solo" else "Premade"),
                           "type": group["type"], "leaderId": group.get("leaderId"),
                           "plannedFactionId": faction_id, "players": members})
        factions.append({"id": faction_id, "name": label, "color": color,
                         "commanderId": owned.get("commanderId"), "groups": groups,
                         "summary": {"planned": active + reserve, "active": active,
                                     "reserves": reserve, "connected": connected if roster_observed else None,
                                     "ready": ready, "aligned": aligned if roster_observed else None,
                                     "mismatched": mismatched if roster_observed else None}})
    unexpected = []
    if roster_observed:
        for item in players.players:
            if (not _valid_steam_id(item.steam_id) or item.steam_id not in planned_steam or
                    item.steam_id in duplicates or planned_steam_counts[item.steam_id] != 1):
                unexpected.append({"steamId": item.steam_id, "displayName": item.display_name,
                                   "observedFactionId": _faction_id(item.faction),
                                   "observedFactionName": item.faction})
    scores = {faction_id: None for faction_id in FACTION_IDS}
    if status:
        for score in status.faction_scores:
            faction_id = _faction_id(score.faction)
            if faction_id:
                scores[faction_id] = score.score
    return {
        "id": lobby["id"], "source": "cmp-backend", "phase": lobby["phase"],
        "label": lobby.get("label") or "WARDOGS lobby", "serverId": lobby.get("serverId"),
        "join": build_wardogs_join_state(lobby),
        "server": {"state": observation_state,
                   "name": status.server_name if status else None,
                   "label": {
            "none": "No server observation yet", "fresh": "Server observed",
            "stale": "Last server observation may be stale",
            "unavailable": "Server observation unavailable"}[observation_state]},
        "observation": {"state": observation_state, "pollState": poll_state,
                        "observedAt": _iso(observed_at), "attemptedAt": _iso(attempted_at)},
        "configuration": {"map": status.map_id if status else None,
                          "experience": ", ".join(status.experiences) if status else None,
                          "lighting": status.lighting if status else None,
                          "zoneAlternator": status.alternator if status else None},
        "serverStatus": {"currentPlayers": status.current_players,
                         "maxPlayers": status.max_players,
                         "rotation": {"nowIndex": status.rotation_now_index,
                                      "nextIndex": status.rotation_next_index},
                         "scoreTick": {"current": status.score_tick.current,
                                       "minimum": status.score_tick.minimum,
                                       "maximum": status.score_tick.maximum} if status.score_tick else None,
                         "observedAt": _iso(status.observed_at)} if status else None,
        "factions": factions, "scores": scores, "unexpectedPlayers": unexpected,
        "result": {"status": "unconfirmed", "note": "No authoritative result is available."},
        "observations": [],
    }


# Process-local observations are reconstructed after restart by the periodic
# worker. They never enter the CMP-owned planned roster table.
@dataclass(frozen=True)
class WardogsObservation:
    players: PlayerSnapshot | None = None
    status: ServerStatus | None = None
    observed_at: datetime | None = None
    attempted_at: datetime | None = None
    poll_state: str = 'not_attempted'


_last_observations: dict[tuple[str, int], WardogsObservation] = {}
_join_ids: dict[tuple[str, int], str] = {}


def _observation_key(lobby):
    return lobby['id'], lobby.get('serverId')


def read_wardogs_lobby(lobby, *, now=None):
    """Project the latest bounded poll; HTTP reads never start status/player reads."""
    now = now or datetime.now(timezone.utc)
    cached = _last_observations.get(_observation_key(lobby)) if lobby.get('serverId') else None
    if cached is None:
        model = build_wardogs_read_model(lobby, now=now)
    else:
        model = build_wardogs_read_model(
            lobby, players=cached.players, status=cached.status,
            observed_at=cached.observed_at, attempted_at=cached.attempted_at,
            poll_state=cached.poll_state, stale=cached.poll_state == 'error', now=now)
    from app_state import DEV_MODE
    from services.wardogs_dev import decorate_read_model
    return decorate_read_model(lobby, model, dev_mode=DEV_MODE)


def mark_wardogs_observation_error(lobby, *, now=None):
    """Preserve the last complete read when a poll or adapter setup fails."""
    if lobby.get('serverId') is None:
        return read_wardogs_lobby(lobby, now=now)
    now = now or datetime.now(timezone.utc)
    key = _observation_key(lobby)
    _last_observations[key] = replace(
        _last_observations.get(key, WardogsObservation()),
        attempted_at=now, poll_state='error')
    return read_wardogs_lobby(lobby, now=now)


def observe_wardogs_lobby(lobby, adapter, *, now=None):
    """Perform one status/player poll and retain only complete normalized reads."""
    if lobby.get('serverId') is None:
        return read_wardogs_lobby(lobby, now=now)
    now = now or datetime.now(timezone.utc)
    if adapter is None:
        return mark_wardogs_observation_error(lobby, now=now)
    try:
        status = adapter.get_status()
        players = adapter.get_players()
    except AdapterError:
        return mark_wardogs_observation_error(lobby, now=now)
    _last_observations[_observation_key(lobby)] = WardogsObservation(
        players=players, status=status,
        observed_at=min(status.observed_at, players.observed_at),
        attempted_at=now, poll_state='ok')
    return read_wardogs_lobby(lobby, now=now)


def wardogs_observation_signature(lobby):
    """Ignore timestamps when deciding whether server-visible content changed."""
    cached = _last_observations.get(_observation_key(lobby))
    if cached is None:
        return None
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
    return (
        cached.poll_state,
        replace(cached.status, observed_at=epoch) if cached.status else None,
        replace(cached.players, observed_at=epoch) if cached.players else None,
    )


def get_or_fetch_wardogs_join_id(lobby, adapter):
    """A Join ID is server identity; reuse a successful read for this allocation."""
    if adapter is None or lobby.get('serverId') is None:
        return None
    key = _observation_key(lobby)
    if key not in _join_ids:
        try:
            _join_ids[key] = adapter.get_join_id()
        except AdapterError:
            return None
    return _join_ids[key]


def clear_wardogs_observation(lobby_id=None, server_id=None):
    """Discard process-local state after explicit lobby cleanup/release."""
    for key in tuple(_last_observations):
        if (lobby_id is None or key[0] == lobby_id) and (server_id is None or key[1] == server_id):
            _last_observations.pop(key, None)
    for key in tuple(_join_ids):
        if (lobby_id is None or key[0] == lobby_id) and (server_id is None or key[1] == server_id):
            _join_ids.pop(key, None)
    from services.wardogs_dev import clear_simulation
    clear_simulation(lobby_id)


def prune_wardogs_observations(eligible_keys):
    """Remove cache entries whose persisted lobby/server association disappeared."""
    for key in set(_last_observations) | set(_join_ids):
        if key not in eligible_keys:
            clear_wardogs_observation(*key)
