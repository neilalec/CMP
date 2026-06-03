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
  isDev: {
    type: Boolean,
    default: false
  }
})

defineEmits(['pause', 'skip', 'prev', 'leave'])
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
      <div class="countdown-actions">
        <button v-if="showPauseButton" class="pause-button" @click="$emit('pause')">
          {{ isCountdownPaused ? 'Unpause Countdown' : 'Pause Countdown' }}
        </button>
        <button v-if="isDev" class="skip-button" @click="$emit('prev')">
          Previous Phase
        </button>
        <button v-if="showPauseButton || isDev" class="skip-button" @click="$emit('skip')">
          Skip Phase
        </button>
        <button class="leave-lobby-button" @click="$emit('leave')">
          Leave Lobby
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lobby-header {
  width: 100%;
}

.lobby-title {
  color: inherit;
  font-weight: 500;
  margin: 28px 0 12px;
  text-align: center;
}

.countdown {
  display: block;
  font-size: 1.2em;
  color: #4CAF50;
  font-weight: bold;
  margin: 1rem auto 0;
  text-align: center;
  width: 100%;
  max-width: 520px;
}

.countdown.is-hidden {
  visibility: hidden;
}

.countdown-slot {
  min-height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.lobby-announcement {
  margin: 0.4rem 0 0;
  color: #7ed957;
  font-weight: 600;
  text-align: center;
}

.countdown-slot .countdown {
  margin-top: 0;
}

.countdown-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.countdown-actions button {
  min-width: 148px;
}

.pause-button,
.skip-button,
.leave-lobby-button {
  margin-top: 0.5rem;
  padding: 0.6rem 1.2rem;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.pause-button:hover,
.skip-button:hover,
.leave-lobby-button:hover {
  background: #4a4f56;
}

@media (max-width: 640px) {
  .lobby-title {
    margin-top: 18px;
  }

  .countdown-actions {
    width: 100%;
  }

  .countdown-actions button {
    width: 100%;
  }
}
</style>
