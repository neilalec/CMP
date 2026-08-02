export const createDefaultLobbyState = () => ({
  lobbyId: null,
  players: [],
  playerProfiles: {},
  playerStatuses: {},
  selectedMap: null,
  queueMode: null,
  queueLabel: null,
  matchSizeLabel: null,
  maxPlayers: null,
  teams: {
    team1: [],
    team2: []
  },
  teamLabels: {},
  captains: {
    team1: null,
    team2: null
  },
  serverDetails: null,
  step: 2,
  loading: false,
  error: null,
  countdown: null,
  mapVotes: {},
  votingCountdown: null,
  voteCounts: {},
  mapPool: [],
  playerGroups: {},
  serverPresence: {},
  serverPresenceAvailable: true,
  serverPresenceError: null,
  serverDetailsProvidedAt: null,
  liveStartedAt: null,
  liveMatchMaxSeconds: null,
  liveRollReadyAt: null,
  liveRollCountdown: null,
  announcement: null
})
