"""Append-only, explicitly confirmed WARDOGS result revisions."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from services.wardogs_lobby import FACTION_IDS, get_wardogs_lobby


RESULT_STATUSES = {'completed_win', 'tie', 'incomplete', 'void'}


class StaleWardogsRevisionError(Exception):
    """The result changed since the correction form was loaded."""


def _json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(',', ':'))


def _scores(value, *, required, observed=False):
    if value is None and not required:
        return None
    if not isinstance(value, dict) or set(value) != FACTION_IDS:
        raise ValueError('Scores must include all three WARDOGS factions')
    normalized = {}
    for faction_id, score in value.items():
        if observed and score is None:
            normalized[faction_id] = None
            continue
        if isinstance(score, bool) or not isinstance(score, int) or score < 0:
            raise ValueError('Faction scores must be nonnegative whole numbers')
        normalized[faction_id] = score
    return {key: normalized[key] for key in sorted(normalized)}


def _normalize_submission(payload):
    if (not isinstance(payload, dict)
            or not set(payload).issubset({'status', 'scores', 'winnerFaction', 'note'})
            or payload.get('status') not in RESULT_STATUSES):
        raise ValueError('Invalid WARDOGS result status')
    status = payload['status']
    scores = _scores(payload.get('scores'), required=status in {'completed_win', 'tie'})
    winner = payload.get('winnerFaction')
    if status == 'completed_win':
        if winner not in FACTION_IDS:
            raise ValueError('Choose one winning faction')
        highest = max(scores.values())
        if scores[winner] != highest or sum(score == highest for score in scores.values()) != 1:
            raise ValueError('The selected winner must have the unique highest final score')
    elif winner is not None:
        raise ValueError('Winner is only valid for a completed win')
    if status == 'tie':
        highest = max(scores.values())
        if sum(score == highest for score in scores.values()) < 2:
            raise ValueError('A tie requires at least two factions to share the highest final score')
    note = payload.get('note', '')
    if not isinstance(note, str) or len(note) > 1000:
        raise ValueError('Result note must be 1000 characters or fewer')
    return {'status': status, 'scores': scores, 'winnerFaction': winner,
            'tied': status == 'tie', 'note': note.strip() or None}


def init_wardogs_result_tables(get_db_connection):
    """Create revision storage and idempotently copy single-row legacy results."""
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        conn.execute("""CREATE TABLE IF NOT EXISTS wardogs_result_revisions (
            revision_id TEXT PRIMARY KEY,
            lobby_id TEXT NOT NULL,
            revision_number INTEGER NOT NULL,
            supersedes_revision_id TEXT,
            revision_type TEXT NOT NULL CHECK (revision_type IN ('confirmation', 'correction')),
            status TEXT NOT NULL,
            scores_json TEXT,
            winner_faction TEXT,
            tied INTEGER NOT NULL DEFAULT 0,
            actor_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            confirmed_at TEXT NOT NULL,
            note TEXT,
            correction_reason TEXT,
            observation_available INTEGER NOT NULL,
            observed_at TEXT,
            observed_scores_json TEXT,
            submitted_scores_json TEXT,
            differs_from_observation INTEGER,
            request_json TEXT NOT NULL,
            UNIQUE (lobby_id, revision_number)
        )""")
        conn.execute("""CREATE INDEX IF NOT EXISTS idx_wardogs_result_revisions_lobby
            ON wardogs_result_revisions (lobby_id, revision_number)""")
        # Keep the old table intact as a recoverable source. A deterministic ID
        # and unique sequence make copying safe on every startup.
        legacy_exists = conn.execute("""SELECT 1 FROM sqlite_master
            WHERE type='table' AND name='wardogs_results'""").fetchone()
        legacy_rows = (conn.execute('SELECT * FROM wardogs_results ORDER BY lobby_id').fetchall()
                       if legacy_exists else [])
        for row in legacy_rows:
            lobby_id = row['lobby_id']
            exists = conn.execute(
                'SELECT 1 FROM wardogs_result_revisions WHERE lobby_id=? AND revision_number=1',
                (lobby_id,),
            ).fetchone()
            if exists:
                continue
            try:
                submission = json.loads(row['submission_json'])
            except (TypeError, ValueError):
                submission = {
                    'status': row['status'], 'scores': _decode_scores(row['submitted_scores_json']),
                    'winnerFaction': row['winner_faction'], 'tied': bool(row['tied']), 'note': row['note'],
                }
            conn.execute("""INSERT INTO wardogs_result_revisions (
                revision_id, lobby_id, revision_number, supersedes_revision_id, revision_type,
                status, scores_json, winner_faction, tied, actor_id, created_at, confirmed_at,
                note, correction_reason, observation_available, observed_at, observed_scores_json,
                submitted_scores_json, differs_from_observation, request_json
            ) VALUES (?, ?, 1, NULL, 'confirmation', ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?)""", (
                f'legacy:{lobby_id}:1', lobby_id, row['status'], row['scores_json'],
                row['winner_faction'], row['tied'], row['confirmed_by'], row['confirmed_at'],
                row['confirmed_at'], row['note'], row['observation_available'], row['observed_at'],
                row['observed_scores_json'], row['submitted_scores_json'],
                row['differs_from_observation'], _json(submission),
            ))
        conn.commit()


def _decode_scores(value):
    return json.loads(value) if value else None


def _revision_rows(conn, lobby_id):
    return conn.execute(
        'SELECT * FROM wardogs_result_revisions WHERE lobby_id=? ORDER BY revision_number ASC',
        (lobby_id,),
    ).fetchall()


def _public_revision(row, *, corrected=False):
    if row is None:
        return {'status': 'unconfirmed', 'revisionNumber': None, 'corrected': False}
    return {
        'status': row['status'], 'scores': _decode_scores(row['scores_json']),
        'winnerFaction': row['winner_faction'], 'tied': bool(row['tied']),
        'confirmedAt': row['confirmed_at'], 'revisionNumber': row['revision_number'],
        'corrected': bool(corrected),
    }


def _current_row(conn, lobby_id):
    return conn.execute("""SELECT * FROM wardogs_result_revisions
        WHERE lobby_id=? ORDER BY revision_number DESC LIMIT 1""", (lobby_id,)).fetchone()


def get_wardogs_result(get_db_connection, lobby_id):
    with get_db_connection() as conn:
        row = _current_row(conn, lobby_id)
        count = conn.execute('SELECT COUNT(*) FROM wardogs_result_revisions WHERE lobby_id=?',
                             (lobby_id,)).fetchone()[0]
    return _public_revision(row, corrected=count > 1)


def get_wardogs_result_history(get_db_connection, lobby_id):
    """Admin-facing chronological chain with the current row marked by sequence."""
    with get_db_connection() as conn:
        rows = _revision_rows(conn, lobby_id)
        current_number = rows[-1]['revision_number'] if rows else None
        return [{
            'revisionId': row['revision_id'], 'revisionNumber': row['revision_number'],
            'supersedesRevisionId': row['supersedes_revision_id'],
            'revisionType': row['revision_type'], 'status': row['status'],
            'scores': _decode_scores(row['scores_json']), 'winnerFaction': row['winner_faction'],
            'tied': bool(row['tied']), 'actorId': row['actor_id'],
            'createdAt': row['created_at'], 'confirmedAt': row['confirmed_at'],
            'note': row['note'], 'correctionReason': row['correction_reason'],
            'observation': {
                'available': bool(row['observation_available']), 'observedAt': row['observed_at'],
                'scores': _decode_scores(row['observed_scores_json']),
                'submittedScores': _decode_scores(row['submitted_scores_json']),
                'differsFromObservation': (None if row['differs_from_observation'] is None
                                           else bool(row['differs_from_observation'])),
            },
            'authoritative': row['revision_number'] == current_number,
        } for row in rows]


def _provenance(observed_scores, observed_at, submitted_scores):
    observed = _scores(observed_scores, required=False, observed=True) if observed_scores is not None else None
    if observed is not None and observed_at is None:
        observed = None
    differs = (submitted_scores != observed
               if submitted_scores is not None and observed is not None else None)
    return observed, differs


def _insert_revision(conn, *, revision_id, lobby_id, revision_number, supersedes_revision_id,
                     revision_type, submission, actor_id, timestamp, correction_reason,
                     observed_scores, observed_at, differs, request_json):
    conn.execute("""INSERT INTO wardogs_result_revisions (
        revision_id, lobby_id, revision_number, supersedes_revision_id, revision_type,
        status, scores_json, winner_faction, tied, actor_id, created_at, confirmed_at,
        note, correction_reason, observation_available, observed_at, observed_scores_json,
        submitted_scores_json, differs_from_observation, request_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
        revision_id, lobby_id, revision_number, supersedes_revision_id, revision_type,
        submission['status'], _json(submission['scores']) if submission['scores'] is not None else None,
        submission['winnerFaction'], int(submission['tied']), actor_id, timestamp, timestamp,
        submission['note'], correction_reason, int(observed_scores is not None), observed_at,
        _json(observed_scores) if observed_scores is not None else None,
        _json(submission['scores']) if submission['scores'] is not None else None,
        None if differs is None else int(differs), request_json,
    ))


