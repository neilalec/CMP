<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import WardogsPlayGroup from './WardogsPlayGroup.vue'

const props = defineProps({
  mode: { type: Object, required: true },
  currentQueueMode: { type: String, default: null },
  inQueue: { type: Boolean, required: true },
  matchAcceptActive: { type: Boolean, required: true },
  loading: { type: Boolean, required: true },
  isInLobby: { type: Boolean, required: true },
  isInGroup: { type: Boolean, required: true },
  isGroupLeader: { type: Boolean, required: true },
  hasSteamId: { type: Boolean, required: true },
  groupMemberCount: { type: Number, required: true },
  canManageQueueTools: { type: Boolean, required: true },
  wardogsLobbyId: { type: String, default: null },
  getQueueProgressPercent: { type: Function, required: true },
  isModeQueueFull: { type: Function, required: true }
})

const emit = defineEmits(['join-queue', 'leave-queue', 'seed-queue', 'clear-queue', 'set-queue-enabled'])

const maxPlayers = computed(() => Number(props.mode.maxPlayers) || 9)
const playersQueued = computed(() => Math.max(0, Number(props.mode.playersInQueue) || 0))
const isQueuedHere = computed(() => props.inQueue && props.currentQueueMode === props.mode.id)
const isQueuedElsewhere = computed(() => props.inQueue && props.currentQueueMode !== props.mode.id)
const isQueueDisabled = computed(() => props.mode.disabled || props.mode.enabled === false)
const queueUnavailable = computed(() => props.mode.matchmakingAvailable === false)
const isFull = computed(() => props.isModeQueueFull(props.mode.id))
const formatLabel = computed(() => `${Number(props.mode.factionCount) || 3} factions · ${maxPlayers.value} players`)
const title = computed(() => {
  const shortLabel = String(props.mode.shortLabel || '').replace(/^WARDOGS\s*/i, '').trim()
  return shortLabel || 'Beta 9'
})
const isBlocked = computed(() => (
  isQueueDisabled.value || queueUnavailable.value || props.isInLobby || isQueuedElsewhere.value
  || !props.hasSteamId || (props.isInGroup && !props.isGroupLeader) || isFull.value
))
const canLeave = computed(() => isQueuedHere.value && (!props.isInGroup || props.isGroupLeader))
const canJoin = computed(() => !props.wardogsLobbyId && !props.matchAcceptActive && !isQueuedHere.value && !isBlocked.value)
const stateLabel = computed(() => {
  if (props.wardogsLobbyId) return 'Match ready'
  if (props.matchAcceptActive) return 'Match found'
  if (isQueuedHere.value) return 'In queue'
  if (props.isInLobby || isQueuedElsewhere.value) return 'Already playing'
  if (isQueueDisabled.value) return 'Queue paused'
  if (queueUnavailable.value) return 'Match forming'
  if (!props.hasSteamId) return 'Steam required'
  if (props.isInGroup && !props.isGroupLeader) return 'Leader controls'
  if (isFull.value) return 'Queue full'
  return 'Open'
})
const stateTone = computed(() => props.wardogsLobbyId ? 'cmp-status--success'
  : ['Queue full', 'Queue paused', 'Steam required'].includes(stateLabel.value)
    ? 'cmp-status--warning' : '')

const status = computed(() => {
  if (props.wardogsLobbyId) return 'Your match is ready.'
  if (props.matchAcceptActive) return 'Match forming.'
  if (isQueuedHere.value) {
    if (props.isInGroup && !props.isGroupLeader) return 'Your group leader manages this queue.'
    return props.isInGroup
      ? `Your group of ${props.groupMemberCount} is queued.`
      : 'You’re in the queue.'
  }
  if (props.isInLobby) return 'You’re already in a lobby.'
  if (isQueuedElsewhere.value) return 'You’re already queued.'
  if (isQueueDisabled.value) return props.mode.disabledReason || 'This queue is currently unavailable.'
  if (queueUnavailable.value) return 'A match is being prepared.'
  if (!props.hasSteamId) return 'A Steam-linked account is required to join.'
  if (props.isInGroup && !props.isGroupLeader) return 'Ask your group leader to join the queue.'
  if (isFull.value) return 'The queue is full.'
  if (props.isInGroup && props.isGroupLeader) return `Ready to queue your group of ${props.groupMemberCount}.`
  return 'Queue open.'
})

const handleAction = () => {
  if (props.wardogsLobbyId) return
  if (isQueuedHere.value) {
    emit('leave-queue', props.mode.id)
    return
  }
  emit('join-queue', props.mode.id)
}
</script>

