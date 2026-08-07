export const createDefaultMatchAcceptState = () => ({
  active: false,
  cancelled: false,
  cancelReason: '',
  queueMode: null,
  players: [],
  playerProfiles: {},
  acceptedPlayers: [],
  acceptedCount: 0,
  requiredCount: 0,
  countdown: null,
  hasAccepted: false
})

export const createDefaultQueueModes = () => ({
  skirmish: {
    id: 'skirmish',
    label: '20v20 Skirmish Layers',
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
  },
  sec26: {
    id: 'sec26',
    label: '26v26 Squad Esports Cup',
    shortLabel: 'SEC 26',
    teamSize: 26,
    maxPlayers: 52,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  sec36: {
    id: 'sec36',
    label: '36v36 Squad Esports Cup',
    shortLabel: 'SEC 36',
    teamSize: 36,
    maxPlayers: 72,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  sec46: {
    id: 'sec46',
    label: '46v46 Squad Esports Cup',
    shortLabel: 'SEC 46',
    teamSize: 46,
    maxPlayers: 92,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  s30: {
    id: 's30',
    label: '36v36 S3O Layers',
    shortLabel: 'S3O',
    teamSize: 36,
    maxPlayers: 72,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  rivals36: {
    id: 'rivals36',
    label: '36v36 Squad Rivals',
    shortLabel: 'Rivals',
    teamSize: 36,
    maxPlayers: 72,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  osi40: {
    id: 'osi40',
    label: '40v40 Offworld Squad Invitational',
    shortLabel: 'OSI',
    teamSize: 40,
    maxPlayers: 80,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  ocbt15: {
    id: 'ocbt15',
    label: '10v10 Open Clan Battle',
    shortLabel: 'OCBT',
    teamSize: 10,
    maxPlayers: 20,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  ocbt5: {
    id: 'ocbt5',
    label: '5v5 Open Clan Battle',
    shortLabel: 'OCBT 5v5',
    teamSize: 5,
    maxPlayers: 10,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  ocbt1: {
    id: 'ocbt1',
    label: '1v1 Open Clan Battle',
    shortLabel: 'OCBT 1v1',
    teamSize: 1,
    maxPlayers: 2,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  balt26: {
    id: 'balt26',
    label: '26v26 Balt Layers',
    shortLabel: 'BALT',
    teamSize: 26,
    maxPlayers: 52,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  outofthebox40: {
    id: 'outofthebox40',
    label: '30v30 Out of The Box Layers',
    shortLabel: 'OOTB',
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
  serverAvailabilityReason: 'available',
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