def _lobby_exists(get_db_connection, lobby_id):
    if get_wardogs_lobby(get_db_connection, lobby_id) is None:
        raise LookupError('WARDOGS lobby not found')


def confirm_wardogs_result(get_db_connection, lobby_id, confirmed_by, payload,
                           *, observed_scores=None, observed_at=None, now=None):
    """Create initial revision; identical retries never overwrite current state."""
    submission = _normalize_submission(payload)
    if not confirmed_by or not isinstance(confirmed_by, str):
        raise ValueError('Confirming user is required')
    request_json = _json(submission)
    observed, differs = _provenance(observed_scores, observed_at, submission['scores'])
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        _lobby_exists(get_db_connection, lobby_id)
        current = _current_row(conn, lobby_id)
        if current is not None:
            original = conn.execute("""SELECT request_json FROM wardogs_result_revisions
                WHERE lobby_id=? AND revision_number=1""", (lobby_id,)).fetchone()
            if original is not None and original['request_json'] == request_json:
                return _public_revision(current, corrected=current['revision_number'] > 1), True
            raise FileExistsError('A confirmed WARDOGS result already exists')
        _insert_revision(conn, revision_id=f'wardogs:{lobby_id}:1', lobby_id=lobby_id,
                         revision_number=1, supersedes_revision_id=None,
                         revision_type='confirmation', submission=submission,
                         actor_id=confirmed_by, timestamp=timestamp, correction_reason=None,
                         observed_scores=observed, observed_at=observed_at,
                         differs=differs, request_json=request_json)
        row = _current_row(conn, lobby_id)
        return _public_revision(row), False


