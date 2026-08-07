<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  queueModes: {
    type: Array,
    required: true
  },
  currentQueueMode: {
    type: String,
    default: null
  },
  inQueue: {
    type: Boolean,
    required: true
  },
  matchAcceptActive: {
    type: Boolean,
    required: true
  },
  loading: {
    type: Boolean,
    required: true
  },
  isInLobby: {
    type: Boolean,
    required: true
  },
  isInGroup: {
    type: Boolean,
    required: true
  },
  isGroupLeader: {
    type: Boolean,
    required: true
  },
  hasSteamId: {
    type: Boolean,
    required: true
  },
  groupMemberCount: {
    type: Number,
    required: true
  },
  canManageQueueTools: {
    type: Boolean,
    required: true
  },
  serverAvailable: {
    type: Boolean,
    required: true
  },
  serverAvailabilityReason: {
    type: String,
    default: 'available'
  },
  getQueueProgressPercent: {
    type: Function,
    required: true
  },
  isModeQueueFull: {
    type: Function,
    required: true
  }
})

const emit = defineEmits(['join-queue', 'leave-queue', 'seed-queue', 'clear-queue', 'set-queue-enabled'])

const SEC_MODE_IDS = ['sec26', 'sec36', 'sec46']
const QUEUE_MOD_LINKS = {
  skirmish: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3294562930',
  sec26: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3661196801',
  sec36: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3661196801',
  sec46: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3661196801',
  rivals36: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3661196801',
  osi40: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3661196801',
  s30: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3735813803',
  ocbt15: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3264205573',
  ocbt5: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3264205573',
  ocbt1: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3264205573',
  balt26: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3686670558',
  outofthebox40: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3746481178'
}
const selectedSecModeId = ref(null)

const secModes = computed(() => {
  return SEC_MODE_IDS
    .map((modeId) => props.queueModes.find((queueMode) => queueMode.id === modeId))
    .filter(Boolean)
})

const queueCards = computed(() => {
  const cards = []
  let secCardAdded = false

  for (const queueMode of props.queueModes) {
    if (SEC_MODE_IDS.includes(queueMode.id)) {
      if (!secCardAdded && secModes.value.length) {
        cards.push({ id: 'sec', type: 'sec' })
        secCardAdded = true
      }
      continue
    }

    cards.push({ id: queueMode.id, type: 'standard', queueMode })
  }

  return cards
})

const activeSecMode = computed(() => {
  return secModes.value.find((queueMode) => queueMode.id === props.currentQueueMode) || null
})

const selectedSecMode = computed(() => {
  if (activeSecMode.value) return activeSecMode.value
  return secModes.value.find((queueMode) => queueMode.id === selectedSecModeId.value) || null
})

watch(activeSecMode, (mode) => {
  if (mode?.id) {
    selectedSecModeId.value = mode.id
  }
}, { immediate: true })

const isSecQueueMode = (modeId) => SEC_MODE_IDS.includes(modeId)

const getQueueTitle = (queueMode) => {
  if (queueMode.id === 'hotdrop') return 'Hotdrop Tournament Layers'
  if (queueMode.id === 's30') return 'S3O Layers'
  if (queueMode.id === 'rivals36') return 'Rivals Layers'
  if (queueMode.id === 'osi40') return 'Offworld Squad Invitational Layers'
  if (queueMode.id === 'ocbt15' || queueMode.id === 'ocbt5' || queueMode.id === 'ocbt1') return 'Open Clan Battle Layers'
  if (queueMode.id === 'balt26') return 'Squad Balt Layers'
  if (queueMode.id === 'outofthebox40') return 'Out of The Box Layers'
  if (isSecQueueMode(queueMode.id)) return 'Squad Esports Cup Layers'
  return 'Skirmish Layers'
}

const getQueueModLink = (queueMode) => QUEUE_MOD_LINKS[queueMode?.id] || ''

const getQueueStatusLabel = (queueMode) => {
  if (queueMode.disabled || queueMode.enabled === false) return 'Disabled'
  if (props.inQueue && props.currentQueueMode === queueMode.id) return 'Queued'
  if (props.inQueue && props.currentQueueMode !== queueMode.id) return 'Other queue'
  if (props.isInLobby) return 'In lobby'
  if (!props.serverAvailable) return getServerUnavailableLabel()
  if (!props.hasSteamId) return 'Steam ID needed'
  if (props.isInGroup && !props.isGroupLeader) return 'Leader only'
  if (props.isModeQueueFull(queueMode.id)) return 'Full'
  return 'Ready'
}

