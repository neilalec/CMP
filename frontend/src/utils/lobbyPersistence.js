const CURRENT_LOBBY_KEY = 'currentLobby';

export function getCurrentLobbyId() {
  return localStorage.getItem(CURRENT_LOBBY_KEY);
}

export function setCurrentLobbyId(lobbyId) {
  if (lobbyId) {
    localStorage.setItem(CURRENT_LOBBY_KEY, lobbyId);
  } else {
    localStorage.removeItem(CURRENT_LOBBY_KEY);
  }
}

export function clearCurrentLobby() {
  localStorage.removeItem(CURRENT_LOBBY_KEY);
  localStorage.removeItem('currentLobbyCaptains');
}

export function isLobbyRoute(path) {
  return typeof path === 'string' && path.startsWith('/lobby/');
}
