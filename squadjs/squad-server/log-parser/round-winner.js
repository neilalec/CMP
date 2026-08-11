export default {
  regex:
    /^\[([0-9.:-]+)]\[([ 0-9]*)]LogSquadTrace: \[DedicatedServer](?:ASQGameMode::)?DetermineMatchWinner\(\): (.+) won on (.+)/,
  onMatch: (args, logParser) => {
    const sequence = (logParser.eventStore.ROUND_AUDIT_SEQ || 0) + 1;
    const data = {
      raw: args[0],
      time: args[1],
      chainID: args[2],
      winner: args[3],
      layer: args[4]
    };
    logParser.eventStore.ROUND_AUDIT_SEQ = sequence;
    logParser.eventStore.ROUND_AUDIT = [
      ...(logParser.eventStore.ROUND_AUDIT || []),
      {
        sequence,
        observedAt: Date.now() / 1000,
        type: 'winner_hint',
        time: data.time,
        chainID: data.chainID,
        winner: data.winner,
        layer: data.layer,
        raw: data.raw
      }
    ].slice(-25);

    if (logParser.eventStore.WON) logParser.eventStore.WON = { ...data, winner: null };
    else logParser.eventStore.WON = data;
  }
};
