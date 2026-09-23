import { API_BASE_URL } from '../../../config';
import { FACTION_IDS } from '../models/match';

// Keep the transport and validation at the data-source boundary. Components
// receive the same Match → Factions → Groups → Players shape as mock mode.
export const normalizeBackendMatch = (payload) => {
  const match = payload?.match;
  if (!payload?.success || !match || !Array.isArray(match.factions) ||
      match.factions.length !== 3 ||
      !FACTION_IDS.every((id) => match.factions.some((faction) => faction.id === id))) {
    throw new Error('Invalid WARDOGS lobby response');
  }
  return {
    id: match.id,
    source: 'cmp-backend',
    phase: match.phase,
    label: match.label,
    server: match.server || { state: 'none', label: 'No server observation yet' },
    observation: match.observation || { state: 'none', observedAt: null },
    configuration: match.configuration || {},
    serverStatus: match.serverStatus || null,
    factions: FACTION_IDS.map((id) => {
      const faction = match.factions.find((item) => item.id === id);
      return {
        id, name: faction.name, color: faction.color,
        commanderId: faction.commanderId ?? null,
        summary: faction.summary || null,
        groups: (faction.groups || []).map((group) => ({
          id: group.id, name: group.name, type: group.type,
          leaderId: group.leaderId ?? null,
          plannedFactionId: id,
          players: (group.players || []).map((player) => ({
            id: player.id, displayName: player.displayName,
            steamId: player.steamId ?? null, groupId: group.id,
            rosterStatus: player.rosterStatus, registered: player.registered,
            ready: player.ready, connected: player.connected,
            plannedFactionId: id,
            observedFactionId: player.observedFactionId ?? null,
            observedFactionName: player.observedFactionName ?? null,
            alignmentState: player.alignmentState || 'unknown',
            isLeader: player.isLeader === true,
            stats: { kills: null, deaths: null, assists: null }
          }))
        }))
      };
    }),
    scores: Object.fromEntries(FACTION_IDS.map((id) => [id, match.scores?.[id] ?? null])),
    result: { status: 'unconfirmed', note: 'No authoritative result is available.' },
    observations: match.observations || [],
    unexpectedPlayers: match.unexpectedPlayers || []
  };
};

export const createBackendWardogsDataSource = ({
  fetchImpl = fetch, apiBaseUrl = API_BASE_URL, getToken = () => null
} = {}) => ({
  async loadMatch(lobbyId) {
    if (!lobbyId) throw new Error('WARDOGS lobby ID is required');
    const token = getToken();
    if (!token) throw new Error('Sign in to view this WARDOGS lobby');
    const response = await fetchImpl(`${apiBaseUrl}/wardogs/lobbies/${encodeURIComponent(lobbyId)}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!response.ok) throw new Error(`WARDOGS lobby unavailable (${response.status})`);
    return normalizeBackendMatch(await response.json());
  }
});
