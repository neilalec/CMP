/**
 * Matches when tickets appear in the log
 *
 * Will not match on Draw or Map Changes before the game has started
 */
function getTicketResultKey(winner, loser) {
  return [
    winner?.layer || loser?.layer || '',
    winner?.team || '',
    winner?.tickets || '',
    loser?.team || '',
    loser?.tickets || ''
  ].join('|');
}

function emitLateRoundEndFromTickets(logParser, latestTicket) {
  const winner = logParser.eventStore.ROUND_WINNER || null;
  const loser = logParser.eventStore.ROUND_LOSER || null;
  if (!winner || !loser) {
    return;
  }

  const resultKey = getTicketResultKey(winner, loser);
  if (logParser.eventStore.LAST_ROUND_TICKET_RESULT_KEY === resultKey) {
    return;
  }
  logParser.eventStore.LAST_ROUND_TICKET_RESULT_KEY = resultKey;

  const data = {
    winner,
    loser,
    layer: winner.layer || loser.layer || null,
    partial: false,
    time: latestTicket.time,
    previousState: null,
    nextState: null,
    roundAudit: {
      emittedAfterMs: null,
      emittedBy: 'late_tickets_without_pending_state',
      completeAtEmit: true,
      events: logParser.eventStore.ROUND_AUDIT || []
    }
  };

  console.log('[CmpBridge] ROUND_ENDED parsed from late tickets', JSON.stringify({
    time: data.time,
    layer: data.layer,
    partial: data.partial,
    emitReason: data.roundAudit.emittedBy,
    hasWinner: true,
    hasLoser: true,
    winnerTickets: winner.tickets,
    loserTickets: loser.tickets
  }));

  logParser.emit('ROUND_ENDED', data);
  delete logParser.eventStore.ROUND_WINNER;
  delete logParser.eventStore.ROUND_LOSER;
  delete logParser.eventStore.WON;
  delete logParser.eventStore.ROUND_AUDIT;
  delete logParser.eventStore.ROUND_AUDIT_SEQ;
}

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

    console.log('[CmpBridge] ROUND_TICKETS parsed', JSON.stringify({
      action: data.action,
      team: data.team,
      faction: data.faction,
      subfaction: data.subfaction,
      tickets: data.tickets,
      layer: data.layer,
      level: data.level,
      hasPendingRoundEnd: !!logParser.eventStore.ROUND_END_PENDING,
      hasWinner: !!logParser.eventStore.ROUND_WINNER,
      hasLoser: !!logParser.eventStore.ROUND_LOSER
    }));

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
      return;
    }

    if (!pendingRoundEnd && logParser.eventStore.ROUND_WINNER && logParser.eventStore.ROUND_LOSER) {
      emitLateRoundEndFromTickets(logParser, data);
    }
  }
};
