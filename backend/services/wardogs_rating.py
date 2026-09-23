"""Versioned WARDOGS rating calculation and transactional full-history replay."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP, localcontext

from services.wardogs_lobby import FACTIONS


VERSION = 'wardogs_rating_v1'
START_RATING = 1000
K = Decimal(24)
FACTION_ORDER = tuple(item[0] for item in FACTIONS)
LOGGER = logging.getLogger(__name__)


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def pairwise_actual_scores(groups):
    """Return each canonical unordered pair's first-faction score."""
    if not isinstance(groups, list) or not 1 <= len(groups) <= 3:
        raise ValueError('placement_unavailable')
    ranks = {}
    for rank, group in enumerate(groups):
        if not isinstance(group, list) or not group:
            raise ValueError('malformed_placement')
        for faction in group:
            if faction not in FACTION_ORDER or faction in ranks:
                raise ValueError('malformed_placement')
            ranks[faction] = rank
    if set(ranks) != set(FACTION_ORDER):
        raise ValueError('malformed_placement')
    return {(left, right): (Decimal('0.5') if ranks[left] == ranks[right]
                            else Decimal(int(ranks[left] < ranks[right])))
            for index, left in enumerate(FACTION_ORDER)
            for right in FACTION_ORDER[index + 1:]}


def round_half_away(value):
    return int(Decimal(value).to_integral_value(rounding=ROUND_HALF_UP))


def conserve_deltas(raw):
    """Round each faction, then assign one-point residuals to largest rounding errors.

    A positive drift decrements the faction whose rounded value is furthest
    above its raw value; a negative drift increments the one furthest below.
    Canonical faction order breaks exact ties. This minimizes added error.
    """
    rounded = {faction: round_half_away(raw[faction]) for faction in FACTION_ORDER}
    drift = sum(rounded.values())
    while drift:
        if drift > 0:
            faction = max(FACTION_ORDER, key=lambda item: (Decimal(rounded[item]) - raw[item],
                                                          -FACTION_ORDER.index(item)))
            rounded[faction] -= 1
            drift -= 1
        else:
            faction = max(FACTION_ORDER, key=lambda item: (raw[item] - Decimal(rounded[item]),
                                                          -FACTION_ORDER.index(item)))
            rounded[faction] += 1
            drift += 1
    return rounded


def calculate_match(roster, ratings, placement_groups):
    """Pure calculation; roster maps each faction to equally sized account IDs."""
    if set(roster) != set(FACTION_ORDER):
        raise ValueError('malformed_roster')
    counts = [len(roster[faction]) for faction in FACTION_ORDER]
    if not all(counts):
        raise ValueError('zero_active_players')
    if len(set(counts)) != 1:
        raise ValueError('unequal_faction_sizes')
    players = [player for faction in FACTION_ORDER for player in roster[faction]]
    if len(players) != len(set(players)) or any(player not in ratings for player in players):
        raise ValueError('unresolved_player_identity')
    outcomes = pairwise_actual_scores(placement_groups)
    with localcontext() as context:
        context.prec = 50
        means = {faction: sum(Decimal(ratings[player]) for player in roster[faction]) / counts[0]
                 for faction in FACTION_ORDER}
        raw = {faction: Decimal(0) for faction in FACTION_ORDER}
        for (left, right), actual in outcomes.items():
            expected = Decimal(1) / (Decimal(1) + Decimal(10) ** ((means[right] - means[left]) / 400))
            contribution = K * (actual - expected)
            raw[left] += contribution
            raw[right] -= contribution
        deltas = conserve_deltas(raw)
    return {'meanRatings': means, 'pairwiseScores': outcomes, 'rawDeltas': raw,
            'factionDeltas': deltas,
            'playerDeltas': {player: deltas[faction] for faction in FACTION_ORDER
                             for player in roster[faction]}}


