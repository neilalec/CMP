<script setup>
import { computed } from 'vue';

const props = defineProps({
  selectedMap: {
    type: String,
    default: ''
  },
  serverPrefix: {
    type: String,
    default: 'Server'
  },
  serverDetails: {
    type: Object,
    default: null
  },
  canAdmin: {
    type: Boolean,
    default: false
  },
  autoConnectAvailable: {
    type: Boolean,
    default: false
  },
  autoConnectEnabled: {
    type: Boolean,
    default: false
  },
  directConnectAvailable: {
    type: Boolean,
    default: false
  },
  directConnectEnabled: {
    type: Boolean,
    default: false
  },
  isSpectator: {
    type: Boolean,
    default: false
  }
});

defineEmits(['auto-connect', 'direct-connect', 'leave-lobby']);

const serverName = computed(() => (
  props.serverDetails?.serverName
  || props.serverDetails?.bridge?.serverName
  || props.serverDetails?.bridge_response?.serverName
  || ''
));

const serverPassword = computed(() => props.serverDetails?.password || '');
const roundResult = computed(() => props.serverDetails?.roundResult || null);
const matchRounds = computed(() => (
  Array.isArray(roundResult.value?.rounds) && roundResult.value.rounds.length
    ? roundResult.value.rounds
    : (roundResult.value ? [roundResult.value] : [])
));
const hasMultiRoundResult = computed(() => matchRounds.value.length > 1);
const roundWinner = computed(() => roundResult.value?.winner || null);
const roundLoser = computed(() => roundResult.value?.loser || null);
const resultIsPartial = computed(() => Boolean(roundResult.value?.partial));
const resultIsUnresolved = computed(() => (
  Boolean(roundResult.value)
  && resultIsPartial.value
  && (
    !roundLoser.value
    || Boolean(roundWinner.value?.inferred)
  )
));
const roundLayer = computed(() => (
  roundWinner.value?.layer
  || roundLoser.value?.layer
  || roundResult.value?.layer
  || props.selectedMap
  || ''
));
const teamLabel = (team) => {
  if (!team) return '';
  return [team.subfaction, team.faction].filter(Boolean).join(' ').trim()
    || (team.team ? `Team ${team.team}` : '')
    || team.winner
    || team.name
    || '';
};
const isUnresolvedRound = (round) => Boolean(
  round
  && round.partial
  && (
    !round.loser
    || Boolean(round.winner?.inferred)
  )
);
const roundTicketRows = (round) => {
  if (isUnresolvedRound(round)) return [];
  return [round?.winner, round?.loser].filter(Boolean).map((side) => {
    const tickets = Number(side?.tickets);
    return {
      team: side?.team ? String(side.team) : '',
      label: teamLabel(side),
      tickets: Number.isFinite(tickets) ? tickets : null,
      wonRound: side === round?.winner
    };
  }).filter((side) => side.team && side.tickets !== null);
};
const formatTicketRows = (rows) => rows
  .map((row) => `${row.label || `Team ${row.team}`}: ${row.tickets}`)
  .join(' - ');
const roundSummaries = computed(() => matchRounds.value.map((round, index) => {
  const rows = roundTicketRows(round);
  return {
    key: `${round.observedAt || round.time || index}`,
    roundNumber: round.roundNumber || index + 1,
    score: formatTicketRows(rows) || 'Ticket totals unavailable'
  };
}));
const overallTicketSummary = computed(() => {
  const totals = new Map();
  for (const round of matchRounds.value) {
    for (const side of roundTicketRows(round)) {
      if (!totals.has(side.team)) {
        totals.set(side.team, {
          team: side.team,
          label: `Team ${side.team}`,
          tickets: 0
        });
      }
      totals.get(side.team).tickets += side.tickets;
    }
  }
  const rows = Array.from(totals.values()).sort((a, b) => Number(a.team) - Number(b.team));
  const sorted = [...rows].sort((a, b) => b.tickets - a.tickets);
  const hasWinner = sorted.length >= 2 && sorted[0].tickets !== sorted[1].tickets;
  return {
    score: formatTicketRows(rows),
    winner: hasWinner ? sorted[0] : null,
    loser: hasWinner ? sorted[1] : null,
    result: hasWinner
      ? `${sorted[0].label} beat ${sorted[1].label} by ${sorted[0].tickets - sorted[1].tickets} tickets`
      : (rows.length ? 'Draw on total tickets' : '')
  };
});
const winningSummary = computed(() => {
  if (resultIsUnresolved.value) return '';
  if (!roundWinner.value) return '';
  const winner = roundWinner.value;
  const factionSummary = [winner.subfaction, winner.faction].filter(Boolean).join(' ').trim();
  const teamSummary = winner.team ? `Team ${winner.team}` : '';
  const fallbackSummary = winner.winner || winner.name || '';
  const label = factionSummary || teamSummary || fallbackSummary || 'Winner';
  const ticketSummary = winner.tickets ? ` won on ${winner.tickets} tickets` : ' won';
  return `${label}${ticketSummary}`;
});
const losingSummary = computed(() => {
  if (resultIsUnresolved.value) return '';
  if (!roundLoser.value) return '';
  const loser = roundLoser.value;
  const factionSummary = [loser.subfaction, loser.faction].filter(Boolean).join(' ').trim();
  const teamSummary = loser.team ? `Team ${loser.team}` : '';
  const fallbackSummary = loser.winner || loser.name || '';
  const label = factionSummary || teamSummary || fallbackSummary || 'Loser';
  const ticketSummary = loser.tickets ? ` lost on ${loser.tickets} tickets` : ' lost';
  return `${label}${ticketSummary}`;
});
const ticketDifference = computed(() => {
  if (resultIsUnresolved.value) return '';
  const winnerTickets = Number(roundWinner.value?.tickets);
  const loserTickets = Number(roundLoser.value?.tickets);
  if (Number.isNaN(winnerTickets) || Number.isNaN(loserTickets)) return '';
  return String(winnerTickets - loserTickets);
});
const roundDurationSeconds = computed(() => {
  const explicitDuration = Number(props.serverDetails?.roundDurationSeconds);
  if (!Number.isNaN(explicitDuration) && explicitDuration >= 0) return explicitDuration;

  const liveStartedAt = Number(props.serverDetails?.liveStartedAt);
  const endedAt = Number(roundResult.value?.observedAt || roundResult.value?.capturedAt);
  if (Number.isNaN(liveStartedAt) || Number.isNaN(endedAt) || endedAt < liveStartedAt) return null;
  return endedAt - liveStartedAt;
});
const roundDuration = computed(() => {
  if (roundDurationSeconds.value === null) return '';
  const totalSeconds = Math.max(0, Math.round(roundDurationSeconds.value));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const parts = [];
  if (hours) parts.push(`${hours}h`);
  if (minutes || hours) parts.push(`${minutes}m`);
  parts.push(`${seconds}s`);
  return parts.join(' ');
});
const roundOutcome = computed(() => {
  if (resultIsUnresolved.value) {
    return 'Ticket totals unavailable.';
  }
  if (winningSummary.value && losingSummary.value && ticketDifference.value) return '';
  if (roundResult.value && winningSummary.value && resultIsPartial.value) {
    return 'Partial result.';
  }
  if (roundResult.value && (winningSummary.value || losingSummary.value)) {
    return 'No ticket totals.';
  }
  if (roundResult.value) return 'No winner data.';
  return '';
});
</script>

