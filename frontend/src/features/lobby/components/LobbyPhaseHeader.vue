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
  serverDetails: {
    type: Object,
    default: null
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
  },
  isSpectator: {
    type: Boolean,
    default: false
  },
  adminLiveReadyOverride: {
    type: Boolean,
    default: false
  }
})

defineEmits(['pause', 'skip', 'prev', 'delete', 'force-live-ready'])

const showCountdownTitle = computed(() => props.activeCountdown !== null)

const liveRoundNumber = computed(() => {
  const round = Number(
    props.serverDetails?.matchCurrentRound
    || props.serverDetails?.match_current_round
    || 1
  )
  return Number.isFinite(round) && round > 0 ? Math.round(round) : 1
})

const liveRequiredRounds = computed(() => {
  const required = Number(
    props.serverDetails?.matchRequiredRounds
    || props.serverDetails?.match_required_rounds
    || 2
  )
  return Number.isFinite(required) && required > 0 ? Math.round(required) : 2
})

const liveRoundLabel = computed(() => `LIVE Round ${liveRoundNumber.value}`)

const phaseTitle = computed(() => {
  if (showCountdownTitle.value) {
    return `${props.activeCountdownLabel} ${props.activeCountdown ?? 0}s`
  }
  if (props.step === 5) return 'SCORE'
  if (props.step === 4) return liveRoundLabel.value
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
  const normalizedAnnouncement = announcement.toLowerCase()
  if (
    announcement
    && normalizedAnnouncement !== 'live'
    && !normalizedAnnouncement.startsWith('live round ')
  ) {
    return announcement
  }

  if (props.step === 5) return 'Score captured. Review the final result.'
  if (props.step === 4) {
    return `${liveRoundLabel.value} is being played, round ${liveRoundNumber.value} of ${liveRequiredRounds.value}. The scoreboard will update when this round ends.`
  }
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
          <span v-if="isSpectator" class="spectator-pill">Spectating</span>
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
            <button
              v-if="step === 2 || step === 3"
              class="phase-admin-button"
              type="button"
              :disabled="adminLiveReadyOverride"
              @click="$emit('force-live-ready')"
            >
              {{ adminLiveReadyOverride ? 'Forced Ready' : 'Force Live' }}
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
  color: var(--lobby-emphasis-text, var(--accent-strong));
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
  border: 1px solid var(--phase-title-border);
  border-radius: var(--radius-md);
  background: var(--phase-title-bg);
  box-shadow: var(--phase-title-shadow);
  color: var(--text-main);
  font-family: var(--font-display);
  font-size: clamp(1.25rem, 2vw, 1.72rem);
  letter-spacing: 0.018em;
  text-shadow: var(--phase-title-text-shadow);
  color: var(--lobby-emphasis-text, var(--text-main));
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
  color: var(--lobby-emphasis-text, var(--accent-strong));
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

.spectator-pill {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0 8px;
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  color: var(--accent-strong);
  font-size: 0.76rem;
  font-weight: 900;
}

.phase-admin-button,
.delete-lobby-button {
  min-height: 32px;
  padding: 0.45rem 0.62rem;
  background: var(--button-flat-bg);
  color: var(--button-flat-text);
  border: 1px solid var(--button-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-weight: 700;
  font-size: 0.78rem;
  transition: background-color 0.12s ease, border-color 0.12s ease, box-shadow 0.12s ease, transform 0.08s ease;
  box-shadow: var(--button-shadow);
}

.delete-lobby-button {
  width: 100%;
  color: var(--danger);
}

.phase-admin-button:hover,
.delete-lobby-button:hover {
  background: var(--button-flat-bg-hover);
  border-color: var(--button-border-hover);
  box-shadow: var(--button-hover-shadow);
  transform: translateY(-1px);
}

.phase-admin-button:disabled {
  background: var(--button-disabled-bg);
  color: var(--button-disabled-text);
  cursor: not-allowed;
  transform: none;
}

@media (max-width: 640px) {
  .lobby-header {
    padding: 10px 8px 0;
  }

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

  .countdown-slot {
    min-height: 72px;
  }

  .lobby-announcement {
    margin-top: 1rem;
  }
}

@media (max-width: 420px) {
  .phase-title {
    margin-top: 0.6rem;
    font-size: 0.84rem;
  }

  .phase-title.is-map-selected,
  .phase-title.is-force-roll,
  .phase-title.is-live,
  .phase-title.is-scoreboard {
    padding: 0.58rem 0.7rem;
    font-size: 1.08rem;
  }
}
</style>
