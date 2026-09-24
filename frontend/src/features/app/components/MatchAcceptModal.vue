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
  <div v-if="active" class="match-accept-overlay cmp-overlay">
    <div class="match-accept-modal cmp-surface cmp-surface--floating">
      <div class="match-accept-header cmp-panel-header">
        <strong class="cmp-heading">{{ isCancelled ? 'Cancelled' : 'Match Found' }}</strong>
        <span v-if="!isCancelled" class="cmp-panel-meta">{{ countdown ?? 0 }}s</span>
        <button
          class="match-accept-close cmp-button cmp-button--secondary"
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
          class="match-accept-button cmp-button cmp-button--primary"
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
  border-radius: var(--cmp-radius-md);
}

.match-accept-header {
  padding-right: 48px;
  min-height: 40px;
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
  font-size: 0.8rem;
  font-weight: 700;
  line-height: 1;
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
  color: var(--cmp-primary-hover);
  font-family: var(--cmp-font-mono);
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
  border-radius: var(--cmp-radius-md);
  background: var(--cmp-surface-raised);
  border: 1px solid var(--cmp-border);
  display: flex;
  flex-wrap: wrap;
  align-content: flex-start;
  gap: 8px;
  overflow-y: auto;
  scrollbar-width: thin;
}

.match-player-list-label {
  width: 100%;
  color: var(--cmp-text-muted);
  font-family: var(--cmp-font-mono);
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
  border-radius: var(--cmp-radius-sm);
  background: var(--cmp-surface-strong);
  color: var(--cmp-text);
  font-size: 0.78rem;
  font-weight: 700;
}

.match-player-chip.is-accepted {
  background: color-mix(in srgb, var(--cmp-success) 18%, var(--cmp-surface-raised));
  color: var(--cmp-success);
}

.match-player-empty {
  background: transparent;
  border: 1px dashed var(--cmp-border);
  color: var(--cmp-text-muted);
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
