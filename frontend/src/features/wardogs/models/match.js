export const FACTION_IDS = ['valkyra', 'lonestar', 'manticore'];

export const activePlayers = (faction) => faction.groups.flatMap((group) =>
  group.players.filter((player) => player.rosterStatus === 'active')
);

export const reservePlayers = (faction) => faction.groups.flatMap((group) =>
  group.players.filter((player) => player.rosterStatus === 'reserve')
);

export const factionSummary = (faction) => {
  const active = activePlayers(faction);
  return {
    active: active.length,
    reserves: reservePlayers(faction).length,
    connected: active.filter((player) => player.connected).length,
    ready: active.filter((player) => player.ready).length,
    missing: active.filter((player) => !player.connected).length,
    aligned: active.filter((player) => player.connected && player.observedFactionId === faction.id).length
  };
};

export const matchSummary = (match) => match.factions.reduce((totals, faction) => {
  const summary = factionSummary(faction);
  for (const key of Object.keys(totals)) totals[key] += summary[key];
  return totals;
}, { active: 0, reserves: 0, connected: 0, ready: 0, missing: 0, aligned: 0 });

// Only the explicitly confirmed demo scenario gets ranks. Observed live scores
// and incomplete result snapshots are never interpreted as final outcomes.
export const resultRows = (match) => {
  if (match.result?.status !== 'confirmed-demo') return [];
  const entries = match.factions.map((faction) => ({
    faction,
    score: match.scores?.[faction.id] ?? null
  }));
  if (entries.some((entry) => !Number.isFinite(entry.score))) return [];
  entries.sort((a, b) => b.score - a.score);
  return entries.map((entry, index) => ({
    ...entry,
    rank: entries.findIndex((candidate) => candidate.score === entry.score) + 1,
    tied: entries.filter((candidate) => candidate.score === entry.score).length > 1,
    index
  }));
};