const getPrimaryLabel = (queueMode) => {
  if (props.inQueue && props.currentQueueMode === queueMode.id) {
    if (props.isInGroup && props.isGroupLeader) {
      return `Leave Queue as Group of ${props.groupMemberCount}`
    }
    return 'Leave Queue'
  }
  if (props.isInLobby) return "You're in a lobby"
  if (queueMode.disabled || queueMode.enabled === false) return 'Queue disabled'
  if (!props.serverAvailable) return getServerUnavailableLabel()
  if (!props.hasSteamId) return 'Set Steam ID in Profile'
  if (props.isInGroup && !props.isGroupLeader) return 'Group leader only'
  if (props.inQueue && props.currentQueueMode !== queueMode.id) return 'Queued elsewhere'
  if (props.isModeQueueFull(queueMode.id)) return 'Queue is full'
  if (props.loading) return 'Processing...'
  if (props.isInGroup && props.isGroupLeader) return `Queue as Group of ${props.groupMemberCount}`
  return 'Join Queue'
}

const getServerUnavailableLabel = () => {
  if (props.serverAvailabilityReason === 'server_in_use') return 'Server in use'
  if (props.serverAvailabilityReason === 'match_acceptance_active') return 'Match forming'
  if (props.serverAvailabilityReason === 'no_servers') return 'No servers available'
  return 'Server unavailable'
}

const serverPausedMessage = computed(() => {
  if (props.serverAvailable) return ''
  if (props.serverAvailabilityReason === 'server_in_use') {
    return 'Queue fulfilment is paused while the match server is in use.'
  }
  if (props.serverAvailabilityReason === 'match_acceptance_active') {
    return 'Queue fulfilment is paused while another match is being accepted.'
  }
  if (props.serverAvailabilityReason === 'no_servers') {
    return 'Queue fulfilment is paused because no approved match server is available.'
  }
  return 'Queue fulfilment is paused while server availability is checked.'
})

const isJoinDisabled = (queueMode) => (
  props.loading
  || props.isInLobby
  || queueMode.disabled
  || queueMode.enabled === false
  || props.inQueue
  || !props.serverAvailable
  || props.isModeQueueFull(queueMode.id)
  || (props.isInGroup && !props.isGroupLeader)
  || !props.hasSteamId
)

const isLeaveDisabled = () => props.loading || (props.isInGroup && !props.isGroupLeader)

const handleSecSelect = (modeId) => {
  selectedSecModeId.value = modeId
}

const handleSecReset = () => {
  if (activeSecMode.value) return
  selectedSecModeId.value = null
}

const handleSecJoin = () => {
  if (!selectedSecMode.value) return
  emit('join-queue', selectedSecMode.value.id)
}
</script>

