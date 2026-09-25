<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  active: {
    type: Boolean,
    required: true
  },
  isCancelled: {
    type: Boolean,
    required: true
  },
  cancelReason: {
    type: String,
    default: ''
  },
  countdown: {
    type: Number,
    default: 0
  },
  acceptedCount: {
    type: Number,
    required: true
  },
  requiredCount: {
    type: Number,
    required: true
  },
  acceptedPlayers: {
    type: Array,
    default: () => []
  },
  playerProfiles: {
    type: Object,
    default: () => ({})
  },
  waitingPlayers: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    required: true
  },
  hasAccepted: {
    type: Boolean,
    required: true
  },
  finalizingLobby: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['accept', 'close', 'dismiss'])

const displayName = (player) => props.playerProfiles?.[player]?.display_name || player
const phase = computed(() => props.isCancelled ? 'cancelled'
  : props.finalizingLobby ? 'finalizing' : props.hasAccepted ? 'accepted' : 'pending')
const remainingCount = computed(() => Math.max(0, props.requiredCount - props.acceptedCount))
const phaseTitle = computed(() => ({
  cancelled: 'Match cancelled',
  finalizing: 'Preparing match…',
  accepted: 'You accepted',
  pending: 'Accept this match'
})[phase.value])
const phaseDetail = computed(() => {
  if (phase.value === 'cancelled') return props.cancelReason || 'Not everyone accepted.'
  if (phase.value === 'finalizing') return 'Everyone accepted. Opening the match when it is ready.'
  if (phase.value === 'accepted') return remainingCount.value
    ? `Waiting for ${remainingCount.value} ${remainingCount.value === 1 ? 'player' : 'players'} to accept.`
    : 'Waiting for the match to be prepared.'
  return 'Confirm your place before the countdown ends.'
})
const modalElement = ref(null)
const phaseHeading = ref(null)
const primaryAction = ref(null)
let previousFocus = null
const restoreFocus = () => {
  if (previousFocus?.isConnected && (document.activeElement === document.body || modalElement.value?.contains(document.activeElement))) previousFocus.focus()
  previousFocus = null
}
onBeforeUnmount(restoreFocus)

watch(() => [props.active, phase.value], async ([active], [wasActive] = []) => {
  if (!active) {
    restoreFocus()
    return
  }
  if (!wasActive) previousFocus = document.activeElement
  await nextTick()
  if (!props.active) return
  if ((phase.value === 'pending' || phase.value === 'cancelled') && !primaryAction.value?.disabled) primaryAction.value?.focus()
  else phaseHeading.value?.focus()
}, { immediate: true, flush: 'post' })

const handleDialogKeydown = (event) => {
  if (event.key !== 'Tab' || !modalElement.value) return
  const focusable = [...modalElement.value.querySelectorAll('button:not(:disabled), a[href]')]
  if (!focusable.length) return
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (event.shiftKey && (document.activeElement === first || !focusable.includes(document.activeElement))) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (document.activeElement === last || !focusable.includes(document.activeElement))) {
    event.preventDefault()
    first.focus()
  }
}
</script>

