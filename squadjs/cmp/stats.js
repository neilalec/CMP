import { normalizePlayer } from './players.js';

const MAX_RAW_EVENTS = 500;

function eventTime() {
  return Date.now() / 1000;
}

function playerKey(player) {
  return player?.eosID || player?.steamID || player?.name || null;
}

function identityValues(player = {}, fallback = {}) {
  return [
    player?.eosID,
    player?.steamID,
    player?.name,
    player?.playerID,
    fallback?.eosID,
    fallback?.steamID,
    fallback?.name,
    fallback?.playerID
  ]
    .map((value) => String(value || '').trim())
    .filter(Boolean);
}

function preferredPlayerKey(player = {}, fallback = {}) {
  return (
    player?.eosID
    || player?.steamID
    || fallback?.eosID
    || fallback?.steamID
    || player?.name
    || fallback?.name
    || player?.playerID
    || fallback?.playerID
    || null
  );
}

function emptyStats() {
  return {
    wounds: 0,
    kills: 0,
    deaths: 0,
    revives: 0,
    teamkills: 0,
    teamDeaths: 0,
    weapons: {}
  };
}

function mergePlayerRows(target, source) {
  if (!target || !source || target === source) return target;
  for (const [field, value] of Object.entries(source)) {
    if (field === 'stats') continue;
    if ((target[field] === undefined || target[field] === null || target[field] === '') && value !== undefined && value !== null && value !== '') {
      target[field] = value;
    }
  }
  for (const field of ['wounds', 'kills', 'deaths', 'revives', 'teamkills', 'teamDeaths']) {
    target.stats[field] = (target.stats[field] || 0) + (source.stats?.[field] || 0);
  }
  for (const [weapon, count] of Object.entries(source.stats?.weapons || {})) {
    target.stats.weapons[weapon] = (target.stats.weapons[weapon] || 0) + count;
  }
  return target;
}

function repointAliases(state, fromKey, toKey) {
  for (const [identity, mappedKey] of Object.entries(state.aliases)) {
    if (mappedKey === fromKey) {
      state.aliases[identity] = toKey;
    }
  }
}

function ensurePlayer(state, player, fallback = {}) {
  const identities = identityValues(player, fallback);
  const existingIdentity = identities.find((identity) => state.aliases[identity]);
  const key = existingIdentity ? state.aliases[existingIdentity] : preferredPlayerKey(player, fallback);
  if (!key) return null;

  if (!state.players[key]) {
    state.players[key] = {
      key,
      name: null,
      steamID: null,
      eosID: null,
      playerID: null,
      teamID: null,
      squadID: null,
      role: null,
      isLeader: null,
      firstSeenAt: eventTime(),
      lastSeenAt: null,
      connectedAt: null,
      disconnectedAt: null,
      stats: emptyStats()
    };
  }

  const row = state.players[key];
  for (const identity of identities) {
    const existingKey = state.aliases[identity];
    if (existingKey && existingKey !== key && state.players[existingKey]) {
      mergePlayerRows(row, state.players[existingKey]);
      delete state.players[existingKey];
      repointAliases(state, existingKey, key);
    }
    state.aliases[identity] = key;
  }

  const normalized = player ? normalizePlayer(player) : {};
  for (const [field, value] of Object.entries({ ...fallback, ...normalized })) {
    if (value !== undefined && value !== null && value !== '') {
      row[field] = value;
    }
  }
  row.lastSeenAt = eventTime();
  return row;
}

function incrementWeapon(row, weapon) {
  if (!row || !weapon) return;
  row.stats.weapons[weapon] = (row.stats.weapons[weapon] || 0) + 1;
}

function recordEvent(state, event) {
  state.eventSequence += 1;
  state.rawEvents.push({
    sequence: state.eventSequence,
    observedAt: eventTime(),
    ...event
  });
  if (state.rawEvents.length > MAX_RAW_EVENTS) {
    state.rawEvents = state.rawEvents.slice(-MAX_RAW_EVENTS);
  }
}

function buildInitialState(server, activeRound = null) {
  const state = {
    startedAt: activeRound?.startedAt || eventTime(),
    layer: activeRound?.layer || server.currentLayer?.layerClassname || server.currentLayer?.name || null,
    level: activeRound?.level || server.currentLayer?.level || null,
    players: {},
    aliases: {},
    rawEvents: [],
    eventSequence: 0
  };

  for (const player of server.players || []) {
    ensurePlayer(state, player);
  }

  return state;
}