<template>
  <section class="queue-board">
    <p v-if="serverPausedMessage" class="queue-paused-message">
      {{ serverPausedMessage }}
    </p>
    <div class="queue-grid">
      <template v-for="queueCard in queueCards" :key="queueCard.id">
        <article
          v-if="queueCard.type === 'standard'"
          :class="[
            'queue-card',
            'window-panel',
            {
              'is-active': currentQueueMode === queueCard.queueMode.id,
              'is-disabled': queueCard.queueMode.disabled || queueCard.queueMode.enabled === false,
              'no-dev-tools-card': !canManageQueueTools
            }
          ]"
        >
          <div class="window-titlebar">
            <span class="window-titlebar-label">{{ queueCard.queueMode.teamSize }}v{{ queueCard.queueMode.teamSize }}</span>
            <span class="window-titlebar-meta">{{ getQueueStatusLabel(queueCard.queueMode) }}</span>
          </div>
          <div class="queue-card-body" :class="{ 'no-dev-tools': !canManageQueueTools }">
            <div class="queue-card-top">
              <a
                v-if="getQueueModLink(queueCard.queueMode)"
                class="queue-title-link"
                :href="getQueueModLink(queueCard.queueMode)"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ getQueueTitle(queueCard.queueMode) }}
              </a>
              <strong v-else>{{ getQueueTitle(queueCard.queueMode) }}</strong>
            </div>

            <div class="queue-progress-row">
              <div class="queue-meter" aria-hidden="true">
                <span class="queue-meter-fill" :style="{ width: `${getQueueProgressPercent(queueCard.queueMode.id)}%` }"></span>
                <strong class="queue-meter-label">{{ queueCard.queueMode.playersInQueue }}/{{ queueCard.queueMode.maxPlayers }}</strong>
              </div>
            </div>

            <div class="queue-action-slot">
              <button
                v-if="!(inQueue && currentQueueMode === queueCard.queueMode.id)"
                class="queue-action"
                :disabled="isJoinDisabled(queueCard.queueMode)"
                @click="emit('join-queue', queueCard.queueMode.id)"
              >
                {{ getPrimaryLabel(queueCard.queueMode) }}
              </button>

              <button
                v-else
                class="queue-action is-danger"
                :disabled="isLeaveDisabled()"
                @click="emit('leave-queue', queueCard.queueMode.id)"
              >
                {{ getPrimaryLabel(queueCard.queueMode) }}
              </button>
            </div>

            <div v-if="canManageQueueTools" class="queue-dev-actions">
              <button type="button" @click="emit('seed-queue', queueCard.queueMode.id)" :disabled="loading">
                Seed {{ queueCard.queueMode.label }}
              </button>
              <button type="button" @click="emit('clear-queue', queueCard.queueMode.id)" :disabled="loading">
                Clear {{ queueCard.queueMode.shortLabel }}
              </button>
              <button
                type="button"
                class="queue-toggle-button"
                :class="{ 'is-enable': queueCard.queueMode.disabled || queueCard.queueMode.enabled === false }"
                :disabled="loading"
                @click="emit('set-queue-enabled', queueCard.queueMode.id, queueCard.queueMode.disabled || queueCard.queueMode.enabled === false)"
              >
                {{ queueCard.queueMode.disabled || queueCard.queueMode.enabled === false ? 'Enable' : 'Disable' }} {{ queueCard.queueMode.shortLabel }}
              </button>
            </div>
          </div>
        </article>

        <article
          v-else
          :class="[
            'queue-card',
            'window-panel',
            'sec-queue-card',
            { 'is-active': !!activeSecMode, 'no-dev-tools-card': !canManageQueueTools }
          ]"
        >
          <div class="window-titlebar">
            <span class="window-titlebar-label">
              {{ selectedSecMode ? `${selectedSecMode.teamSize}v${selectedSecMode.teamSize}` : 'Select Format' }}
            </span>
            <button
              v-if="selectedSecMode && !activeSecMode"
              type="button"
              class="sec-back-button"
              @click="handleSecReset"
            >
              Back to Formats
            </button>
            <span class="window-titlebar-meta">
              {{ selectedSecMode ? getQueueStatusLabel(selectedSecMode) : 'Choose format' }}
            </span>
          </div>
          <div class="queue-card-body" :class="{ 'no-dev-tools': !canManageQueueTools }">
            <div class="queue-card-top">
              <a
                class="queue-title-link"
                href="https://steamcommunity.com/sharedfiles/filedetails/?id=3661196801"
                target="_blank"
                rel="noopener noreferrer"
              >
                Squad Esports Cup Layers
              </a>
            </div>

            <div v-if="selectedSecMode" class="queue-progress-row">
              <div class="queue-meter" aria-hidden="true">
                <span
                  class="queue-meter-fill"
                  :style="{ width: `${selectedSecMode ? getQueueProgressPercent(selectedSecMode.id) : 0}%` }"
                ></span>
                <strong class="queue-meter-label">
                  {{ selectedSecMode ? `${selectedSecMode.playersInQueue}/${selectedSecMode.maxPlayers}` : '--/--' }}
                </strong>
              </div>
            </div>

            <div v-if="!selectedSecMode" class="sec-mini-meter-grid">
              <div
                v-for="queueMode in secModes"
                :key="`sec-meter-${queueMode.id}`"
                class="sec-mini-meter-card"
              >
                <div class="sec-mini-meter" aria-hidden="true">
                  <span
                    class="sec-mini-meter-fill"
                    :style="{ width: `${getQueueProgressPercent(queueMode.id)}%` }"
                  ></span>
                  <strong class="sec-mini-meter-label">
                    {{ queueMode.playersInQueue }}/{{ queueMode.maxPlayers }}
                  </strong>
                </div>
              </div>
            </div>

            <div v-if="!selectedSecMode" class="queue-action-slot">
              <div class="sec-option-grid">
                <button
                  v-for="queueMode in secModes"
                  :key="`sec-option-${queueMode.id}`"
                  type="button"
                  class="queue-action sec-option-button"
                  :disabled="loading"
                  @click="handleSecSelect(queueMode.id)"
                >
                  {{ queueMode.teamSize }}v{{ queueMode.teamSize }}
                </button>
              </div>
            </div>

            <div v-if="selectedSecMode" class="queue-action-slot">
              <button
                v-if="activeSecMode"
                class="queue-action is-danger"
                :disabled="isLeaveDisabled()"
                @click="emit('leave-queue', activeSecMode.id)"
              >
                {{ getPrimaryLabel(activeSecMode) }}
              </button>

              <button
                v-else
                class="queue-action"
                :disabled="isJoinDisabled(selectedSecMode)"
                @click="handleSecJoin"
              >
                {{ getPrimaryLabel(selectedSecMode) }}
              </button>
            </div>

            <div v-if="canManageQueueTools" class="queue-dev-actions sec-dev-actions">
              <button
                v-for="queueMode in secModes"
                :key="`seed-${queueMode.id}`"
                type="button"
                @click="emit('seed-queue', queueMode.id)"
                :disabled="loading"
              >
                Seed {{ queueMode.shortLabel }}
              </button>
              <button
                v-for="queueMode in secModes"
                :key="`clear-${queueMode.id}`"
                type="button"
                @click="emit('clear-queue', queueMode.id)"
                :disabled="loading"
              >
                Clear {{ queueMode.shortLabel }}
              </button>
            </div>
          </div>
        </article>
      </template>
    </div>
  </section>
