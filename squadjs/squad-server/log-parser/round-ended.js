/**
 * Matches when Map state Changes to PostMatch (ScoreBoard)
 *
 * Emits winner and loser from eventstore
 *
 * winner and loser may be null if the match ends with a draw
 */
function buildFallbackWinner(logParser) {
  if (!logParser.eventStore.WON) {
    return null;
  }

  return {
    ...logParser.eventStore.WON,
    faction: logParser.eventStore.WON.winner || null,
    subfaction: null,
    tickets: null,
    inferred: true
  };
}

export default {
  regex:
    /^\[([0-9.:-]+)]\[([ 0-9]*)](?:LogGameState|LogSquadGameMode|LogSquad): .*Match State Changed from (.+) to (WaitingPostMatch|PostMatch|MatchEnded|MatchState_PostMatch)/,
  onMatch: (args, logParser) => {
    const winner = logParser.eventStore.ROUND_WINNER || buildFallbackWinner(logParser) || null;
    const loser = logParser.eventStore.ROUND_LOSER ? logParser.eventStore.ROUND_LOSER : null;
    const data = {
      winner,
      loser,
      layer: winner?.layer || loser?.layer || logParser.eventStore.WON?.layer || null,
      partial: !logParser.eventStore.ROUND_WINNER || !logParser.eventStore.ROUND_LOSER,
      time: args[1],
      previousState: args[3] || null,
      nextState: args[4] || null
    };
    console.log('[CmpBridge] ROUND_ENDED parsed', JSON.stringify({
      time: data.time,
      layer: data.layer,
      partial: data.partial,
      hasWinner: !!data.winner,
      hasLoser: !!data.loser,
      previousState: data.previousState,
      nextState: data.nextState
    }));
    logParser.emit('ROUND_ENDED', data);
    delete logParser.eventStore.ROUND_WINNER;
    delete logParser.eventStore.ROUND_LOSER;
    delete logParser.eventStore.WON;
  }
};
