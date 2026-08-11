/**
 * Matches when tickets appear in the log
 *
 * Will not match on Draw or Map Changes before the game has started
 */
export default {
  regex:
    /^\[([0-9.:-]+)]\[([ 0-9]*)]LogSquadGameEvents: Display: Team ([0-9]), (.*) \( ?(.*?) ?\) has (won|lost) the match with ([0-9]+) Tickets on layer (.*) \(level (.*)\)!/,
  onMatch: (args, logParser) => {
    const sequence = (logParser.eventStore.ROUND_AUDIT_SEQ || 0) + 1;
    const data = {
      raw: args[0],
      time: args[1],
      chainID: args[2],
      team: args[3],
      subfaction: args[4],
      faction: args[5],
      action: args[6],
      tickets: args[7],
      layer: args[8],
      level: args[9]
    };
    logParser.eventStore.ROUND_AUDIT_SEQ = sequence;
    logParser.eventStore.ROUND_AUDIT = [
      ...(logParser.eventStore.ROUND_AUDIT || []),
      {
        sequence,
        observedAt: Date.now() / 1000,
        type: data.action === 'won' ? 'winner_tickets' : 'loser_tickets',
        time: data.time,
        chainID: data.chainID,
        team: data.team,
        faction: data.faction,
        subfaction: data.subfaction,
        action: data.action,
        tickets: data.tickets,
        layer: data.layer,
        level: data.level,
        raw: data.raw
      }
    ].slice(-25);
    if (data.action === 'won') {
      logParser.eventStore.ROUND_WINNER = data;
    } else {
      logParser.eventStore.ROUND_LOSER = data;
    }

    const pendingRoundEnd = logParser.eventStore.ROUND_END_PENDING;
    if (
      pendingRoundEnd
      && !pendingRoundEnd.emitted
      && logParser.eventStore.ROUND_WINNER
      && logParser.eventStore.ROUND_LOSER
      && typeof pendingRoundEnd.flush === 'function'
    ) {
      pendingRoundEnd.emitReason = 'tickets_complete';
      pendingRoundEnd.flush();
    }
  }
};