</template>

<style scoped>
.queue-board {
  width: 100%;
  padding-block: 6px;
}

.queue-paused-message {
  margin: 0 auto 14px;
  max-width: 780px;
  color: var(--accent-strong);
  text-align: center;
  font-weight: 650;
  line-height: 1.35;
}

.queue-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 320px));
  justify-content: center;
  gap: 24px;
}

.queue-card {
  overflow: hidden;
  min-height: 222px;
  display: flex;
  flex-direction: column;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.queue-card.no-dev-tools-card {
  height: 222px;
}

.queue-card.is-active {
  border-color: var(--accent-border);
  background: linear-gradient(180deg, color-mix(in srgb, var(--panel-bg-strong) 88%, var(--accent-soft) 12%) 0%, var(--panel-bg) 100%);
  box-shadow: 0 0 0 1px var(--accent-ring), var(--window-shadow), var(--window-inset);
}

.queue-card.is-disabled {
  border-color: color-mix(in srgb, var(--surface-border-strong) 72%, var(--danger) 28%);
  opacity: 0.78;
}

.queue-card-body {
  flex: 1;
  padding: 14px;
  display: grid;
  grid-template-rows: auto auto auto auto;
  gap: 12px;
  align-content: start;
}

.queue-card-body.no-dev-tools {
  grid-template-rows: auto auto 1fr;
}

.queue-card-top {
  min-height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.queue-card-top strong,
.queue-title-link {
  display: block;
  margin: 0;
  color: var(--accent-strong);
  font-family: var(--font-display);
  font-size: 1.2rem;
  font-weight: 900;
  line-height: 1.1;
}

.queue-title-link {
  text-decoration: none;
}

.queue-title-link:hover {
  color: var(--accent);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.queue-progress-row {
  display: block;
}

.queue-meter {
  position: relative;
  height: 18px;
  width: 100%;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--accent-soft) 28%, white 72%);
  border: 1px solid color-mix(in srgb, var(--accent-border) 48%, var(--surface-border-strong));
  box-shadow: var(--inset-shadow);
}

.queue-meter-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--accent-soft) 86%, white 14%) 0%,
    color-mix(in srgb, var(--accent) 64%, white 36%) 100%
  );
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.28);
  position: relative;
  overflow: hidden;
}

.queue-meter-fill::after {
  content: "";
  position: absolute;
  inset: 0;
  background:
    linear-gradient(
      110deg,
      transparent 0%,
      rgba(255, 255, 255, 0.16) 35%,
      rgba(255, 255, 255, 0.42) 50%,
      rgba(255, 255, 255, 0.16) 65%,
      transparent 100%
    );
  background-size: 180% 100%;
  animation: queue-meter-shimmer 2.2s linear infinite;
}

