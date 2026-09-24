<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

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
const title = computed(() => (
  props.mode.shortLabel && props.mode.shortLabel !== 'WARDOGS'
    ? props.mode.shortLabel
    : 'WARDOGS Beta 9'
))
const progress = computed(() => Math.min(100, Math.max(0, Number(props.getQueueProgressPercent(props.mode.id)) || 0)))

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
  if (props.isInGroup && props.isGroupLeader) return `Queueing as a group of ${props.groupMemberCount}.`
  return ''
})

const actionLabel = computed(() => {
  if (props.wardogsLobbyId) return 'Open Match'
  if (props.matchAcceptActive) return 'Match forming'
  if (isQueuedHere.value) return props.isInGroup && !props.isGroupLeader ? 'Group leader only' : 'Leave Queue'
  if (queueUnavailable.value) return 'Match forming'
  if (props.loading) return 'Joining…'
  if (isQueueDisabled.value) return 'Queue unavailable'
  if (props.isInLobby) return 'In a lobby'
  if (isQueuedElsewhere.value) return 'Already queued'
  if (!props.hasSteamId) return 'Steam account required'
  if (props.isInGroup && !props.isGroupLeader) return 'Group leader only'
  if (isFull.value) return 'Queue full'
  return 'Join Queue'
})

const actionDisabled = computed(() => {
  if (props.wardogsLobbyId) return false
  if (props.matchAcceptActive) return true
  if (isQueuedHere.value) return props.loading || (props.isInGroup && !props.isGroupLeader)
  return (
    props.loading
    || isQueueDisabled.value
    || props.isInLobby
    || isQueuedElsewhere.value
    || queueUnavailable.value
    || !props.hasSteamId
    || (props.isInGroup && !props.isGroupLeader)
    || isFull.value
  )
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
  <article class="wardogs-queue-card cmp-surface" :class="{ 'is-queued': isQueuedHere }">
    <header class="wardogs-queue-heading">
      <div>
        <p class="wardogs-queue-kicker">WARDOGS</p>
        <h2 class="cmp-heading">{{ title }}</h2>
        <p class="wardogs-queue-format">{{ formatLabel }}</p>
      </div>
      <span v-if="isQueuedHere" class="wardogs-queue-state">Queued</span>
    </header>

    <div class="wardogs-queue-population">
      <p class="wardogs-queue-label">Players queued</p>
      <p class="wardogs-queue-count">
        <span>{{ playersQueued }}</span><span aria-hidden="true"> / </span><span>{{ maxPlayers }}</span>
      </p>
      <div
        class="wardogs-queue-progress"
        role="progressbar"
        aria-label="Queue population"
        aria-valuemin="0"
        :aria-valuemax="maxPlayers"
        :aria-valuenow="Math.min(playersQueued, maxPlayers)"
        :aria-valuetext="`${playersQueued} of ${maxPlayers} players queued`"
      >
        <span :style="{ width: `${progress}%` }"></span>
      </div>
    </div>

    <p v-if="status" class="wardogs-queue-status" :class="{ 'is-blocking': actionDisabled }" role="status">
      {{ status }}
    </p>

    <RouterLink v-if="wardogsLobbyId" class="wardogs-queue-action cmp-button cmp-button--primary" :to="`/wardogs/lobby/${wardogsLobbyId}`">
      {{ actionLabel }}
    </RouterLink>
    <button
      v-else
      class="wardogs-queue-action cmp-button"
      :class="isQueuedHere ? 'cmp-button--secondary is-leave' : 'cmp-button--primary'"
      type="button"
      :disabled="actionDisabled"
      @click="handleAction"
    >
      {{ actionLabel }}
    </button>

    <details v-if="canManageQueueTools" class="wardogs-queue-admin-tools">
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
  width: min(100%, 580px);
  min-width: 0;
  margin: 0 auto;
  padding: clamp(24px, 3.2vw, 34px);
  display: grid;
  gap: clamp(20px, 3vw, 28px);
  border-color: color-mix(in srgb, var(--cmp-border-strong) 78%, transparent);
  background: linear-gradient(145deg, color-mix(in srgb, var(--cmp-surface-raised) 38%, var(--cmp-surface)) 0%, var(--cmp-surface) 64%);
  box-shadow: var(--cmp-shadow-md);
}

.wardogs-queue-card.is-queued {
  border-color: color-mix(in srgb, var(--cmp-primary) 52%, var(--cmp-border));
  background: linear-gradient(145deg, color-mix(in srgb, var(--cmp-primary) 10%, var(--cmp-surface-raised)) 0%, var(--cmp-surface) 68%);
}

.wardogs-queue-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; }
.wardogs-queue-kicker,
.wardogs-queue-label { margin: 0; color: var(--cmp-text-muted); font-size: .68rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
.wardogs-queue-heading h2 { margin: 7px 0 5px; font-size: clamp(1.4rem, 2.7vw, 1.8rem); letter-spacing: -.035em; line-height: 1.12; }
.wardogs-queue-format { margin: 0; color: var(--cmp-text-secondary); font-size: .9rem; }
.wardogs-queue-state { flex: 0 0 auto; padding: 6px 10px; border: 1px solid color-mix(in srgb, var(--cmp-primary) 48%, transparent); border-radius: var(--cmp-radius-sm); background: color-mix(in srgb, var(--cmp-primary) 13%, transparent); color: #a9d5f5; font-size: .72rem; font-weight: 800; letter-spacing: .04em; }
.wardogs-queue-population { display: grid; gap: 9px; }
.wardogs-queue-count { margin: 0; color: var(--cmp-text); font-size: clamp(2.35rem, 6vw, 3.25rem); font-variant-numeric: tabular-nums; font-weight: 700; letter-spacing: -.055em; line-height: 1; }
.wardogs-queue-count span:nth-child(2) { color: var(--cmp-text-muted); font-size: .68em; font-weight: 500; }
.wardogs-queue-progress { height: 6px; overflow: hidden; border-radius: 999px; background: color-mix(in srgb, var(--cmp-surface-strong) 76%, #050b12); }
.wardogs-queue-progress span { display: block; height: 100%; border-radius: inherit; background: var(--cmp-primary); transition: width .3s ease; }
.wardogs-queue-status { margin: -7px 0 0; color: var(--cmp-text-secondary); font-size: .86rem; line-height: 1.4; }
.wardogs-queue-status.is-blocking { color: var(--cmp-warning); }
.wardogs-queue-action { width: 100%; min-height: 52px; padding: 12px 20px; font-size: .98rem; }
.wardogs-queue-action.is-leave { min-height: 48px; }
.wardogs-queue-action.is-leave:hover:not(:disabled) { border-color: color-mix(in srgb, var(--cmp-danger) 55%, var(--cmp-border)); background: color-mix(in srgb, var(--cmp-danger) 8%, var(--cmp-surface-raised)); color: var(--cmp-danger); }
.wardogs-queue-admin-tools { padding-top: 12px; border-top: 1px solid var(--cmp-border); }
.wardogs-queue-admin-tools summary { width: fit-content; color: var(--cmp-text-muted); font-size: .75rem; cursor: pointer; }
.queue-dev-actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr)); gap: 8px; margin-top: 12px; }
.queue-dev-actions button { min-height: 40px; padding: 8px 10px; font-size: .75rem; }

@media (max-width: 520px) {
  .wardogs-queue-card { width: 100%; padding: 22px 18px; gap: 22px; }
  .wardogs-queue-heading { gap: 12px; }
  .wardogs-queue-state { padding: 5px 8px; font-size: .67rem; }
  .wardogs-queue-action { min-height: 54px; font-size: 1rem; }
}

@media (prefers-reduced-motion: reduce) {
  .wardogs-queue-progress span,
  .wardogs-queue-action { transition: none; }
}
</style>