def correct_wardogs_result(get_db_connection, lobby_id, revised_by, payload,
                           *, expected_revision_id, correction_reason,
                           observed_scores=None, observed_at=None, now=None):
    """Append a correction only if the submitted base revision is still current."""
    submission = _normalize_submission(payload)
    if not revised_by or not isinstance(revised_by, str):
        raise ValueError('Revising admin is required')
    if not isinstance(correction_reason, str) or not correction_reason.strip() or len(correction_reason.strip()) > 1000:
        raise ValueError('A correction reason of 1000 characters or fewer is required')
    if not isinstance(expected_revision_id, str) or not expected_revision_id:
        raise ValueError('Expected current revision is required')
    correction_reason = correction_reason.strip()
    request_json = _json({'expectedRevisionId': expected_revision_id,
                          'result': submission, 'correctionReason': correction_reason})
    observed, differs = _provenance(observed_scores, observed_at, submission['scores'])
    timestamp = (now or datetime.now(timezone.utc)).isoformat()
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        current = _current_row(conn, lobby_id)
        if current is None:
            raise LookupError('No confirmed WARDOGS result exists')
        if current['revision_id'] != expected_revision_id:
            duplicate = conn.execute("""SELECT revision_id FROM wardogs_result_revisions
                WHERE lobby_id=? AND request_json=?""", (lobby_id, request_json)).fetchone()
            if duplicate is not None:
                return _public_revision(current, corrected=current['revision_number'] > 1), True
            raise StaleWardogsRevisionError('The authoritative result changed. Reload history before correcting it.')
        duplicate = conn.execute("""SELECT revision_id FROM wardogs_result_revisions
            WHERE lobby_id=? AND request_json=?""", (lobby_id, request_json)).fetchone()
        if duplicate is not None:
            return _public_revision(current, corrected=current['revision_number'] > 1), True
        _insert_revision(conn, revision_id=f'wardogs:{lobby_id}:{current["revision_number"] + 1}',
                         lobby_id=lobby_id, revision_number=current['revision_number'] + 1,
                         supersedes_revision_id=current['revision_id'], revision_type='correction',
                         submission=submission, actor_id=revised_by, timestamp=timestamp,
                         correction_reason=correction_reason, observed_scores=observed,
                         observed_at=observed_at, differs=differs, request_json=request_json)
        row = _current_row(conn, lobby_id)
        return _public_revision(row, corrected=True), False