export function createRoundStatsCollector(server) {
  let stats = buildInitialState(server);

  const reset = (activeRound = null) => {
    stats = buildInitialState(server, activeRound);
    recordEvent(stats, {
      type: 'round_started',
      layer: stats.layer,
      level: stats.level
    });
  };

  const onPlayerConnected = (data = {}) => {
    const row = ensurePlayer(stats, data.player, {
      eosID: data.eosID,
      steamID: data.steamID,
      name: data.player?.name
    });
    if (row) row.connectedAt = eventTime();
    recordEvent(stats, {
      type: 'player_connected',
      player: row ? { key: row.key, name: row.name, steamID: row.steamID, eosID: row.eosID } : null,
      raw: data.raw || null
    });
  };

  const onPlayerDisconnected = (data = {}) => {
    const row = ensurePlayer(stats, data.player, {
      eosID: data.eosID,
      steamID: data.steamID,
      name: data.player?.name
    });
    if (row) row.disconnectedAt = eventTime();
    recordEvent(stats, {
      type: 'player_disconnected',
      player: row ? { key: row.key, name: row.name, steamID: row.steamID, eosID: row.eosID } : null,
      raw: data.raw || null
    });
  };

  const onWound = (data = {}) => {
    const attacker = ensurePlayer(stats, data.attacker, data.attackerFallback);
    const victim = ensurePlayer(stats, data.victim, data.victimFallback);
    if (attacker && attacker.key !== victim?.key) {
      attacker.stats.wounds += 1;
      incrementWeapon(attacker, data.weapon);
      if (data.teamkill) attacker.stats.teamkills += 1;
    }
    recordEvent(stats, {
      type: 'wound',
      attackerKey: attacker?.key || null,
      victimKey: victim?.key || null,
      weapon: data.weapon || null,
      teamkill: !!data.teamkill,
      raw: data.raw || null
    });
    console.log('[CmpBridge] PLAYER_WOUNDED captured', JSON.stringify({
      attacker: attacker?.name || attacker?.steamID || attacker?.eosID || data.attackerFallback?.name || null,
      victim: victim?.name || victim?.steamID || victim?.eosID || data.victimFallback?.name || null,
      weapon: data.weapon || null,
      teamkill: !!data.teamkill
    }));
  };

  const onDeath = (data = {}) => {
    const attacker = ensurePlayer(stats, data.attacker, data.attackerFallback);
    const victim = ensurePlayer(stats, data.victim, data.victimFallback);
    if (victim) {
      victim.stats.deaths += 1;
      if (data.teamkill) victim.stats.teamDeaths += 1;
    }
    if (attacker && attacker.key !== victim?.key) {
      if (data.teamkill) {
        attacker.stats.teamkills += 1;
      } else {
        attacker.stats.kills += 1;
      }
      incrementWeapon(attacker, data.weapon);
    }
    recordEvent(stats, {
      type: 'death',
      attackerKey: attacker?.key || null,
      victimKey: victim?.key || null,
      weapon: data.weapon || null,
      teamkill: !!data.teamkill,
      raw: data.raw || null
    });
    console.log('[CmpBridge] PLAYER_DIED captured', JSON.stringify({
      attacker: attacker?.name || attacker?.steamID || attacker?.eosID || data.attackerFallback?.name || null,
      victim: victim?.name || victim?.steamID || victim?.eosID || data.victimFallback?.name || null,
      weapon: data.weapon || null,
      teamkill: !!data.teamkill
    }));
  };

  const onRevive = (data = {}) => {
    const reviver = ensurePlayer(stats, data.reviver, data.reviverFallback);
    const victim = ensurePlayer(stats, data.victim, data.victimFallback);
    if (reviver && reviver.key !== victim?.key) {
      reviver.stats.revives += 1;
    }
    recordEvent(stats, {
      type: 'revive',
      reviverKey: reviver?.key || null,
      victimKey: victim?.key || null,
      raw: data.raw || null
    });
  };

  const snapshot = () => {
    const players = Object.values(stats.players).sort((a, b) => {
      const teamDelta = Number(a.teamID || 0) - Number(b.teamID || 0);
      if (teamDelta) return teamDelta;
      return String(a.name || a.key).localeCompare(String(b.name || b.key));
    });

    const teamTotals = {};
    for (const player of players) {
      const teamKey = player.teamID ?? 'unknown';
      if (!teamTotals[teamKey]) {
        teamTotals[teamKey] = emptyStats();
      }
      for (const field of ['wounds', 'kills', 'deaths', 'revives', 'teamkills', 'teamDeaths']) {
        teamTotals[teamKey][field] += player.stats[field] || 0;
      }
    }

    return {
      source: 'cmp-event-stats-collector',
      startedAt: stats.startedAt,
      capturedAt: eventTime(),
      layer: stats.layer,
      level: stats.level,
      players,
      teams: teamTotals,
      rawEvents: stats.rawEvents
    };
  };

  const bind = () => {
    server.on('PLAYER_CONNECTED', onPlayerConnected);
    server.on('PLAYER_DISCONNECTED', onPlayerDisconnected);
    server.on('PLAYER_WOUNDED', onWound);
    server.on('PLAYER_DIED', onDeath);
    server.on('PLAYER_REVIVED', onRevive);
  };

  const dispose = () => {
    server.removeListener('PLAYER_CONNECTED', onPlayerConnected);
    server.removeListener('PLAYER_DISCONNECTED', onPlayerDisconnected);
    server.removeListener('PLAYER_WOUNDED', onWound);
    server.removeListener('PLAYER_DIED', onDeath);
    server.removeListener('PLAYER_REVIVED', onRevive);
  };

  bind();

  return {
    reset,
    snapshot,
    dispose
  };
}
