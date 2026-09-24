"""Participant-only WARDOGS match summaries from durable authoritative state."""

import json
from datetime import datetime, timezone


def _instant(value):
    try:
        parsed = datetime.fromisoformat(value)
        return (parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None
                else parsed.astimezone(timezone.utc))
    except (TypeError, ValueError):
        return datetime.min.replace(tzinfo=timezone.utc)


def _position(roster_json, username):
    if not roster_json:
        return None
    try:
        roster = json.loads(roster_json)
        for faction in roster.get('factions', []):
            for group in faction.get('groups', []):
                for player in group.get('players', []):
                    if player.get('id') == username and player.get('registered') is True:
                        return {'factionId': faction['id'], 'rosterStatus': player['rosterStatus']}
    except (TypeError, ValueError, KeyError):
        return None
    return None


def _placement(groups, faction_id):
    if not isinstance(groups, list):
        return None, None
    rank = 1
    for group in groups:
        if not isinstance(group, list):
            return None, None
        if faction_id in group:
            return rank, len(group) > 1
        rank += len(group)
    return None, None


def get_current_wardogs_match(get_db_connection, username):
    if not username:
        return None
    with get_db_connection() as conn:
        rows = conn.execute('''SELECT l.lobby_id, l.roster_json FROM wardogs_lobbies l
            WHERE NOT EXISTS (SELECT 1 FROM wardogs_result_revisions r WHERE r.lobby_id=l.lobby_id)
            ORDER BY l.updated_at DESC''').fetchall()
    for row in rows:
        position = _position(row['roster_json'], username)
        if position:
            roster = json.loads(row['roster_json'])
            return {'lobbyId': row['lobby_id'], **position,
                    'state': ('server_allocated' if roster.get('serverId') is not None
                              else 'waiting_for_server'),
                    'createdAt': (roster.get('provenance') or {}).get('createdAt')}
    return None


def get_participant_wardogs_history(get_db_connection, username, *, limit=30):
    if not username:
        return []
    with get_db_connection() as conn:
        rows = conn.execute('''SELECT r.lobby_id, r.revision_id, r.revision_number,
                r.status, r.placement_groups_json, r.confirmed_at,
                first.confirmed_at AS first_confirmed_at,
                snapshot.roster_json AS snapshot_roster_json,
                lobby.roster_json AS lobby_roster_json,
                event.rating_before, event.delta, event.rating_after
            FROM wardogs_result_revisions r
            JOIN (SELECT lobby_id, MAX(revision_number) AS revision_number
                  FROM wardogs_result_revisions GROUP BY lobby_id) latest
              ON latest.lobby_id=r.lobby_id AND latest.revision_number=r.revision_number
            JOIN wardogs_result_revisions first
              ON first.lobby_id=r.lobby_id AND first.revision_number=1
            LEFT JOIN wardogs_rating_rosters snapshot ON snapshot.lobby_id=r.lobby_id
            LEFT JOIN wardogs_lobbies lobby ON lobby.lobby_id=r.lobby_id
            LEFT JOIN wardogs_rating_events event
              ON event.lobby_id=r.lobby_id AND event.player_id=?
             AND event.result_revision_id=r.revision_id
             AND event.generation_id=(SELECT active_generation_id
                                      FROM wardogs_rating_state WHERE singleton=1)
            ''', (username,)).fetchall()
    rows = sorted(rows, key=lambda row: (_instant(row['first_confirmed_at']),
                                         row['lobby_id']), reverse=True)
    history = []
    for row in rows:
        position = _position(row['snapshot_roster_json'] or row['lobby_roster_json'], username)
        if not position:
            continue
        groups = json.loads(row['placement_groups_json']) if row['placement_groups_json'] else None
        rank, _ = _placement(groups, position['factionId'])
        status = row['status']
        if status in {'incomplete', 'void'}:
            outcome = status
        elif rank is None:
            outcome = None
        elif status == 'tie' and rank == 1:
            outcome = 'tie'
        elif rank == 1:
            outcome = 'win'
        else:
            outcome = 'loss'
        rating = ({'before': row['rating_before'], 'delta': row['delta'],
                   'after': row['rating_after']}
                  if row['rating_after'] is not None else None)
        history.append({'lobbyId': row['lobby_id'], **position,
                        'result': {'status': status, 'outcome': outcome,
                                   'placement': rank, 'placementGroups': groups,
                                   'revisionNumber': row['revision_number'],
                                   'corrected': row['revision_number'] > 1,
                                   'confirmedAt': row['confirmed_at']},
                        'matchAt': row['first_confirmed_at'], 'rating': rating})
        if len(history) >= limit:
            break
    return history