.queue-meter-label {
  position: absolute;
  top: 50%;
  left: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 16px;
  padding: 0 6px;
  color: color-mix(in srgb, var(--text-main) 88%, #1c3552 12%);
  font-family: var(--font-mono);
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.28);
  transform: translate(-50%, -50%);
  z-index: 1;
}

.queue-action {
  width: 100%;
}

.queue-action-slot {
  display: flex;
  align-items: flex-start;
}

.queue-card-body.no-dev-tools .queue-action-slot {
  align-items: center;
}

.queue-action.is-danger {
  background: linear-gradient(180deg, color-mix(in srgb, var(--danger-soft) 92%, white 8%) 0%, var(--danger-soft) 100%);
  border-color: color-mix(in srgb, var(--danger) 40%, var(--surface-border));
  color: var(--danger);
}

.sec-back-button {
  margin-inline: auto;
  min-height: 24px;
  padding: 0 10px;
  border: 1px solid color-mix(in srgb, var(--accent-strong) 32%, rgba(255, 255, 255, 0.38));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, rgba(255, 255, 255, 0.18) 100%, transparent 0%);
  color: #f8fbff;
  font-family: var(--font-mono);
  font-size: 0.66rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  white-space: nowrap;
}

.sec-back-button:hover {
  background: color-mix(in srgb, rgba(255, 255, 255, 0.28) 100%, transparent 0%);
}

.sec-mini-meter-grid,
.sec-option-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
  width: 100%;
}

.sec-mini-meter-card {
  display: block;
}

.sec-mini-meter {
  position: relative;
  height: 12px;
  width: 100%;
  overflow: hidden;
  border-radius: 999px;
  background: color-mix(in srgb, var(--accent-soft) 28%, white 72%);
  border: 1px solid color-mix(in srgb, var(--accent-border) 48%, var(--surface-border-strong));
  box-shadow: var(--inset-shadow);
}

.sec-mini-meter-fill {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(
    90deg,
    color-mix(in srgb, var(--accent-soft) 86%, white 14%) 0%,
    color-mix(in srgb, var(--accent) 64%, white 36%) 100%
  );
}

.sec-mini-meter-label {
  position: absolute;
  top: 50%;
  left: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 10px;
  padding: 0 4px;
  color: color-mix(in srgb, var(--text-main) 88%, #1c3552 12%);
  font-family: var(--font-mono);
  font-size: 0.6rem;
  font-weight: 800;
  letter-spacing: 0.03em;
  transform: translate(-50%, -50%);
}

.sec-option-button {
  min-width: 0;
  padding-inline: 0;
}

.queue-dev-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.queue-dev-actions button {
  flex: 1 1 180px;
}

.queue-dev-actions .queue-toggle-button {
  border-color: color-mix(in srgb, var(--danger) 36%, var(--surface-border));
  color: var(--danger);
}

.queue-dev-actions .queue-toggle-button.is-enable {
  border-color: color-mix(in srgb, var(--success, #2f855a) 36%, var(--surface-border));
  color: var(--success, #2f855a);
}

.sec-dev-actions button {
  flex-basis: calc(50% - 4px);
}

@media (max-width: 1120px) {
  .queue-grid {
    grid-template-columns: repeat(2, minmax(220px, 320px));
  }
}

@media (max-width: 900px) {
  .queue-grid {
    grid-template-columns: 1fr;
    gap: 30px;
  }

  .sec-option-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .queue-board {
    padding-block: 0;
  }

  .queue-grid {
    gap: 14px;
  }

  .queue-card {
    min-height: 0;
  }

  .queue-card.no-dev-tools-card {
    height: auto;
  }

  .queue-card-body {
    gap: 10px;
    padding: 10px;
  }

  .queue-card-top {
    min-height: 42px;
  }

  .queue-card-top strong,
  .queue-title-link {
    font-size: 1.05rem;
  }

  .sec-mini-meter-grid,
  .sec-option-grid {
    grid-template-columns: 1fr;
  }

  .queue-dev-actions button,
  .sec-dev-actions button {
    flex-basis: 100%;
  }
}

@keyframes queue-meter-shimmer {
  from {
    background-position: 180% 0;
  }

  to {
    background-position: -40% 0;
  }
}
</style>
