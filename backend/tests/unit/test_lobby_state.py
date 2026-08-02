from types import SimpleNamespace

from state import lobby as lobby_state


def test_finalized_lobbies_are_not_listed_as_open_or_active(monkeypatch):
    monkeypatch.setattr(
        lobby_state,
        '_app',
        lambda: SimpleNamespace(
            MAX_LOBBY_PLAYERS=4,
            lobbies={
                'open': {
                    'players': ['alice'],
                    'max_players': 4,
                    'step': 2,
                },
                'finalized_with_slot': {
                    'players': ['bob'],
                    'max_players': 4,
                    'step': 5,
                },
                'finalized_full': {
                    'players': ['p1', 'p2', 'p3', 'p4'],
                    'max_players': 4,
                    'step': 5,
                },
            },
        )
    )

    assert [lobby['lobby_id'] for lobby in lobby_state.get_open_lobbies()] == ['open']
    assert lobby_state.get_active_lobbies() == []
