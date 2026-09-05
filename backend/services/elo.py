import json
import math
import time


DEFAULT_ELO_RATING = 1000
PROVISIONAL_ELO_MATCHES = 10
PROVISIONAL_ELO_K = 40
STANDARD_ELO_K = 32
DEV_SOLO_ELO_SYNTHETIC_OPPONENT = '__dev_solo_elo_opponent__'


def init_elo_tables(get_db_connection):
    with get_db_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS elo_match_updates (
                lobby_id TEXT PRIMARY KEY,
                applied_at REAL NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}'
            )
        """)
        conn.commit()


def get_elo_rating(record):
    try:
        rating = int(record.get('elo_rating', DEFAULT_ELO_RATING))
    except (AttributeError, TypeError, ValueError):
        return DEFAULT_ELO_RATING
    return max(0, rating)


def get_elo_matches(record):
    try:
        matches = int(record.get('elo_matches', 0))
    except (AttributeError, TypeError, ValueError):
        return 0
    return max(0, matches)


def get_elo_k_factor(record):
    return PROVISIONAL_ELO_K if get_elo_matches(record) < PROVISIONAL_ELO_MATCHES else STANDARD_ELO_K


def normalize_elo_record(record):
    normalized = dict(record or {})
    normalized['elo_rating'] = get_elo_rating(normalized)
    normalized['elo_matches'] = get_elo_matches(normalized)
    return normalized


def _expected_score(team_rating, opponent_rating):
    return 1 / (1 + math.pow(10, (opponent_rating - team_rating) / 400))


def _mean_rating(players, users):
    if not players:
        return DEFAULT_ELO_RATING
    ratings = [get_elo_rating(users.get(player) or {}) for player in players]
    return sum(ratings) / len(ratings)


def _round_delta(value):
    if value >= 0:
        return int(value + 0.5)
    return int(value - 0.5)


def _team_key_from_round_side(round_side):
    if not isinstance(round_side, dict):
        return None
    raw_team = str(round_side.get('team') or '').strip().lower().replace(' ', '')
    if raw_team in {'1', 'team1', 'one', 'teamone'}:
        return 'team1'
    if raw_team in {'2', 'team2', 'two', 'teamtwo'}:
        return 'team2'
    return None


def _resolve_scores(round_result):
    if not isinstance(round_result, dict) or round_result.get('partial'):
        return None
    if round_result.get('draw'):
        return {'team1': 0.5, 'team2': 0.5, 'result': 'draw'}

    winner_team = _team_key_from_round_side(round_result.get('winner'))
    if winner_team == 'team1':
        return {'team1': 1.0, 'team2': 0.0, 'result': 'team1_win'}
    if winner_team == 'team2':
        return {'team1': 0.0, 'team2': 1.0, 'result': 'team2_win'}
    return None


def _team_for_player(teams, username):
    normalized_username = str(username or '').strip().lower()
    if not normalized_username:
        return None
    for team_key in ('team1', 'team2'):
        players = [
            str(player or '').strip().lower()
            for player in (teams.get(team_key) or [])
        ]
        if normalized_username in players:
            return team_key
    return None


def build_dev_solo_elo_smoke_lobby(
    lobby,
    *,
    enabled=False,
    username='',
    synthetic_opponent=DEV_SOLO_ELO_SYNTHETIC_OPPONENT
):
    if not enabled or not isinstance(lobby, dict):
        return lobby

    normalized_username = str(username or '').strip().lower()
    teams = lobby.get('teams') if isinstance(lobby.get('teams'), dict) else {}
    team1_players = [player for player in (teams.get('team1') or []) if player]
    team2_players = [player for player in (teams.get('team2') or []) if player]
    players = [player for player in (lobby.get('players') or []) if player]
    if len(players) != 1 or str(players[0]).strip().lower() != normalized_username:
        return lobby
    if team1_players and team2_players:
        return lobby

    solo_team = _team_for_player(teams, normalized_username)
    if solo_team not in {'team1', 'team2'}:
        return lobby

    round_result = lobby.get('round_result') if isinstance(lobby.get('round_result'), dict) else {}
    scores = _resolve_scores(round_result)
    if not scores or scores.get('result') == 'draw':
        return lobby

    winning_team = scores['result'].replace('_win', '')
    if winning_team == solo_team:
        return lobby

    opponent_team = 'team2' if solo_team == 'team1' else 'team1'
    adjusted_teams = {
        **teams,
        solo_team: list(teams.get(solo_team) or []),
        opponent_team: list(teams.get(opponent_team) or [])
    }
    if adjusted_teams[opponent_team]:
        return lobby

    adjusted_teams[opponent_team].append(synthetic_opponent)
    return {
        **lobby,
        'teams': adjusted_teams,
        'dev_solo_elo_smoke': {
            'enabled': True,
            'username': normalized_username,
            'syntheticOpponent': synthetic_opponent,
            'soloTeam': solo_team,
            'opponentTeam': opponent_team,
            'result': scores['result'],
        }
    }


def build_elo_update_payload(lobby, users):
    teams = lobby.get('teams') if isinstance(lobby, dict) else {}
    if not isinstance(teams, dict):
        return None

    team1_players = [player for player in (teams.get('team1') or []) if player]
    team2_players = [player for player in (teams.get('team2') or []) if player]
    if not team1_players or not team2_players:
        return None

    scores = _resolve_scores(lobby.get('round_result') or {})
    if not scores:
        return None

    team_ratings = {
        'team1': _mean_rating(team1_players, users),
        'team2': _mean_rating(team2_players, users),
    }
    expected_scores = {
        'team1': _expected_score(team_ratings['team1'], team_ratings['team2']),
        'team2': _expected_score(team_ratings['team2'], team_ratings['team1']),
    }

    updates = []
    for team_key, players in (('team1', team1_players), ('team2', team2_players)):
        for username in players:
            record = users.get(username)
            if record is None:
                continue
            old_rating = get_elo_rating(record)
            old_matches = get_elo_matches(record)
            k_factor = get_elo_k_factor(record)
            delta = _round_delta(k_factor * (scores[team_key] - expected_scores[team_key]))
            updates.append({
                'username': username,
                'team': team_key,
                'oldRating': old_rating,
                'newRating': max(0, old_rating + delta),
                'delta': max(0, old_rating + delta) - old_rating,
                'oldMatches': old_matches,
                'newMatches': old_matches + 1,
                'kFactor': k_factor,
            })

    if not updates:
        return None

    payload = {
        'result': scores['result'],
        'teamRatings': {
            'team1': round(team_ratings['team1'], 2),
            'team2': round(team_ratings['team2'], 2),
        },
        'expectedScores': {
            'team1': round(expected_scores['team1'], 4),
            'team2': round(expected_scores['team2'], 4),
        },
        'updates': updates,
    }
    if lobby.get('dev_solo_elo_smoke'):
        payload['devSoloEloSmoke'] = lobby.get('dev_solo_elo_smoke')
    return payload


def apply_elo_for_completed_match(
    get_db_connection,
    lobby_id,
    lobby,
    users,
    save_users,
    *,
    applied_at=None,
    dev_solo_smoke_enabled=False,
    dev_solo_smoke_username=''
):
    lobby_id = str(lobby_id or '').strip()
    if not lobby_id:
        return None

    with get_db_connection() as conn:
        existing = conn.execute(
            'SELECT lobby_id FROM elo_match_updates WHERE lobby_id = ?',
            (lobby_id,)
        ).fetchone()
    if existing:
        return None

    elo_lobby = build_dev_solo_elo_smoke_lobby(
        lobby,
        enabled=dev_solo_smoke_enabled,
        username=dev_solo_smoke_username
    )
    payload = build_elo_update_payload(elo_lobby, users)
    if not payload:
        return None

    for update in payload['updates']:
        username = update['username']
        record = normalize_elo_record(users.get(username) or {})
        record['elo_rating'] = update['newRating']
        record['elo_matches'] = update['newMatches']
        users[username] = record

    save_users()

    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO elo_match_updates (lobby_id, applied_at, payload_json)
            VALUES (?, ?, ?)
            """,
            (
                lobby_id,
                applied_at if applied_at is not None else time.time(),
                json.dumps(payload, ensure_ascii=True, sort_keys=True)
            )
        )
        conn.commit()

    return payload
