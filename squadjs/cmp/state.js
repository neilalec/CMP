import { buildActiveRound, buildScoreboardResult } from './scoreboard.js';
import { createRoundStatsCollector } from './stats.js';
import { createSyntheticLobbyManager } from './synthetic-lobby.js';
import { createRoundResultRegistry } from './rounds.js';

function shouldKeepExistingRoundResult(existingResult, nextResult) {
  if (!existingResult || !nextResult) {
    return false;
  }

  const existingIsComplete = existingResult.resultQuality === 'complete' && !existingResult.partial;
  const nextIsPartial = nextResult.partial || nextResult.resultQuality !== 'complete';
  const sameRoundTime = existingResult.time && nextResult.time && existingResult.time === nextResult.time;

  return existingIsComplete && nextIsPartial && sameRoundTime;
}

function countStatsEvents(roundStats) {
  return (roundStats?.rawEvents || []).reduce((counts, event) => {
    const type = event?.type || 'unknown';
    counts[type] = (counts[type] || 0) + 1;
    return counts;
  }, {});
}

export function createBridgeState(server) {
  const state = {
    latestRoundEnded: null,
    latestScoreboard: null,
    activeRound: null,
    layerStatus: {
      currentLevel: null,
      currentLayer: null,
      nextLevel: null,
      nextLayer: null
    },
    lastCommand: null,
    commandHistory: [],
    reconnectPromise: null,
    statsCollector: createRoundStatsCollector(server),
    roundResults: createRoundResultRegistry(),
    syntheticLobby: createSyntheticLobbyManager()
  };

  const onNewGame = (data) => {
    state.activeRound = buildActiveRound(server, data);
    state.statsCollector.reset(state.activeRound);
    console.log('[CmpBridge] Active round started', JSON.stringify({
      layer: state.activeRound.layer,
      level: state.activeRound.level
    }));
  };

  const onRoundEnded = (data) => {
    const nextScoreboard = buildScoreboardResult(
      server,
      data,
      state.activeRound,
      state.statsCollector.snapshot()
    );
    if (shouldKeepExistingRoundResult(state.latestScoreboard, nextScoreboard)) {
      state.roundResults.addResult(nextScoreboard);
      console.log('[CmpBridge] ROUND_ENDED partial ignored after complete result', JSON.stringify({
        existingObservedAt: state.latestScoreboard.observedAt,
        incomingObservedAt: nextScoreboard.observedAt,
        time: nextScoreboard.time || null,
        incomingLayer: nextScoreboard.layer || null,
        incomingResultQuality: nextScoreboard.resultQuality || null,
        incomingPartial: !!nextScoreboard.partial
      }));
      return;
    }

    state.latestScoreboard = nextScoreboard;
    state.roundResults.addResult(state.latestScoreboard);
    state.latestRoundEnded = state.latestScoreboard;
    console.log('[CmpBridge] ROUND_ENDED captured', JSON.stringify({
      observedAt: state.latestRoundEnded.observedAt,
      layer: state.latestRoundEnded.layer || null,
      partial: !!state.latestRoundEnded.partial,
      resultQuality: state.latestRoundEnded.resultQuality || null,
      hasWinner: !!state.latestRoundEnded.winner,
      hasLoser: !!state.latestRoundEnded.loser,
      statsPlayers: state.latestRoundEnded.roundStats?.players?.length || 0,
      statsEvents: state.latestRoundEnded.roundStats?.rawEvents?.length || 0,
      statsEventTypes: countStatsEvents(state.latestRoundEnded.roundStats)
    }));
  };

  server.on('NEW_GAME', onNewGame);
  server.on('ROUND_ENDED', onRoundEnded);

  state.dispose = () => {
    state.statsCollector?.dispose?.();
    state.syntheticLobby?.dispose?.();
    if (typeof server.off === 'function') {
      server.off('NEW_GAME', onNewGame);
      server.off('ROUND_ENDED', onRoundEnded);
      return;
    }
    server.removeListener('NEW_GAME', onNewGame);
    server.removeListener('ROUND_ENDED', onRoundEnded);
  };

  return state;
}
