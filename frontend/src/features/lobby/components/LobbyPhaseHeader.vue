<script setup>
defineProps({
  phaseTitle: {
    type: String,
    required: true
  },
  activeCountdownLabel: {
    type: String,
    required: true
  },
  activeCountdown: {
    type: Number,
    default: null
  },
  announcement: {
    type: String,
    default: ''
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

defineEmits(['pause', 'skip', 'prev', 'leave', 'delete'])
</script>

<template>
  <div class="lobby-header">
    <h1 class="lobby-title">{{ phaseTitle }}</h1>
    <div class="countdown-slot">
      <p class="countdown" :class="{ 'is-hidden': activeCountdown === null }">
        {{ activeCountdownLabel }} {{ activeCountdown ?? 0 }}s
      </p>
      <p v-if="announcement" class="lobby-announcement">
        {{ announcement }}
      </p>
      <div class="lobby-actions action-row">
        <button class="leave-lobby-button" @click="$emit('leave')">
          Leave
        </button>
      </div>
      <section v-if="canAdmin && (showPauseButton || isDev)" class="admin-lobby-controls window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Admin</span>
          <span class="window-titlebar-meta">Lobby</span>
        </div>
        <div class="admin-lobby-body">
          <button v-if="showPauseButton" class="pause-button" @click="$emit('pause')">
            {{ isCountdownPaused ? 'Unpause' : 'Pause' }}
          </button>
          <button v-if="isDev" class="skip-button" @click="$emit('prev')">
            Previous
          </button>
          <button class="skip-button" @click="$emit('skip')">
            Skip
          </button>
          <button class="delete-lobby-button" @click="$emit('delete')">
            Delete Lobby
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.lobby-header {
  width: 100%;
  padding: 18px clamp(14px, 3vw, 24px) 0;
}

.lobby-title {
  color: inherit;
  font-weight: 750;
  margin: 10px 0 12px;
  text-align: center;
  font-size: clamp(2rem, 4.4vw, 4rem);
  line-height: 1.02;
  letter-spacing: -0.035em;
}

.countdown {
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

.countdown.is-hidden {
  visibility: hidden;
}

.countdown-slot {
  min-height: 92px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.lobby-announcement {
  margin: 0.4rem 0 0;
  color: var(--accent-strong);
  font-weight: 600;
  text-align: center;
}

.countdown-slot .countdown {
  margin-top: 0;
}

.lobby-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: center;
  margin-top: 10px;
}

.lobby-actions button {
  min-width: 138px;
}

.admin-lobby-controls {
  width: min(100%, 520px);
  margin-top: 10px;
  overflow: hidden;
}

.admin-lobby-body {
  display: flex;
  justify-content: center;
  gap: 8px;
  padding: 10px;
  flex-wrap: wrap;
  background: var(--panel-bg-muted);
}

.admin-lobby-body button {
  min-width: 110px;
  margin: 0;
}

.pause-button,
.skip-button,
.leave-lobby-button {
  margin-top: 0.5rem;
  min-height: 40px;
  padding: 0.62rem 1rem;
  background: var(--control-bg);
  color: inherit;
  border: 1px solid var(--control-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-weight: 800;
  transition: background-color 0.12s ease, border-color 0.12s ease, transform 0.08s ease;
  box-shadow: var(--surface-shadow);
}

.pause-button {
  background: var(--accent-soft);
  border-color: var(--accent-border);
  color: var(--accent-strong);
}

.leave-lobby-button {
  background: var(--danger-soft);
  border-color: var(--danger);
  color: var(--danger);
}

.delete-lobby-button {
  background: var(--danger);
  border-color: var(--danger);
  color: #fff;
}

.pause-button:hover,
.skip-button:hover,
.leave-lobby-button:hover,
.delete-lobby-button:hover {
  background: var(--control-bg-hover);
  transform: translateY(-1px);
}

@media (max-width: 640px) {
  .lobby-title {
    margin-top: 18px;
  }

  .lobby-actions,
  .admin-lobby-body {
    width: 100%;
  }

  .lobby-actions button,
  .admin-lobby-body button {
    width: 100%;
  }
}
</style>
