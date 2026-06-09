export const createDefaultMatchAcceptState = () => ({
  active: false,
  cancelled: false,
  cancelReason: '',
  queueMode: null,
  players: [],
  acceptedPlayers: [],
  acceptedCount: 0,
  requiredCount: 0,
  countdown: null,
  hasAccepted: false
})

export const createDefaultQueueModes = () => ({
  skirmish: {
    id: 'skirmish',
    label: 'Skirmish',
    shortLabel: 'Skirmish',
    teamSize: 20,
    maxPlayers: 40,
    playersInQueue: 0,
    queue: [],
    inQueue: false
  },
  hotdrop: {
    id: 'hotdrop',
    label: 'Hotdrop',
    shortLabel: 'Hotdrop',
    teamSize: 30,
    maxPlayers: 60,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  }
})

export const createDefaultQueueState = () => ({
  inQueue: false,
  queueMode: null,
  maxPlayers: 0,
  playersInQueue: 0,
  queueList: [],
  queueModes: createDefaultQueueModes(),
  serverCapacity: 1,
  serverAvailable: true,
  activeLobbyCount: 0,
  activePendingMatchCount: 0,
  openLobbies: [],
  activeLobbies: [],
  loading: false,
  error: null,
  lastSync: null,
  countdown: null,
  matchAccept: createDefaultMatchAcceptState()
})