def init_wardogs_rating_tables(get_db_connection, *, now=None):
    """The first startup durably fixes the rating-era cutover; no backfill."""
    activation = (now or datetime.now(timezone.utc)).isoformat()
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute('''CREATE TABLE IF NOT EXISTS wardogs_rating_state (
            singleton INTEGER PRIMARY KEY CHECK(singleton=1), activation_at TEXT NOT NULL,
            active_generation_id INTEGER)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS wardogs_rating_rosters (
            lobby_id TEXT PRIMARY KEY, roster_json TEXT NOT NULL, captured_at TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS wardogs_rating_generations (
            generation_id INTEGER PRIMARY KEY AUTOINCREMENT, predecessor_id INTEGER,
            revision_fingerprint TEXT NOT NULL, calculation_version TEXT NOT NULL,
            created_at TEXT NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS wardogs_rating_events (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT, generation_id INTEGER NOT NULL,
            lobby_id TEXT NOT NULL, result_revision_id TEXT NOT NULL, player_id TEXT NOT NULL,
            faction_id TEXT NOT NULL, match_order INTEGER NOT NULL,
            rating_before INTEGER NOT NULL, delta INTEGER NOT NULL, rating_after INTEGER NOT NULL,
            calculation_version TEXT NOT NULL, created_at TEXT NOT NULL,
            UNIQUE(generation_id, lobby_id, player_id))''')
        conn.execute('''CREATE TABLE IF NOT EXISTS wardogs_rating_current (
            player_id TEXT PRIMARY KEY, rating INTEGER NOT NULL, generation_id INTEGER NOT NULL)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS wardogs_rating_skips (
            generation_id INTEGER NOT NULL, lobby_id TEXT NOT NULL, result_revision_id TEXT NOT NULL,
            reason TEXT NOT NULL, PRIMARY KEY(generation_id, lobby_id))''')
        for table in ('wardogs_rating_rosters', 'wardogs_rating_generations',
                      'wardogs_rating_events', 'wardogs_rating_skips'):
            for operation in ('UPDATE', 'DELETE'):
                conn.execute(f'''CREATE TRIGGER IF NOT EXISTS immutable_{table}_{operation.lower()}
                    BEFORE {operation} ON {table} BEGIN
                    SELECT RAISE(ABORT, 'WARDOGS rating audit rows are immutable'); END''')
        conn.execute('''CREATE TRIGGER IF NOT EXISTS immutable_wardogs_rating_activation
            BEFORE UPDATE OF activation_at ON wardogs_rating_state BEGIN
            SELECT RAISE(ABORT, 'WARDOGS rating activation is immutable'); END''')
        conn.execute('INSERT OR IGNORE INTO wardogs_rating_state VALUES (1, ?, NULL)', (activation,))


def _snapshot_roster(conn, lobby_id, timestamp):
    if conn.execute('SELECT 1 FROM wardogs_rating_rosters WHERE lobby_id=?', (lobby_id,)).fetchone():
        return
    row = conn.execute('SELECT roster_json FROM wardogs_lobbies WHERE lobby_id=?', (lobby_id,)).fetchone()
    if row:
        conn.execute('INSERT INTO wardogs_rating_rosters VALUES (?, ?, ?)',
                     (lobby_id, row['roster_json'], timestamp))


def _eligible_roster(conn, lobby_id):
    row = conn.execute('SELECT roster_json FROM wardogs_rating_rosters WHERE lobby_id=?', (lobby_id,)).fetchone()
    if row is None:
        raise ValueError('roster_unavailable')
    try:
        lobby = json.loads(row['roster_json'])
        factions = {faction['id']: faction for faction in lobby['factions']}
        if set(factions) != set(FACTION_ORDER):
            raise ValueError('malformed_roster')
        roster = {}
        for faction_id in FACTION_ORDER:
            active = [player for group in factions[faction_id]['groups'] for player in group['players']
                      if player['rosterStatus'] == 'active']
            if any(not player['registered'] for player in active):
                raise ValueError('unresolved_player_identity')
            roster[faction_id] = sorted(player['id'] for player in active)
        counts = [len(roster[faction]) for faction in FACTION_ORDER]
        if not all(counts):
            raise ValueError('zero_active_players')
        if len(set(counts)) != 1:
            raise ValueError('unequal_faction_sizes')
        players = [player for members in roster.values() for player in members]
        if len(set(players)) != len(players):
            raise ValueError('unresolved_player_identity')
        known = {row['username'] for row in conn.execute(
            f'SELECT username FROM users WHERE username IN ({",".join("?" for _ in players)})', players)}
        if set(players) != known:
            raise ValueError('unresolved_player_identity')
        return roster
    except (KeyError, TypeError, IndexError, json.JSONDecodeError) as error:
        raise ValueError('malformed_roster') from error


