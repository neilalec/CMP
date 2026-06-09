<script setup>
import { computed } from 'vue';

const props = defineProps({
  matchSizeLabel: {
    type: String,
    default: ''
  },
  selectedMap: {
    type: String,
    default: ''
  },
  serverLabel: {
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
  autoConnectAvailable: {
    type: Boolean,
    default: false
  },
  autoConnectEnabled: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['auto-connect']);

const serverName = computed(() => (
  props.serverDetails?.serverName
  || props.serverDetails?.bridge?.serverName
  || props.serverDetails?.bridge_response?.serverName
  || ''
));

const serverPassword = computed(() => props.serverDetails?.password || '');
const connectAddress = computed(() => props.serverDetails?.connectAddress || props.serverDetails?.ip || '');
const connectUrl = computed(() => {
  if (!connectAddress.value) return '';
  const command = serverPassword.value
    ? `+connect ${connectAddress.value} +password ${serverPassword.value}`
    : `+connect ${connectAddress.value}`;
  return `steam://run/393380//${encodeURIComponent(command).replace(/%2B/g, '+')}`;
});
const roundResult = computed(() => props.serverDetails?.roundResult || null);
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
const roundEndedAt = computed(() => roundResult.value?.time || '');
const resultSummary = computed(() => {
  if (!roundResult.value) return '';
  if (resultIsUnresolved.value) return 'Draw / unresolved';
  if (winningSummary.value && losingSummary.value) return 'Completed';
  return 'Completed';
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
const bridgeNote = computed(() => {
  if (props.serverDetails?.bridgeAvailable === false) {
    return 'Bridge offline.';
  }
  return '';
});
</script>

<template>
  <div class="match-info match-info-center window-panel">
    <div class="window-titlebar">
      <span class="window-titlebar-label">Match Summary</span>
    </div>
    <div class="match-info-body">
      <div class="match-info-row">
        <span>Map</span>
        <strong>{{ roundLayer || selectedMap || 'Map TBD' }}</strong>
      </div>
      <div class="match-info-row">
        <span>Server Name</span>
        <strong>{{ serverName || serverLabel || 'Server details pending' }}</strong>
      </div>
      <div class="match-info-row">
        <span>Password</span>
        <strong>{{ serverPassword || 'No password configured' }}</strong>
      </div>
      <div v-if="connectAddress" class="match-info-row">
        <span>{{ serverPrefix }}</span>
        <a :href="connectUrl" class="server-link">{{ connectAddress }}</a>
      </div>
      <button
        v-if="autoConnectAvailable"
        type="button"
        class="match-connect-button"
        :disabled="!autoConnectEnabled"
        @click="emit('auto-connect')"
      >
        {{ autoConnectEnabled ? 'Auto Connect' : 'Waiting for server' }}
      </button>
      <div v-if="resultSummary" class="match-info-row">
        <span>Result</span>
        <strong>{{ resultSummary }}</strong>
      </div>
      <div v-if="winningSummary" class="match-info-row">
        <span>Winner</span>
        <strong>{{ winningSummary }}</strong>
      </div>
      <div v-if="losingSummary" class="match-info-row">
        <span>Loser</span>
        <strong>{{ losingSummary }}</strong>
      </div>
      <div v-if="ticketDifference" class="match-info-row">
        <span>Ticket Diff</span>
        <strong>{{ ticketDifference }}</strong>
      </div>
      <div v-if="roundEndedAt" class="match-info-row">
        <span>Round Ended</span>
        <strong>{{ roundEndedAt }}</strong>
      </div>
      <p v-if="roundOutcome" class="match-info-note">{{ roundOutcome }}</p>
      <p v-if="bridgeNote" class="match-info-note">{{ bridgeNote }}</p>
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

.match-info-row {
  display: flex;
  flex-direction: column;
  gap: 5px;
  padding: 10px;
  border-radius: var(--radius-sm);
  background: var(--panel-bg-strong);
  border: 1px solid var(--surface-border);
  box-shadow: var(--surface-shadow);
}

.match-info-row + .match-info-row {
  margin-top: 8px;
}

.match-info-row span {
  color: var(--text-muted);
  font-size: 0.76rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.match-info-row strong {
  color: var(--text-main);
  font-size: 1rem;
  line-height: 1.25;
  overflow-wrap: anywhere;
}

.server-link {
  color: var(--text-main);
  font-size: 1rem;
  font-weight: 800;
  line-height: 1.25;
  overflow-wrap: anywhere;
  text-decoration: none;
}

.server-link:hover,
.server-link:focus-visible {
  color: var(--accent-strong);
  text-decoration: underline;
}

.match-connect-button {
  margin-top: 10px;
  width: 100%;
}

.match-info-note {
  margin: 12px 0 0;
  color: var(--text-soft);
  font-size: 0.82rem;
  line-height: 1.4;
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
  .match-info-row strong {
    font-size: 1rem;
  }
}
</style>
