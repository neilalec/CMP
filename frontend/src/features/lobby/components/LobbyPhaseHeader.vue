<script setup>
import { computed } from 'vue';

const props = defineProps({
  activeCountdownLabel: {
    type: String,
    required: true
  },
  activeCountdown: {
    type: Number,
    default: null
  },
  connectedCount: {
    type: Number,
    default: 0
  },
  totalPlayers: {
    type: Number,
    default: 0
  },
  requiredAfterGraceCount: {
    type: Number,
    default: 0
  },
  readyPercent: {
    type: Number,
    default: 95
  },
  readyThresholdSeconds: {
    type: Number,
    default: 300
  },
  readyGraceSeconds: {
    type: Number,
    default: 600
  },
  readyGraceRemainingSeconds: {
    type: Number,
    default: null
  },
  announcement: {
    type: String,
    default: ''
  },
  step: {
    type: Number,
    default: 0
  },
  showPauseButton: {
    type: Boolean,
    default: false
  },
  isCountdownPaused: {
    type: Boolean,
    default: false
  },
  canAdmin: {
    type: Boolean,
    default: false
  },
  isDev: {
    type: Boolean,
    default: false
  }
})

defineEmits(['pause', 'skip', 'prev', 'delete'])

const showCountdownTitle = computed(() => props.activeCountdown !== null)

const phaseTitle = computed(() => {
  if (showCountdownTitle.value) {
    return `${props.activeCountdownLabel} ${props.activeCountdown ?? 0}s`
  }
  if (props.step === 5) return 'SCORE'
  if (props.step === 4) return 'LIVE'
  if (props.step === 3) return 'JOIN SERVER'
  if (props.step === 2) return 'MAP VOTE'
  return 'LOBBY'
})

const phaseTitleClass = computed(() => ({
  'is-map-selected': props.activeCountdownLabel === 'Map selected in' || props.step === 2,
  'is-force-roll': props.activeCountdownLabel === 'Force Roll in' || props.step === 3,
  'is-live': props.step === 4,
  'is-scoreboard': props.step === 5
}))

const statusSentence = computed(() => {
  const announcement = String(props.announcement || '').trim()
  if (announcement && announcement.toLowerCase() !== 'live') return announcement

  if (props.step === 5) return 'Score captured. Review the final result.'
  if (props.step === 4) return 'Match is live. The scoreboard will appear when the round ends.'
  if (props.step === 3) {
    const totalPlayers = Math.max(0, props.totalPlayers || 0)
    const connectedCount = Math.max(0, Math.min(props.connectedCount || 0, totalPlayers))
    const requiredCount = Math.max(0, Math.min(props.requiredAfterGraceCount || 0, totalPlayers))
    const thresholdSeconds = Math.max(0, props.readyThresholdSeconds || 0)
    const graceSeconds = Math.max(0, props.readyGraceSeconds || 0)
    const remainingSeconds = props.readyGraceRemainingSeconds === null
      ? graceSeconds
      : Math.max(0, props.readyGraceRemainingSeconds || 0)
    const forceStatus = remainingSeconds > 0
      ? `force rolling after ${graceSeconds}s (${remainingSeconds}s remaining)`
      : `force rolling now that ${graceSeconds}s have passed`
    return `Join the server, ${connectedCount}/${totalPlayers} connected. Rolling live once everyone has joined, or once ${requiredCount}/${totalPlayers} (${props.readyPercent}%) have joined after ${thresholdSeconds}s; ${forceStatus}.`
  }
  if (props.step === 2) return 'Vote for the next map before the timer ends.'
  return 'Lobby details are syncing.'
})
</script>

