"""Durable, explicitly referee-confirmed WARDOGS results."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from services.wardogs_lobby import FACTION_IDS, get_wardogs_lobby


RESULT_STATUSES = {'completed_win', 'tie', 'incomplete', 'void'}


def init_wardogs_result_tables(get_db_connection):
    with get_db_connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS wardogs_results (
            lobby_id TEXT PRIMARY KEY,
            game_type TEXT NOT NULL CHECK (game_type='wardogs'),
            status TEXT NOT NULL,
            scores_json TEXT,
            winner_faction TEXT,
            tied INTEGER NOT NULL DEFAULT 0,
            confirmed_at TEXT NOT NULL,
            confirmed_by TEXT NOT NULL,
            note TEXT,
            observation_available INTEGER NOT NULL,
            observed_at TEXT,
            observed_scores_json TEXT,
            submitted_scores_json TEXT,
            differs_from_observation INTEGER,
            submission_json TEXT NOT NULL
        )""")
        conn.commit()


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


def _decode_scores(value):
    return json.loads(value) if value else None


def _public_result(row):
    if row is None:
        return {'status': 'unconfirmed'}
    return {
        'status': row['status'],
        'scores': _decode_scores(row['scores_json']),
        'winnerFaction': row['winner_faction'],
        'tied': bool(row['tied']),
        'confirmedAt': row['confirmed_at'],
    }


def get_wardogs_result(get_db_connection, lobby_id):
    with get_db_connection() as conn:
        row = conn.execute('SELECT * FROM wardogs_results WHERE lobby_id=?', (lobby_id,)).fetchone()
    return _public_result(row)


def confirm_wardogs_result(get_db_connection, lobby_id, confirmed_by, payload,
                           *, observed_scores=None, observed_at=None, now=None):
    """Insert once; identical retries are idempotent and conflicts are immutable."""
    submission = _normalize_submission(payload)
    if not confirmed_by or not isinstance(confirmed_by, str):
        raise ValueError('Confirming user is required')
    observed = _scores(observed_scores, required=False, observed=True) if observed_scores is not None else None
    if observed is not None and observed_at is None:
        observed = None
    differs = (submission['scores'] != observed
               if submission['scores'] is not None and observed is not None else None)
    submission_json = json.dumps(submission, ensure_ascii=True, sort_keys=True)
    confirmed_at = (now or datetime.now(timezone.utc)).isoformat()
    with get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        lobby = get_wardogs_lobby(get_db_connection, lobby_id)
        if lobby is None:
            raise LookupError('WARDOGS lobby not found')
        existing = conn.execute('SELECT * FROM wardogs_results WHERE lobby_id=?',
                                 (lobby_id,)).fetchone()
        if existing is not None:
            if existing['submission_json'] == submission_json:
                return _public_result(existing), True
            raise FileExistsError('A confirmed WARDOGS result already exists')
        conn.execute("""INSERT INTO wardogs_results (
        lobby_id, game_type, status, scores_json, winner_faction, tied,
            confirmed_at, confirmed_by, note, observation_available, observed_at, observed_scores_json,
            submitted_scores_json, differs_from_observation, submission_json
        ) VALUES (?, 'wardogs', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
            lobby_id, submission['status'],
            json.dumps(submission['scores'], sort_keys=True) if submission['scores'] is not None else None,
            submission['winnerFaction'], int(submission['tied']), confirmed_at,
            confirmed_by, submission['note'], int(observed is not None), observed_at,
            json.dumps(observed, sort_keys=True) if observed is not None else None,
            json.dumps(submission['scores'], sort_keys=True) if submission['scores'] is not None else None,
            None if differs is None else int(differs), submission_json,
        ))
        row = conn.execute('SELECT * FROM wardogs_results WHERE lobby_id=?', (lobby_id,)).fetchone()
        return _public_result(row), False
