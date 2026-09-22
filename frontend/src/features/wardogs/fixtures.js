const roster = {
  valkyra: [
    ['Aster North', true, true, true, 'Alpha'], ['Rook Marlow', true, true, false, 'Alpha'],
    ['Jun Vela', true, true, false, 'Bravo'], ['Hal Mercer', true, true, false, 'Bravo'],
    ['Mira Quill', true, true, false, 'Command']
  ],
  lonestar: [
    ['Kestrel Vale', true, true, true, 'Alpha'], ['Pax Rowan', true, true, false, 'Alpha'],
    ['Nia Sable', true, true, false, 'Bravo'], ['Dane Cross', true, true, false, 'Bravo'],
    ['Ivo Flint', true, true, false, 'Command']
  ],
  manticore: [
    ['Cinder Moss', true, true, true, 'Alpha'], ['Tala Reed', true, true, false, 'Alpha'],
    ['Oren Pike', true, false, false, 'Bravo'], ['Sable Finch', false, false, false, 'Bravo'],
    ['Venn Ash', true, true, false, 'Command']
  ]
};

const factions = [
  { id: 'valkyra', name: 'Valkyra', color: '#8b5568' },
  { id: 'lonestar', name: 'Lonestar', color: '#4b7186' },
  { id: 'manticore', name: 'Manticore', color: '#62754e' }
];

const makePlayers = (state) => factions.map((faction) => ({
  ...faction,
  players: roster[faction.id].map(([name, connected, ready, captain, group], index) => ({
    id: `${faction.id}-${index}`,
    name,
    connected: state === 'ready' ? true : connected,
    ready: state === 'ready' ? true : ready,
    captain,
    group
  }))
}));

export const wardogsFixtures = {
  lobby: {
    state: 'lobby', label: 'Pre-match lobby', server: 'Awaiting server confirmation', map: 'Ashfall Basin',
    config: 'Competitive draft · prototype fields', factions: makePlayers('lobby')
  },
  partial: {
    state: 'partial', label: 'Partially connected', server: 'Demo server reachable', map: 'Ashfall Basin',
    config: 'Experience: Conquest · Lighting: Dusk · Zone: Alternator A', factions: makePlayers('partial')
  },
  ready: {
    state: 'ready', label: 'All-ready check', server: 'Demo server ready', map: 'Ashfall Basin',
    config: 'Experience: Conquest · Lighting: Dusk · Zone: Alternator A', factions: makePlayers('ready')
  },
  live: {
    state: 'live', label: 'Live match — demo observation', server: 'Server status: observed snapshot', map: 'Ashfall Basin',
    config: 'Conquest · Dusk · Alternator A', factions: makePlayers('ready'),
    scores: { valkyra: 482, lonestar: 451, manticore: 438 },
    events: ['Valkyra control point observed', 'Roster snapshot refreshed', 'Lonestar score changed +12', 'Manticore player connected']
  },
  results: {
    state: 'results', label: 'Results — presentation only', server: 'Completion source not established', map: 'Ashfall Basin',
    config: 'Conquest · Dusk · Alternator A', factions: makePlayers('ready'),
    scores: { valkyra: 620, lonestar: 592, manticore: 556 },
    stats: { valkyra: ['Aster North', 18, 7, 9], lonestar: ['Kestrel Vale', 15, 8, 11], manticore: ['Cinder Moss', 13, 10, 7] }
  }
};

export const fixtureOptions = ['lobby', 'partial', 'ready', 'live', 'results'];
