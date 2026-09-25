"""Resolve the authenticated user's current game and lobby for navigation."""


def resolve_current_match_location(username, find_active_squad_lobby, get_current_wardogs_match):
    if not username:
        return None

    squad_lobby_id = find_active_squad_lobby(username)
    wardogs_match = get_current_wardogs_match(username)

    # Cross-game exclusivity is not enforced in current domain state. Preserve
    # the durable participant match as the recovery choice when both exist.
    if wardogs_match and wardogs_match.get('lobbyId'):
        return {'gameType': 'wardogs', 'lobbyId': wardogs_match['lobbyId']}
    if squad_lobby_id:
        return {'gameType': 'squad', 'lobbyId': squad_lobby_id}
    return None
