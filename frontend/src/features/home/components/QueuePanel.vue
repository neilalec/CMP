<script setup>
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
  getQueueProgressPercent: {
    type: Function,
    required: true
  },
  isModeQueueFull: {
    type: Function,
    required: true
  }
})

const emit = defineEmits(['join-queue', 'leave-queue', 'seed-queue', 'clear-queue'])

const getQueueTitle = (queueMode) => {
  if (queueMode.id === 'hotdrop') return 'Hotdrop Tournament Layers'
  return 'Vanilla Skirmish Layers'
}

const getQueueStatusLabel = (queueMode) => {
  if (props.inQueue && props.currentQueueMode === queueMode.id) return 'Queued'
  if (props.inQueue && props.currentQueueMode !== queueMode.id) return 'Other queue'
  if (props.isInLobby) return 'In lobby'
  if (!props.serverAvailable) return 'Server busy'
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
  if (!props.serverAvailable) return 'Server busy'
  if (!props.hasSteamId) return 'Set Steam ID in Profile'
  if (props.isInGroup && !props.isGroupLeader) return 'Group leader only'
  if (props.inQueue && props.currentQueueMode !== queueMode.id) return 'Queued elsewhere'
  if (props.isModeQueueFull(queueMode.id)) return 'Queue is full'
  if (props.loading) return 'Processing...'
  if (props.isInGroup && props.isGroupLeader) return `Queue as Group of ${props.groupMemberCount}`
  return 'Join Queue'
}

const isJoinDisabled = (queueMode) => (
  props.loading
  || props.isInLobby
  || props.inQueue
  || !props.serverAvailable
  || props.isModeQueueFull(queueMode.id)
  || (props.isInGroup && !props.isGroupLeader)
  || !props.hasSteamId
)

const isLeaveDisabled = () => props.loading || (props.isInGroup && !props.isGroupLeader)
</script>

<template>
  <section class="queue-board">
    <div class="queue-grid">
      <article
        v-for="queueMode in queueModes"
        :key="queueMode.id"
        :class="['queue-card window-panel', { 'is-active': currentQueueMode === queueMode.id }]"
      >
        <div class="window-titlebar">
          <span class="window-titlebar-label">{{ queueMode.teamSize }}v{{ queueMode.teamSize }}</span>
          <span class="window-titlebar-meta">{{ getQueueStatusLabel(queueMode) }}</span>
        </div>
        <div class="queue-card-body">
          <div class="queue-card-top">
            <strong>{{ getQueueTitle(queueMode) }}</strong>
          </div>

          <div class="queue-progress-row">
            <div class="queue-meter" aria-hidden="true">
              <span :style="{ width: `${getQueueProgressPercent(queueMode.id)}%` }"></span>
            </div>
            <span class="queue-counter">{{ queueMode.playersInQueue }}/{{ queueMode.maxPlayers }}</span>
          </div>

          <button
            v-if="!(inQueue && currentQueueMode === queueMode.id)"
            class="queue-action"
            :disabled="isJoinDisabled(queueMode)"
            @click="emit('join-queue', queueMode.id)"
          >
            {{ getPrimaryLabel(queueMode) }}
          </button>

          <button
            v-else
            class="queue-action is-danger"
            :disabled="isLeaveDisabled()"
            @click="emit('leave-queue', queueMode.id)"
          >
            {{ getPrimaryLabel(queueMode) }}
          </button>

          <div v-if="canManageQueueTools" class="queue-dev-actions">
            <button type="button" @click="emit('seed-queue', queueMode.id)" :disabled="loading">
              Seed {{ queueMode.label }}
            </button>
            <button type="button" @click="emit('clear-queue', queueMode.id)" :disabled="loading">
              Clear {{ queueMode.shortLabel }}
            </button>
          </div>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.queue-board {
  width: 100%;
  display: grid;
  gap: 16px;
}

.queue-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(240px, 320px));
  justify-content: center;
  gap: 28px;
}

.queue-card {
  overflow: hidden;
  min-height: 280px;
}

.queue-card.is-active {
  border-color: var(--accent-border);
  background: var(--panel-bg-strong);
}

.queue-card-body {
  padding: 16px;
  display: grid;
  gap: 18px;
  align-content: start;
}

.queue-card-top {
  min-height: 72px;
}

.queue-card-top strong {
  display: block;
  margin: 0;
  font-family: var(--font-mono);
  font-size: 1.45rem;
  line-height: 1.15;
}

.queue-progress-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}

.queue-counter {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.76rem;
  font-weight: 700;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.queue-meter {
  height: 10px;
  width: 100%;
  overflow: hidden;
  border-radius: var(--radius-sm);
  background: var(--panel-bg-muted);
  border: 1px solid var(--surface-border);
  box-shadow: var(--inset-shadow);
}

.queue-meter span {
  display: block;
  height: 100%;
  background: linear-gradient(90deg, var(--accent), var(--accent-strong));
}

.queue-action {
  width: 100%;
}

.queue-action.is-danger {
  background: var(--danger-soft);
  border-color: var(--danger);
  color: var(--danger);
}

.queue-dev-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.queue-dev-actions button {
  flex: 1 1 180px;
}

@media (max-width: 900px) {
  .queue-grid {
    grid-template-columns: 1fr;
  }
}
</style>