def replay_current_results(conn, *, now=None):
    """Called inside the authoritative revision transaction, before commit."""
    state = conn.execute('SELECT * FROM wardogs_rating_state WHERE singleton=1').fetchone()
    if state is None:
        raise RuntimeError('WARDOGS rating storage is not initialized')
    rows = conn.execute('''SELECT current.*, first.confirmed_at AS effective_at
        FROM wardogs_result_revisions current
        JOIN (SELECT lobby_id, MAX(revision_number) AS latest FROM wardogs_result_revisions
              GROUP BY lobby_id) head
          ON current.lobby_id=head.lobby_id AND current.revision_number=head.latest
        JOIN wardogs_result_revisions first
          ON first.lobby_id=current.lobby_id AND first.revision_number=1
        ''').fetchall()
    # Parse timestamps before filtering/sorting: ISO strings with different UTC
    # offsets or fractional precision do not have reliable lexical order.
    def instant(value):
        try:
            parsed = datetime.fromisoformat(value)
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None
    activation = instant(state['activation_at'])
    if activation is None:
        raise RuntimeError('Invalid WARDOGS rating activation timestamp')
    rows = [row for row in rows if instant(row['effective_at']) is not None
            and instant(row['effective_at']) >= activation]
    rows.sort(key=lambda row: (instant(row['effective_at']), row['lobby_id']))
    fingerprint = hashlib.sha256(_json([(row['lobby_id'], row['revision_id']) for row in rows]).encode()).hexdigest()
    active = state['active_generation_id']
    if active is not None:
        previous = conn.execute('SELECT revision_fingerprint, calculation_version FROM wardogs_rating_generations WHERE generation_id=?',
                                (active,)).fetchone()
        if previous and previous['revision_fingerprint'] == fingerprint and previous['calculation_version'] == VERSION:
            return active
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    generation = conn.execute('''INSERT INTO wardogs_rating_generations
        (predecessor_id, revision_fingerprint, calculation_version, created_at)
        VALUES (?, ?, ?, ?)''', (active, fingerprint, VERSION, timestamp)).lastrowid
    ratings = {}
    for order, row in enumerate(rows):
        reason = None
        if row['status'] not in {'completed_win', 'tie'}:
            reason = 'unsupported_outcome'
        elif not row['placement_groups_json']:
            reason = 'placement_unavailable'
        else:
            try:
                roster = _eligible_roster(conn, row['lobby_id'])
                players = [player for faction in FACTION_ORDER for player in roster[faction]]
                before = {player: ratings.get(player, START_RATING) for player in players}
                calculation = calculate_match(roster, before, json.loads(row['placement_groups_json']))
            except json.JSONDecodeError:
                reason = 'malformed_placement'
            except ValueError as error:
                reason = str(error)
        if reason:
            conn.execute('INSERT INTO wardogs_rating_skips VALUES (?, ?, ?, ?)',
                         (generation, row['lobby_id'], row['revision_id'], reason))
            LOGGER.info('WARDOGS rating skipped lobby=%s revision=%s reason=%s',
                        row['lobby_id'], row['revision_id'], reason)
            continue
        for faction in FACTION_ORDER:
            for player in roster[faction]:
                delta = calculation['factionDeltas'][faction]
                after = before[player] + delta
                conn.execute('''INSERT INTO wardogs_rating_events
                    (generation_id, lobby_id, result_revision_id, player_id, faction_id, match_order,
                     rating_before, delta, rating_after, calculation_version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (generation, row['lobby_id'], row['revision_id'], player, faction, order,
                     before[player], delta, after, VERSION, timestamp))
                ratings[player] = after
    conn.execute('DELETE FROM wardogs_rating_current')
    conn.executemany('INSERT INTO wardogs_rating_current VALUES (?, ?, ?)',
                     [(player, rating, generation) for player, rating in sorted(ratings.items())])
    conn.execute('UPDATE wardogs_rating_state SET active_generation_id=? WHERE singleton=1', (generation,))
    return generation


def apply_result_revision(conn, lobby_id, *, now=None):
    """Capture immutable roster input, then replay in the caller's transaction."""
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    _snapshot_roster(conn, lobby_id, timestamp)
    return replay_current_results(conn, now=now)


def get_player_rating(get_db_connection, username, lobby_id=None):
    with get_db_connection() as conn:
        row = conn.execute('SELECT rating FROM wardogs_rating_current WHERE player_id=?', (username,)).fetchone()
        rating = row['rating'] if row else START_RATING
        event = None
        if lobby_id:
            event = conn.execute('''SELECT e.rating_before, e.delta, e.rating_after FROM wardogs_rating_events e
                JOIN wardogs_rating_state s ON e.generation_id=s.active_generation_id
                WHERE e.lobby_id=? AND e.player_id=?''', (lobby_id, username)).fetchone()
    return {'currentRating': rating, 'match': ({'before': event['rating_before'],
            'delta': event['delta'], 'after': event['rating_after']} if event else None)}


def get_rating_skip(get_db_connection, lobby_id):
    with get_db_connection() as conn:
        row = conn.execute('''SELECT k.reason FROM wardogs_rating_skips k
            JOIN wardogs_rating_state s ON k.generation_id=s.active_generation_id
            WHERE k.lobby_id=?''', (lobby_id,)).fetchone()
    return row['reason'] if row else None
