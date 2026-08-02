<script setup>
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
  }
})

const emit = defineEmits(['accept', 'close', 'dismiss'])

const displayName = (player) => props.playerProfiles?.[player]?.display_name || player
</script>

<template>
  <div v-if="active" class="match-accept-overlay">
    <div class="match-accept-modal window-panel">
      <div class="match-accept-header window-titlebar">
        <span class="window-titlebar-label">{{ isCancelled ? 'Cancelled' : 'Match Found' }}</span>
        <span v-if="!isCancelled" class="window-titlebar-meta">{{ countdown ?? 0 }}s</span>
        <button
          class="match-accept-close"
          type="button"
          aria-label="Close match found"
          @click="emit('close')"
        >
          x
        </button>
      </div>
      <div class="match-accept-body">
        <p v-if="isCancelled">
          {{ cancelReason || 'Not everyone accepted.' }}
        </p>
        <p v-else class="match-accept-progress">
          {{ acceptedCount }}/{{ requiredCount }} accepted
        </p>
        <div v-if="!isCancelled" class="match-player-groups">
          <div class="match-player-list">
            <span class="match-player-list-label">Accepted</span>
            <span
              v-for="player in acceptedPlayers"
              :key="`accepted-${player}`"
              class="match-player-chip is-accepted"
              :title="player"
            >
              {{ displayName(player) }}
            </span>
            <span v-if="!acceptedPlayers.length" class="match-player-empty">None</span>
          </div>
          <div class="match-player-list">
            <span class="match-player-list-label">Waiting</span>
            <span
              v-for="player in waitingPlayers"
              :key="`waiting-${player}`"
              class="match-player-chip"
              :title="player"
            >
              {{ displayName(player) }}
            </span>
            <span v-if="!waitingPlayers.length" class="match-player-empty">Ready</span>
          </div>
        </div>
        <button
          class="match-accept-button"
          type="button"
          :disabled="!isCancelled && (loading || hasAccepted)"
          @click="isCancelled ? emit('dismiss') : emit('accept')"
        >
          {{
            isCancelled
              ? 'OK'
              : (hasAccepted
                ? 'Accepted'
                : (loading ? 'Accepting...' : 'Accept'))
          }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.match-accept-overlay {
  position: fixed;
  inset: 0;
  background: var(--overlay);
  display: flex;
  align-items: stretch;
  justify-content: center;
  z-index: 40;
  padding: clamp(12px, 3vw, 24px);
  overflow-y: auto;
}

.match-accept-modal {
  width: min(100%, 980px);
  max-height: calc(100dvh - clamp(24px, 6vw, 48px));
  margin: auto;
  text-align: center;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  position: relative;
}

.match-accept-header {
  padding-right: 48px;
}

.match-accept-close {
  position: absolute;
  top: 3px;
  right: 6px;
  width: 24px;
  height: 24px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 1px solid var(--control-border);
  background: var(--control-bg);
  color: var(--text-main);
  box-shadow: var(--surface-shadow);
  font-size: 0.8rem;
  font-weight: 700;
  line-height: 1;
}

.match-accept-close:hover {
  background: var(--control-bg-hover);
}

.match-accept-body {
  padding: clamp(16px, 3vw, 24px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.match-accept-modal p {
  margin: 0;
}

.match-accept-progress {
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-weight: 700;
}

.match-player-groups {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  text-align: left;
  min-height: 0;
  overflow: hidden;
}

.match-player-list {
  min-height: 120px;
  max-height: min(42dvh, 360px);
  padding: 12px;
  border-radius: var(--radius-md);
  background: var(--panel-bg-muted);
  border: 1px solid var(--surface-border);
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 8px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.match-player-list-label {
  width: 100%;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.match-player-chip,
.match-player-empty {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  background: var(--control-bg);
  color: var(--text-main);
  font-size: 0.78rem;
  font-weight: 700;
}

.match-player-chip.is-accepted {
  background: var(--success-soft);
  color: var(--success);
}

.match-player-empty {
  background: transparent;
  border: 1px dashed var(--surface-border);
  color: var(--text-muted);
}

.match-accept-button {
  flex: 0 0 auto;
  margin-top: 16px;
  width: 100%;
}

@media (max-width: 480px) {
  .match-player-groups {
    grid-template-columns: 1fr;
  }

  .match-player-list {
    max-height: min(28dvh, 240px);
  }
}
</style>
