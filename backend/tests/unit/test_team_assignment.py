from types import SimpleNamespace

import matchmaking


def _install_groups(monkeypatch, group_sizes):
    players = [f'player_{index}' for index in range(sum(group_sizes))]
    groups = {}
    user_to_group = {}
    cursor = 0
    for group_index, size in enumerate(group_sizes):
        members = players[cursor:cursor + size]
        cursor += size
        code = f'group_{group_index}'
        groups[code] = {'members': members}
        user_to_group.update({player: code for player in members})
    monkeypatch.setattr(matchmaking, '_app', lambda: SimpleNamespace(
        user_to_group=user_to_group,
        groups=groups
    ))
    monkeypatch.setattr(matchmaking.random, 'shuffle', lambda items: None)
    return players, groups


def test_assign_teams_splits_minimally_when_premades_cannot_fit(monkeypatch):
    players, _groups = _install_groups(monkeypatch, [4, 3, 3])

    teams = matchmaking.assign_teams(players)

    assert len(teams['team1']) == 5
    assert len(teams['team2']) == 5
    assert sorted(teams['team1'] + teams['team2']) == sorted(players)
    assert matchmaking.team_assignment_matches_queue_format(
        teams, {'team_size': 5}
    )


def test_assign_teams_keeps_premades_intact_when_exact_partition_exists(monkeypatch):
    players, groups = _install_groups(monkeypatch, [3, 2, 3, 2])

    teams = matchmaking.assign_teams(players)

    assert len(teams['team1']) == len(teams['team2']) == 5
    for group in groups.values():
        members = set(group['members'])
        assert members.issubset(set(teams['team1'])) or members.issubset(set(teams['team2']))