<template>
  <div class="match-info match-info-center window-panel">
    <div class="window-titlebar">
      <span class="window-titlebar-label">Match Summary</span>
    </div>
    <div class="match-info-body">
      <div class="match-info-row info-row is-stacked">
        <span class="info-row-label">Map</span>
        <strong class="info-row-value">{{ roundLayer || selectedMap || 'Map TBD' }}</strong>
      </div>
      <div class="match-info-row info-row is-stacked">
        <span class="info-row-label">Server Name</span>
        <strong class="info-row-value">{{ serverName || 'Server details pending' }}</strong>
      </div>
      <div class="match-info-row info-row is-stacked">
        <span class="info-row-label">Password</span>
        <strong class="info-row-value">{{ serverPassword || 'No password configured' }}</strong>
      </div>
      <template v-if="hasMultiRoundResult">
        <div v-for="round in roundSummaries" :key="round.key" class="match-info-row info-row is-stacked">
          <span class="info-row-label">Round {{ round.roundNumber }}</span>
          <strong class="info-row-value">{{ round.score }}</strong>
        </div>
        <div v-if="overallTicketSummary.score" class="match-info-row info-row is-stacked">
          <span class="info-row-label">Ticket Totals</span>
          <strong class="info-row-value">{{ overallTicketSummary.score }}</strong>
        </div>
        <div v-if="overallTicketSummary.result" class="match-info-row info-row is-stacked">
          <span class="info-row-label">Overall Result</span>
          <strong class="info-row-value">{{ overallTicketSummary.result }}</strong>
        </div>
      </template>
      <div v-if="!hasMultiRoundResult && winningSummary" class="match-info-row info-row is-stacked">
        <span class="info-row-label">Winner</span>
        <strong class="info-row-value">{{ winningSummary }}</strong>
      </div>
      <div v-if="!hasMultiRoundResult && losingSummary" class="match-info-row info-row is-stacked">
        <span class="info-row-label">Loser</span>
        <strong class="info-row-value">{{ losingSummary }}</strong>
      </div>
      <div v-if="roundDuration" class="match-info-row info-row is-stacked">
        <span class="info-row-label">Round Duration</span>
        <strong class="info-row-value">{{ roundDuration }}</strong>
      </div>
      <p v-if="roundOutcome" class="match-info-note">{{ roundOutcome }}</p>
      <div class="match-info-actions">
        <button class="match-leave-button" type="button" @click="$emit('leave-lobby')">
          {{ isSpectator ? 'Stop Spectating' : 'Leave Lobby' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.match-info {
  width: 100%;
  max-width: var(--middle-column-width, 280px);
  text-align: center;
  overflow: hidden;
}

.match-info-center {
  align-self: center;
  justify-self: center;
}

.match-info-body {
  padding: 14px;
}

.match-connect-button {
  margin-top: 10px;
  width: 100%;
}

.match-connect-button-secondary {
  margin-top: 8px;
}

.match-info-note {
  margin: 12px 0 0;
  color: var(--text-soft);
  font-size: 0.82rem;
  line-height: 1.4;
}

.match-info-actions {
  margin-top: 14px;
  padding-top: 12px;
  border-top: 1px solid var(--panel-border);
}

.match-leave-button {
  width: 100%;
  min-height: 34px;
  background: var(--control-bg);
  border-color: var(--control-border);
  color: inherit;
}

@media (max-width: 900px) {
  .match-info {
    width: 100%;
    max-width: 100%;
    margin-top: 0;
  }

  .match-info-center {
    align-self: stretch;
  }
}

@media (max-width: 640px) {
  .info-row-value {
    font-size: 1rem;
  }
}
</style>