<template>
  <div class="lobby-header">
    <div class="countdown-slot">
      <div class="phase-title-row">
        <div class="phase-title-spacer" aria-hidden="true"></div>
        <p class="phase-title countdown" :class="phaseTitleClass">
          {{ phaseTitle }}
        </p>
        <div v-if="canAdmin" class="admin-phase-controls" aria-label="Lobby admin controls">
          <div class="admin-phase-buttons">
            <button
              v-if="showPauseButton"
              class="phase-admin-button"
              type="button"
              @click="$emit('pause')"
            >
              {{ isCountdownPaused ? 'Resume' : 'Pause' }}
            </button>
            <button v-if="isDev" class="phase-admin-button" type="button" @click="$emit('prev')">
              Back
            </button>
            <button class="phase-admin-button" type="button" @click="$emit('skip')">
              Forward
            </button>
          </div>
          <button class="delete-lobby-button" type="button" @click="$emit('delete')">
            Delete Lobby
          </button>
        </div>
      </div>
      <p class="lobby-announcement">
        {{ statusSentence }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.lobby-header {
  width: 100%;
  padding: 18px clamp(14px, 3vw, 24px) 0;
}

.phase-title {
  display: block;
  font-size: 0.95rem;
  color: var(--accent-strong);
  font-weight: 800;
  margin: 1rem auto 0;
  text-align: center;
  width: 100%;
  max-width: 520px;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}

.phase-title-row {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(160px, 1fr) auto minmax(160px, 1fr);
  align-items: start;
  column-gap: 12px;
}

.phase-title-spacer {
  min-width: 0;
}

.phase-title.is-map-selected,
.phase-title.is-force-roll,
.phase-title.is-live,
.phase-title.is-scoreboard {
  max-width: 620px;
  padding: 0.72rem 1.2rem;
  border: 1px solid color-mix(in srgb, var(--accent-border) 72%, var(--surface-border) 28%);
  border-radius: var(--radius-md);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.3), transparent 48%),
    linear-gradient(90deg, color-mix(in srgb, var(--chrome-blue) 48%, transparent), color-mix(in srgb, var(--chrome-green) 45%, transparent));
  box-shadow:
    inset 1px 1px 0 rgba(255, 255, 255, 0.42),
    inset -1px -1px 0 rgba(34, 32, 24, 0.14),
    2px 2px 0 rgba(76, 69, 58, 0.16);
  color: var(--text-main);
  font-family: var(--font-display);
  font-size: clamp(1.25rem, 2vw, 1.72rem);
  letter-spacing: 0.018em;
  text-shadow:
    0 1px 0 rgba(255, 255, 255, 0.24),
    0 3px 10px rgba(93, 86, 73, 0.14);
}

.countdown-slot {
  min-height: 108px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
}

.lobby-announcement {
  min-height: 1.4rem;
  margin: 2rem 0 0;
  color: var(--accent-strong);
  font-weight: 600;
  text-align: center;
  line-height: 1.35;
  max-width: 760px;
}

.countdown-slot .phase-title {
  margin-top: 0;
}

.admin-phase-controls {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 6px;
  justify-self: start;
  min-width: 150px;
}

.admin-phase-buttons {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(72px, 1fr));
  gap: 6px;
}

.phase-admin-button,
.delete-lobby-button {
  min-height: 32px;
  padding: 0.45rem 0.62rem;
  background: var(--control-bg);
  color: inherit;
  border: 1px solid var(--control-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-weight: 700;
  font-size: 0.78rem;
  transition: background-color 0.12s ease, border-color 0.12s ease, transform 0.08s ease;
  box-shadow: var(--surface-shadow);
}

.delete-lobby-button {
  width: 100%;
  color: var(--danger);
}

.phase-admin-button:hover,
.delete-lobby-button:hover {
  background: var(--control-bg-hover);
  transform: translateY(-1px);
}

@media (max-width: 640px) {
  .phase-title-row {
    grid-template-columns: 1fr;
    justify-items: center;
    row-gap: 10px;
  }

  .phase-title-spacer {
    display: none;
  }

  .admin-phase-controls {
    justify-self: center;
    width: min(100%, 260px);
  }
}
</style>
