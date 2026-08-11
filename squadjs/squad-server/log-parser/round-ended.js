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

function recordRoundAuditEvent(logParser, event) {
  const sequence = (logParser.eventStore.ROUND_AUDIT_SEQ || 0) + 1;
  logParser.eventStore.ROUND_AUDIT_SEQ = sequence;
  logParser.eventStore.ROUND_AUDIT = [
    ...(logParser.eventStore.ROUND_AUDIT || []),
    {
      sequence,
      observedAt: Date.now() / 1000,
      ...event
    }
  ].slice(-25);
}

function buildRoundEndData(logParser, pendingRoundEnd) {
  const winner = logParser.eventStore.ROUND_WINNER || buildFallbackWinner(logParser) || null;
  const loser = logParser.eventStore.ROUND_LOSER ? logParser.eventStore.ROUND_LOSER : null;
  return {
    winner,
    loser,
    layer: winner?.layer || loser?.layer || logParser.eventStore.WON?.layer || null,
    partial: !logParser.eventStore.ROUND_WINNER || !logParser.eventStore.ROUND_LOSER,
    time: pendingRoundEnd.time,
    previousState: pendingRoundEnd.previousState,
    nextState: pendingRoundEnd.nextState,
    roundAudit: {
      emittedAfterMs: Date.now() - pendingRoundEnd.createdAtMs,
      emittedBy: pendingRoundEnd.emitReason || 'unknown',
      completeAtEmit: !!(logParser.eventStore.ROUND_WINNER && logParser.eventStore.ROUND_LOSER),
      events: logParser.eventStore.ROUND_AUDIT || []
    }
  };
}

function clearRoundTicketState(logParser) {
  delete logParser.eventStore.ROUND_WINNER;
  delete logParser.eventStore.ROUND_LOSER;
  delete logParser.eventStore.WON;
  delete logParser.eventStore.ROUND_AUDIT;
  delete logParser.eventStore.ROUND_AUDIT_SEQ;
}

function emitPendingRoundEnd(logParser) {
  const pendingRoundEnd = logParser.eventStore.ROUND_END_PENDING;
  if (!pendingRoundEnd || pendingRoundEnd.emitted) {
    return;
  }

  pendingRoundEnd.emitted = true;
  pendingRoundEnd.emitReason = pendingRoundEnd.emitReason || 'settled';
  if (pendingRoundEnd.timeout) {
    clearTimeout(pendingRoundEnd.timeout);
  }

  const data = buildRoundEndData(logParser, pendingRoundEnd);
  console.log('[CmpBridge] ROUND_ENDED parsed', JSON.stringify({
    time: data.time,
    layer: data.layer,
    partial: data.partial,
    resultQuality: data.partial ? 'partial' : 'complete',
    emitReason: data.roundAudit?.emittedBy || null,
    emittedAfterMs: data.roundAudit?.emittedAfterMs || null,
    auditEvents: data.roundAudit?.events?.map((event) => event.type) || [],
    hasWinner: !!data.winner,
    hasLoser: !!data.loser,
    winnerTickets: data.winner?.tickets ?? null,
    loserTickets: data.loser?.tickets ?? null,
    previousState: data.previousState,
    nextState: data.nextState
  }));
  logParser.emit('ROUND_ENDED', data);
  clearRoundTicketState(logParser);
  delete logParser.eventStore.ROUND_END_PENDING;
}

function getRoundEndSettleMs() {
  const configuredValue = Number.parseInt(process.env.CMP_ROUND_END_SETTLE_MS || '', 10);
  if (Number.isFinite(configuredValue) && configuredValue >= 3000) {
    return configuredValue;
  }
  return 12000;
}

export default {
  regex:
    /^\[([0-9.:-]+)]\[([ 0-9]*)](?:LogGameState|LogSquadGameMode|LogSquad): .*Match State Changed from (.+) to (WaitingPostMatch|PostMatch|MatchEnded|MatchState_PostMatch)/,
  onMatch: (args, logParser) => {
    const existingPendingRoundEnd = logParser.eventStore.ROUND_END_PENDING;
    if (existingPendingRoundEnd && !existingPendingRoundEnd.emitted) {
      existingPendingRoundEnd.previousState = existingPendingRoundEnd.previousState || args[3] || null;
      existingPendingRoundEnd.nextState = args[4] || existingPendingRoundEnd.nextState || null;
      if (logParser.eventStore.ROUND_WINNER && logParser.eventStore.ROUND_LOSER) {
        existingPendingRoundEnd.emitReason = 'tickets_complete_after_duplicate_state';
        existingPendingRoundEnd.flush();
      }
      return;
    }

    if (existingPendingRoundEnd) {
      emitPendingRoundEnd(logParser);
    }

    const pendingRoundEnd = {
      time: args[1],
      previousState: args[3] || null,
      nextState: args[4] || null,
      raw: args[0],
      createdAtMs: Date.now(),
      emitted: false,
      flush: () => emitPendingRoundEnd(logParser)
    };

    recordRoundAuditEvent(logParser, {
      type: 'state_change',
      time: args[1],
      chainID: args[2],
      previousState: args[3] || null,
      nextState: args[4] || null,
      raw: args[0]
    });

    logParser.eventStore.ROUND_END_PENDING = pendingRoundEnd;

    if (logParser.eventStore.ROUND_WINNER && logParser.eventStore.ROUND_LOSER) {
      pendingRoundEnd.emitReason = 'tickets_complete_at_state_change';
      emitPendingRoundEnd(logParser);
      return;
    }

    const settleMs = getRoundEndSettleMs();
    recordRoundAuditEvent(logParser, {
      type: 'settle_timer_started',
      settleMs
    });

    pendingRoundEnd.timeout = setTimeout(() => {
      pendingRoundEnd.emitReason = 'settle_timeout';
      pendingRoundEnd.flush();
    }, settleMs);
  }
};
