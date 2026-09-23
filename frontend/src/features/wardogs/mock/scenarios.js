const names = {
  valkyra: ['Aster North', 'Rook Marlow', 'Jun Vela', 'Hal Mercer', 'Mira Quill', 'Risa Penn', 'Tern Cole', 'Ada Flint', 'Bex Hale', 'Niko Ward'],
  lonestar: ['Kestrel Vale', 'Pax Rowan', 'Nia Sable', 'Dane Cross', 'Ivo Flint', 'Tess Bloom', 'Cai Wells', 'Milo Beck', 'Eris Lane', 'Quin Oak'],
  manticore: ['Cinder Moss', 'Tala Reed', 'Oren Pike', 'Sable Finch', 'Venn Ash', 'Joss Gray', 'Lio Birch', 'Remy Stone', 'Fenn Lake', 'Kira West']
};

const definitions = [
  { id: 'valkyra', name: 'Valkyra', color: '#8b5568' },
  { id: 'lonestar', name: 'Lonestar', color: '#4b7186' },
  { id: 'manticore', name: 'Manticore', color: '#62754e' }
];

const player = (factionId, index, overrides = {}) => ({
  id: `${factionId}-p${index}`,
  displayName: names[factionId][index] || `${factionId} player ${index + 1}`,
  registered: true,
  steamId: index !== 9 ? `mock-steam-${factionId}-${index}` : null,
  connected: true,
  observedFactionId: factionId,
  ready: true,
  rosterStatus: 'active',
  stats: { kills: Math.max(0, 14 - index), deaths: 5 + index, assists: 3 + index },
  ...overrides
});

const group = (factionId, id, name, type, indices, options = {}) => ({
  id: `${factionId}-${id}`,
  name,
  type,
  leaderId: options.leaderIndex == null ? null : `${factionId}-p${options.leaderIndex}`,
  players: indices.map((index) => player(factionId, index))
});

const baseFaction = (definition) => {
  const id = definition.id;
  return {
    ...definition,
    mockCapacity: 30,
    commanderId: id === 'valkyra' ? `${id}-p0` : null,
    groups: [
      group(id, 'clan', 'Northwatch detachment', 'clan', [0, 1, 2, 3], { leaderIndex: 0 }),
      group(id, 'squad', 'Squad Bravo', 'squad', [4, 5, 6], { leaderIndex: 4 }),
      group(id, 'solo-a', 'Solo fill', 'solo', [7]),
      group(id, 'solo-b', 'Solo fill', 'solo', [8])
    ]
  };
};

const base = () => ({
  id: 'mock-match',
  source: 'local-mock',
  phase: 'assembling',
  label: 'Assembling',
  server: { state: 'unconfirmed', label: 'Server confirmation pending' },
  configuration: { map: 'Ashfall Basin', experience: 'Conquest', lighting: 'Dusk', zoneAlternator: 'Alternator A' },
  factions: definitions.map(baseFaction),
  scores: { valkyra: null, lonestar: null, manticore: null },
  result: { status: 'unconfirmed', note: 'No authoritative result is available.' },
  observations: []
});

const updatePlayer = (match, factionId, index, updates) => {
  const faction = match.factions.find((entry) => entry.id === factionId);
  const target = faction.groups.flatMap((entry) => entry.players).find((entry) => entry.id === `${factionId}-p${index}`);
  Object.assign(target, updates);
};

const scenario = (key, mutate) => {
  const match = base();
  mutate(match);
  return { key, label: match.label, match };
};

export const scenarios = [
  scenario('assembling', (match) => {
    for (const faction of match.factions) {
      updatePlayer(match, faction.id, 7, { connected: false, observedFactionId: null, ready: false });
      updatePlayer(match, faction.id, 8, { connected: false, observedFactionId: null, ready: false });
    }
  }),
  scenario('partial', (match) => {
    match.label = 'Partially connected';
    match.server = { state: 'observed', label: 'Demo server reachable' };
    updatePlayer(match, 'manticore', 7, { connected: false, observedFactionId: null, ready: false });
    updatePlayer(match, 'lonestar', 8, { ready: false });
  }),
  scenario('ready', (match) => {
    match.label = 'All ready';
    match.server = { state: 'observed', label: 'Demo server reachable' };
  }),
  scenario('reserves', (match) => {
    match.label = 'Active roster and reserves';
    const faction = match.factions[0];
    faction.groups.push(group('valkyra', 'reserve', 'Reserve pool', 'squad', [9], { leaderIndex: 9 }));
    updatePlayer(match, 'valkyra', 9, { registered: false, rosterStatus: 'reserve', connected: false, observedFactionId: null, ready: false });
    updatePlayer(match, 'valkyra', 8, { rosterStatus: 'reserve', connected: false, observedFactionId: null, ready: false });
  }),
  scenario('disconnected', (match) => {
    match.label = 'Disconnected player';
    updatePlayer(match, 'lonestar', 2, { connected: false, observedFactionId: null, ready: true });
  }),
  scenario('imbalanced', (match) => {
    match.label = 'Incomplete faction';
    match.factions[2].groups.splice(2);
    updatePlayer(match, 'manticore', 3, { connected: false, observedFactionId: null, ready: false });
  }),
  scenario('largeRoster', (match) => {
    match.label = 'Thirty-player faction';
    const faction = match.factions[0];
    faction.groups.push(group('valkyra', 'detachment', 'Second clan detachment', 'clan', [9, 10, 11, 12, 13, 14, 15, 16], { leaderIndex: 9 }));
    faction.groups.push(group('valkyra', 'charlie', 'Squad Charlie', 'squad', [17, 18, 19, 20, 21, 22, 23, 24], { leaderIndex: 17 }));
    faction.groups.push(group('valkyra', 'delta', 'Squad Delta', 'squad', [25, 26, 27, 28, 29], { leaderIndex: 25 }));
  }),
  scenario('live', (match) => {
    match.phase = 'live'; match.label = 'Live observation';
    match.server = { state: 'observed', label: 'Observed snapshot · phase unverified' };
    match.scores = { valkyra: 482, lonestar: 451, manticore: null };
    match.observations = ['Roster snapshot refreshed', 'Valkyra score changed', 'Manticore score unavailable'];
  }),
  scenario('tie', (match) => {
    match.phase = 'results'; match.label = 'Tied mock result';
    match.scores = { valkyra: 620, lonestar: 620, manticore: 556 };
    match.result = { status: 'confirmed-demo', note: 'Manual demo confirmation only; tie policy is unresolved.' };
  }),
  scenario('incompleteResult', (match) => {
    match.phase = 'results'; match.label = 'Unconfirmed result';
    match.scores = { valkyra: 620, lonestar: null, manticore: 556 };
    match.result = { status: 'unconfirmed', note: 'A faction score is missing; ranking is withheld.' };
  }),
  scenario('completed', (match) => {
    match.phase = 'results'; match.label = 'Completed mock result';
    match.scores = { valkyra: 620, lonestar: 592, manticore: 556 };
    match.result = { status: 'confirmed-demo', note: 'Manually confirmed in this mock only; no WDRCON completion signal is implied.' };
  })
];

export const scenarioOptions = scenarios.map(({ key, label }) => ({ key, label }));