<template>
  <div v-if="active" class="match-accept-overlay cmp-overlay">
    <section ref="modalElement" class="match-accept-modal cmp-surface cmp-surface--floating" :class="`is-${phase}`" role="dialog" aria-modal="true" aria-labelledby="match-accept-title" aria-describedby="match-accept-detail" @keydown="handleDialogKeydown">
      <header class="match-accept-header">
        <div>
          <p class="cmp-kicker">{{ isCancelled ? 'Matchmaking update' : 'Match found' }}</p>
          <span v-if="!isCancelled && !finalizingLobby" class="match-accept-countdown" :class="{ 'is-urgent': countdown <= 5 && !hasAccepted }" role="timer">{{ countdown ?? 0 }}s left</span>
        </div>
        <button
          class="match-accept-close cmp-button cmp-button--secondary"
          type="button"
          :aria-label="isCancelled ? 'Dismiss match cancellation' : 'Cancel match acceptance'"
          @click="emit('close')"
        >×</button>
      </header>
      <div class="match-accept-body">
        <div class="match-accept-summary" aria-live="polite">
          <h2 id="match-accept-title" ref="phaseHeading" tabindex="-1">{{ phaseTitle }}</h2>
          <p id="match-accept-detail">{{ phaseDetail }}</p>
          <p v-if="isCancelled">Check Play for your current queue status.</p>
          <p v-if="!isCancelled" class="match-accept-progress">{{ acceptedCount }} of {{ requiredCount }} accepted</p>
        </div>
      </div>
      <div v-if="!isCancelled" class="match-player-groups" aria-label="Acceptance status">
          <div class="match-player-list">
            <h3>Accepted <span>{{ acceptedPlayers.length }}</span></h3>
            <ul><li v-for="player in acceptedPlayers" :key="`accepted-${player}`" :title="player">{{ displayName(player) }}</li></ul>
            <p v-if="!acceptedPlayers.length" class="match-player-empty">No confirmations yet</p>
          </div>
          <div class="match-player-list">
            <h3>Waiting <span>{{ waitingPlayers.length }}</span></h3>
            <ul><li v-for="player in waitingPlayers" :key="`waiting-${player}`" :title="player">{{ displayName(player) }}</li></ul>
            <p v-if="!waitingPlayers.length" class="match-player-empty">No one waiting</p>
          </div>
      </div>
      <footer class="match-accept-footer">
        <button v-if="isCancelled" ref="primaryAction" class="match-accept-button cmp-button cmp-button--secondary" type="button" @click="emit('dismiss')">Dismiss</button>
        <button v-else-if="phase === 'pending'" ref="primaryAction" class="match-accept-button cmp-button cmp-button--primary" type="button" :disabled="loading" :aria-busy="loading" @click="emit('accept')">{{ loading ? 'Accepting…' : 'Accept Match' }}</button>
        <p v-else-if="phase === 'accepted'" class="match-accept-confirmed cmp-status cmp-status--success" role="status">Accepted · waiting for others</p>
        <p v-else class="match-accept-confirmed cmp-status cmp-status--success" role="status">Accepted · preparing match</p>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.match-accept-overlay {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: center;
  z-index: 40;
  padding: var(--cmp-space-4);
  overflow: auto;
}
.match-accept-modal {
  width: min(100%, 520px);
  max-height: calc(100dvh - 32px);
  min-height: 0;
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr) auto;
  overflow: hidden;
  border-top: 3px solid var(--cmp-primary);
}
.match-accept-modal.is-accepted, .match-accept-modal.is-finalizing { border-top-color: var(--cmp-success); }
.match-accept-modal.is-cancelled { grid-template-rows: auto auto auto; border-top-color: var(--cmp-warning); }
.match-accept-header { display: flex; align-items: start; justify-content: space-between; gap: var(--cmp-space-4); padding: var(--cmp-space-4) var(--cmp-space-5) 0; }
.match-accept-header > div { display: flex; align-items: center; flex-wrap: wrap; gap: var(--cmp-space-2) var(--cmp-space-4); min-height: 42px; }
.match-accept-header .cmp-kicker { color: var(--cmp-primary-hover); }
.is-cancelled .match-accept-header .cmp-kicker { color: var(--cmp-warning); }
.match-accept-countdown { color: var(--cmp-text); font: 700 .875rem/1 var(--cmp-font-mono); font-variant-numeric: tabular-nums; }
.match-accept-countdown.is-urgent { color: var(--cmp-warning); }
.match-accept-close {
  width: 42px;
  height: 42px;
  min-height: 42px;
  flex: none;
  padding: 0;
  font-size: 1.25rem;
  font-weight: 400;
  line-height: 1;
}
.match-accept-body { padding: var(--cmp-space-2) var(--cmp-space-5) var(--cmp-space-4); }
.match-accept-summary { display: grid; gap: var(--cmp-space-2); }
.match-accept-summary h2 { margin: 0; font-size: 1.5rem; line-height: 1.15; letter-spacing: -.03em; }
.match-accept-summary p { margin: 0; color: var(--cmp-text-secondary); font-size: .875rem; }
.match-accept-summary .match-accept-progress { color: var(--cmp-text); font-weight: 700; font-variant-numeric: tabular-nums; }
.match-player-groups {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--cmp-space-5);
  min-height: 0;
  margin: 0 var(--cmp-space-5);
  padding: var(--cmp-space-4) 0;
  border-top: 1px solid var(--cmp-border);
  overflow-y: auto;
  scrollbar-width: thin;
}
.match-player-list { min-width: 0; }
.match-player-list h3 { display: flex; justify-content: space-between; gap: var(--cmp-space-2); margin: 0 0 var(--cmp-space-2); color: var(--cmp-text-secondary); font-size: .75rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; }
.match-player-list h3 span { color: var(--cmp-text-muted); font-variant-numeric: tabular-nums; }
.match-player-list ul { display: grid; gap: 0; list-style: none; }
.match-player-list li { min-width: 0; padding: 6px 0; border-bottom: 1px solid var(--cmp-border); color: var(--cmp-text); font-size: .8125rem; font-weight: 600; overflow-wrap: anywhere; }
.match-player-list:first-child li::before { content: '✓'; margin-right: 8px; color: var(--cmp-success); }
.match-player-list:last-child li::before { content: '·'; margin-right: 8px; color: var(--cmp-text-muted); }
.match-player-empty { margin: 0; color: var(--cmp-text-muted); font-size: .8125rem; }
.match-accept-footer { min-height: 76px; display: grid; align-items: center; padding: var(--cmp-space-3) var(--cmp-space-5) var(--cmp-space-4); border-top: 1px solid var(--cmp-border); background: var(--cmp-surface); }
.match-accept-button { width: 100%; min-height: 46px; font-size: .9375rem; }
.match-accept-confirmed { margin: 0; font-size: .875rem; }
@media (max-width: 480px) {
  .match-accept-overlay { padding: var(--cmp-space-2); }
  .match-accept-modal { max-height: calc(100dvh - 16px); }
  .match-accept-header { padding: var(--cmp-space-3) var(--cmp-space-4) 0; }
  .match-accept-body { padding: var(--cmp-space-2) var(--cmp-space-4) var(--cmp-space-3); }
  .match-player-groups { gap: var(--cmp-space-3); margin-inline: var(--cmp-space-4); padding-block: var(--cmp-space-3); }
  .match-accept-footer { padding: var(--cmp-space-3) var(--cmp-space-4); }
}
</style>