<template>
  <article class="wardogs-queue-card cmp-surface" :class="{ 'is-queued': isQueuedHere, 'has-match': wardogsLobbyId }">
    <header class="wardogs-queue-heading">
      <div>
        <p class="cmp-kicker">Queue</p>
        <h2 class="cmp-heading">{{ title }}</h2>
        <p class="wardogs-queue-format">{{ formatLabel }}</p>
      </div>
      <span class="cmp-status wardogs-queue-state" :class="stateTone">{{ stateLabel }}</span>
    </header>

    <WardogsPlayGroup
      :actions-disabled="inQueue || isInLobby || !!wardogsLobbyId || matchAcceptActive"
      :is-in-group="isInGroup"
      :is-group-leader="isGroupLeader"
    />

    <div class="wardogs-queue-bottom">
      <div class="wardogs-queue-population">
        <div class="wardogs-queue-population-heading">
          <p class="cmp-kicker">Players in queue</p>
          <p class="wardogs-queue-count"><strong>{{ playersQueued }}</strong><span> / {{ maxPlayers }}</span></p>
        </div>
        <div class="wardogs-queue-slots" role="meter" aria-label="Queue occupancy" aria-valuemin="0" :aria-valuemax="maxPlayers" :aria-valuenow="Math.min(playersQueued, maxPlayers)" :aria-valuetext="`${playersQueued} of ${maxPlayers} players queued`">
          <span v-for="slot in maxPlayers" :key="slot" :class="{ 'is-filled': slot <= playersQueued }" aria-hidden="true"></span>
        </div>
      </div>
      <div class="wardogs-queue-decision">
        <p class="wardogs-queue-status" :class="{ 'is-blocking': isBlocked && !isQueuedHere }" role="status">{{ status }}</p>
        <RouterLink v-if="wardogsLobbyId" class="wardogs-queue-action cmp-button cmp-button--primary" :to="`/wardogs/lobby/${wardogsLobbyId}`">Open Match</RouterLink>
        <button v-else-if="canLeave" class="wardogs-queue-action cmp-button cmp-button--secondary is-leave" type="button" :disabled="loading" :aria-busy="loading" @click="handleAction">{{ loading ? 'Leaving…' : 'Leave Queue' }}</button>
        <button v-else-if="canJoin" class="wardogs-queue-action cmp-button cmp-button--primary" type="button" :disabled="loading" :aria-busy="loading" @click="handleAction">{{ loading ? 'Joining…' : 'Join Queue' }}</button>
      </div>
    </div>

    <details v-if="canManageQueueTools" class="wardogs-queue-admin-tools cmp-disclosure">
      <summary>Queue tools</summary>
      <div class="queue-dev-actions">
        <button class="cmp-button cmp-button--secondary" type="button" :disabled="loading" @click="emit('seed-queue', mode.id)">Fill WARDOGS beta queue</button>
        <button class="cmp-button cmp-button--secondary" type="button" :disabled="loading" @click="emit('clear-queue', mode.id)">Clear queue</button>
        <button class="cmp-button cmp-button--secondary" type="button" :disabled="loading" @click="emit('set-queue-enabled', mode.id, isQueueDisabled)">
          {{ isQueueDisabled ? 'Enable queue' : 'Disable queue' }}
        </button>
      </div>
    </details>
  </article>
</template>

<style scoped>
.wardogs-queue-card {
  width: 100%;
  min-width: 0;
  margin: 0 auto;
  padding: var(--cmp-space-5);
  display: grid;
  gap: var(--cmp-space-5);
  border-top: 3px solid var(--cmp-border-strong);
}
.wardogs-queue-card.is-queued { border-top-color: var(--cmp-primary); }
.wardogs-queue-card.has-match { border-top-color: var(--cmp-success); }
.wardogs-queue-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--cmp-space-4); }
.wardogs-queue-heading h2 { margin: var(--cmp-space-1) 0 0; font-size: 1.5rem; letter-spacing: -.03em; line-height: 1.15; }
.wardogs-queue-format { margin: var(--cmp-space-1) 0 0; color: var(--cmp-text-secondary); font-size: .875rem; }
.wardogs-queue-state { flex: none; margin-top: 2px; white-space: nowrap; }
.wardogs-queue-card.is-queued .wardogs-queue-state::before { background: var(--cmp-primary); }
.wardogs-queue-bottom { display: grid; grid-template-columns: minmax(0, 1fr) 200px; align-items: end; gap: var(--cmp-space-5); }
.wardogs-queue-population { min-width: 0; }
.wardogs-queue-population-heading { display: flex; align-items: baseline; justify-content: space-between; gap: var(--cmp-space-3); }
.wardogs-queue-count { margin: 0; font-variant-numeric: tabular-nums; white-space: nowrap; }
.wardogs-queue-count strong { font-size: 1.5rem; font-weight: 700; letter-spacing: -.04em; }
.wardogs-queue-count span { color: var(--cmp-text-muted); font-size: .875rem; }
.wardogs-queue-slots { display: grid; grid-auto-flow: column; grid-auto-columns: 1fr; gap: 4px; margin-top: var(--cmp-space-3); }
.wardogs-queue-slots span { display: block; height: 9px; border: 1px solid var(--cmp-border-strong); border-radius: 2px; background: var(--cmp-surface-inset); }
.wardogs-queue-slots span.is-filled { border-color: var(--cmp-primary); background: var(--cmp-primary); }
.wardogs-queue-decision { display: grid; gap: var(--cmp-space-2); align-content: end; }
.wardogs-queue-status { margin: 0; min-height: 2.6em; color: var(--cmp-text-secondary); font-size: .8125rem; line-height: 1.3; }
.wardogs-queue-status.is-blocking { color: var(--cmp-warning); }
.wardogs-queue-action { width: 100%; min-height: 44px; }
.wardogs-queue-action.is-leave:hover:not(:disabled) { border-color: var(--cmp-danger); color: var(--cmp-danger); }
.wardogs-queue-admin-tools { padding-top: var(--cmp-space-2); }
.wardogs-queue-admin-tools summary { width: fit-content; font-size: .8125rem; }
.queue-dev-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr)); gap: var(--cmp-space-2); margin-top: var(--cmp-space-3); }
.queue-dev-actions button { min-height: 42px; padding-inline: var(--cmp-space-2); font-size: .75rem; }
@media (max-width: 600px) {
  .wardogs-queue-card { padding: var(--cmp-space-4); gap: var(--cmp-space-4); }
  .wardogs-queue-bottom { grid-template-columns: 1fr; gap: var(--cmp-space-4); }
  .wardogs-queue-status { min-height: 0; }
}
@media (max-width: 375px) {
  .wardogs-queue-heading { gap: var(--cmp-space-2); }
  .wardogs-queue-heading h2 { font-size: 1.3rem; }
  .wardogs-queue-state { font-size: .75rem; }
}
</style>
