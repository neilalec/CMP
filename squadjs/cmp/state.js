import { buildActiveRound, buildScoreboardResult } from './scoreboard.js';

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
    reconnectPromise: null
  };

  const onNewGame = (data) => {
    state.activeRound = buildActiveRound(server, data);
    console.log('[CmpBridge] Active round started', JSON.stringify({
      layer: state.activeRound.layer,
      level: state.activeRound.level
    }));
  };

  const onRoundEnded = (data) => {
    state.latestScoreboard = buildScoreboardResult(server, data, state.activeRound);
    state.latestRoundEnded = state.latestScoreboard;
    console.log('[CmpBridge] ROUND_ENDED captured', JSON.stringify({
      observedAt: state.latestRoundEnded.observedAt,
      layer: state.latestRoundEnded.layer || null,
      partial: !!state.latestRoundEnded.partial,
      resultQuality: state.latestRoundEnded.resultQuality || null,
      hasWinner: !!state.latestRoundEnded.winner,
      hasLoser: !!state.latestRoundEnded.loser
    }));
  };

  server.on('NEW_GAME', onNewGame);
  server.on('ROUND_ENDED', onRoundEnded);

  state.dispose = () => {
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
