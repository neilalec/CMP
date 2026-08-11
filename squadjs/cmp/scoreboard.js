import { normalizePlayer } from './players.js';

function getLayerLabel(server, roundEnded, activeRound) {
  return (
    roundEnded?.layer
    || roundEnded?.winner?.layer
    || roundEnded?.loser?.layer
    || activeRound?.layer
    || server.currentLayer?.layerClassname
    || server.currentLayer?.name
    || null
  );
}

function getLevelLabel(server, roundEnded, activeRound) {
  return (
    roundEnded?.winner?.level
    || roundEnded?.loser?.level
    || activeRound?.level
    || server.currentLayer?.level
    || null
  );
}

function buildTeamSnapshot(players = []) {
  const teams = {};

  for (const player of players) {
    const teamId = player.teamID ?? 'unknown';
    if (!teams[teamId]) {
      teams[teamId] = {
        teamID: player.teamID ?? null,
        playerCount: 0,
        players: []
      };
    }

    teams[teamId].playerCount += 1;
    teams[teamId].players.push(normalizePlayer(player));
  }

  return Object.values(teams).sort((a, b) => {
    if (a.teamID === null) return 1;
    if (b.teamID === null) return -1;
    return a.teamID - b.teamID;
  });
}

function getResultQuality(roundEnded) {
  const winner = roundEnded?.winner || null;
  const loser = roundEnded?.loser || null;

  if (winner && loser && !roundEnded?.partial) {
    return 'complete';
  }

  if (roundEnded?.partial && (!loser || winner?.inferred)) {
    return 'draw_or_unresolved';
  }

  return 'partial';
}

export function buildScoreboardResult(server, roundEnded, activeRound = null, roundStats = null) {
  if (!roundEnded) return null;

  const resultQuality = getResultQuality(roundEnded);
  const isDrawOrUnresolved = resultQuality === 'draw_or_unresolved';
  const observedAt = Date.now() / 1000;

  return {
    ...roundEnded,
    observedAt,
    source: 'cmp-scoreboard-collector',
    resultQuality,
    draw: isDrawOrUnresolved,
    unresolved: isDrawOrUnresolved,
    partial: roundEnded.partial || resultQuality !== 'complete',
    winner: isDrawOrUnresolved ? null : roundEnded.winner || null,
    loser: isDrawOrUnresolved ? null : roundEnded.loser || null,
    inferredWinner: isDrawOrUnresolved ? roundEnded.winner || null : null,
    layer: getLayerLabel(server, roundEnded, activeRound),
    level: getLevelLabel(server, roundEnded, activeRound),
    endedAt: roundEnded.time || null,
    capturedAt: observedAt,
    teams: buildTeamSnapshot(server.players || []),
    roundStats
  };
}

export function buildActiveRound(server, data = {}) {
  return {
    startedAt: Date.now() / 1000,
    layer: data.layer?.layerClassname || data.layer?.classname || data.layer?.name || null,
    level: data.layer?.level || null,
    raw: {
      layerClassname: data.layerClassname || null
    }
  };
}
