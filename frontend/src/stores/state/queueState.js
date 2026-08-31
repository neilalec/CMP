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
  hasAccepted: false,
  finalizingLobby: false
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
  s3osmall1: {
    id: 's3osmall1',
    label: '1v1 S3O Small Format',
    shortLabel: 'S3O 1v1',
    teamSize: 1,
    maxPlayers: 2,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  s3osmall2: {
    id: 's3osmall2',
    label: '2v2 S3O Small Format',
    shortLabel: 'S3O 2v2',
    teamSize: 2,
    maxPlayers: 4,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  s3osmall3: {
    id: 's3osmall3',
    label: '3v3 S3O Small Format',
    shortLabel: 'S3O 3v3',
    teamSize: 3,
    maxPlayers: 6,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  s3osmall4: {
    id: 's3osmall4',
    label: '4v4 S3O Small Format',
    shortLabel: 'S3O 4v4',
    teamSize: 4,
    maxPlayers: 8,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  s3osmall5: {
    id: 's3osmall5',
    label: '5v5 S3O Layers',
    shortLabel: 'S3O 5v5',
    teamSize: 5,
    maxPlayers: 10,
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
  outofthebox10: {
    id: 'outofthebox10',
    label: '10v10 Out of The Box Layers',
    shortLabel: 'OOTB 10v10',
    teamSize: 10,
    maxPlayers: 20,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  outofthebox15: {
    id: 'outofthebox15',
    label: '15v15 Out of The Box Layers',
    shortLabel: 'OOTB 15v15',
    teamSize: 15,
    maxPlayers: 30,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  outofthebox20: {
    id: 'outofthebox20',
    label: '20v20 Out of The Box Layers',
    shortLabel: 'OOTB 20v20',
    teamSize: 20,
    maxPlayers: 40,
    queue: [],
    playersInQueue: 0,
    inQueue: false
  },
  outofthebox40: {
    id: 'outofthebox40',
    label: '30v30 Out of The Box Layers',
    shortLabel: 'OOTB 30v30',
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
