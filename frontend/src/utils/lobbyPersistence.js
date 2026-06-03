const CURRENT_LOBBY_KEY = 'currentLobby';
const CURRENT_LOBBY_CAPTAINS_KEY = 'currentLobbyCaptains';

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
  localStorage.removeItem(CURRENT_LOBBY_CAPTAINS_KEY);
}

export function getCurrentLobbyCaptains() {
  try {
    const saved = localStorage.getItem(CURRENT_LOBBY_CAPTAINS_KEY);
    return saved ? JSON.parse(saved) : null;
  } catch (error) {
    return null;
  }
}

export function setCurrentLobbyCaptains(captains) {
  if (captains) {
    localStorage.setItem(CURRENT_LOBBY_CAPTAINS_KEY, JSON.stringify(captains));
  } else {
    localStorage.removeItem(CURRENT_LOBBY_CAPTAINS_KEY);
  }
}

export function isLobbyRoute(path) {
  return typeof path === 'string' && path.startsWith('/lobby/');
}
