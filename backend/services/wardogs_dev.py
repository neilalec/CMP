"""Local-only WARDOGS test identities and read-model decoration.

No synthetic observation is written to the server cache or planned roster.
"""

from services.queue import find_user_queue_mode

MODE = 'wardogs_beta9'
PREFIX = '__dev_wardogs_'
SYNTHETIC_IDS = tuple(f'{PREFIX}{index:02d}__' for index in range(1, 10))
SYNTHETIC_STEAM_IDS = {
    name: str(76561199990000000 + index)
    for index, name in enumerate(SYNTHETIC_IDS, 1)
}
_simulated_lobbies = set()


def is_synthetic(username):
    return username in SYNTHETIC_STEAM_IDS


def is_synthetic_record(username, record):
    return (is_synthetic(username) and isinstance(record, dict)
            and record.get('seeded_player') is True
            and record.get('steam_id') == SYNTHETIC_STEAM_IDS[username])


def fill_queue(*, enabled, username, users, matchmaking_queue, queue_lock,
               upsert_player_activity, save_users, save_queue,
               check_queue_and_start_countdown, pending_match, broadcast_queue_update):
    if not enabled:
        raise PermissionError('WARDOGS test tools are disabled')
    if username not in users:
        raise ValueError('Join with a real account first')
    if find_user_queue_mode(matchmaking_queue, username) != MODE:
        raise ValueError('Join the WARDOGS beta queue before filling it')
    if pending_match.get(MODE):
        raise ValueError('A WARDOGS match is already awaiting acceptance')
    added = []
    with queue_lock:
        queue = matchmaking_queue[MODE]
        for name in SYNTHETIC_IDS:
            if len(queue) >= 9:
                break
            if name in queue:
                continue
            if name in users and not is_synthetic_record(name, users[name]):
                raise ValueError('Reserved test identity collides with a real account')
            if name not in users:
                users[name] = {
                    'steam_id': SYNTHETIC_STEAM_IDS[name],
                    'display_name': f'WARDOGS Test {len(added) + 1}',
                    'seeded_player': True,
                    'wardogs_dev_synthetic': True,
                }
            queue.append(name)
            upsert_player_activity(name, status='queued')
            added.append(name)
        if added:
            save_users()
            save_queue()
    check_queue_and_start_countdown()
    broadcast_queue_update()
    return added


def autoaccept_synthetic(pending, *, enabled, users):
    if not enabled or not pending or pending.get('game_type') != 'wardogs' or pending.get('queue_mode') != MODE:
        return ()
    accepted = []
    for username in pending.get('players', ()):
        if (is_synthetic_record(username, users.get(username))
                and username in pending.get('accepted', {})):
            pending['accepted'][username] = True
            accepted.append(username)
    return tuple(accepted)


def set_simulated(lobby, enabled, *, dev_mode):
    if not dev_mode:
        raise PermissionError('WARDOGS test tools are disabled')
    if not any(is_synthetic(player['id']) for faction in lobby['factions']
               for group in faction['groups'] for player in group['players']):
        raise ValueError('This lobby has no WARDOGS test participants')
    if enabled:
        _simulated_lobbies.add(lobby['id'])
    else:
        _simulated_lobbies.discard(lobby['id'])


def decorate_read_model(lobby, model, *, dev_mode):
    if not dev_mode:
        return model
    simulated = lobby['id'] in _simulated_lobbies
    for faction in model['factions']:
        summary = faction['summary']
        for group in faction['groups']:
            for player in group['players']:
                if not is_synthetic(player['id']):
                    continue
                player['devSynthetic'] = True
                if not simulated:
                    continue
                player['devSimulated'] = True
                player['connected'] = True
                player['observedFactionId'] = faction['id']
                player['observedFactionName'] = faction['name']
                player['alignmentState'] = 'aligned'
        if simulated:
            active = [player for group in faction['groups'] for player in group['players']
                      if player['rosterStatus'] == 'active']
            summary['connected'] = sum(player['connected'] is True for player in active)
            summary['aligned'] = sum(player['alignmentState'] == 'aligned' for player in active)
            summary['mismatched'] = sum(player['alignmentState'] == 'mismatch' for player in active)
            summary['devSimulated'] = True
    if simulated:
        model['devSimulation'] = {'enabled': True, 'label': 'Synthetic participants simulated; real WDRCON observations remain separate'}
    return model


def clear_simulation(lobby_id=None):
    if lobby_id is None:
        _simulated_lobbies.clear()
    else:
        _simulated_lobbies.discard(lobby_id)
