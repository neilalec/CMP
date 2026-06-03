<script setup>
defineProps({
  playersInQueue: {
    type: Number,
    required: true
  },
  maxPlayers: {
    type: Number,
    required: true
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
  isQueueFull: {
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
  isDev: {
    type: Boolean,
    required: true
  }
})

const emit = defineEmits(['join-queue', 'leave-queue', 'seed-queue', 'clear-queue'])
</script>

<template>
  <section class="queue-column">
    <h1>20vs20</h1>

    <div class="queue-status">
      <p class="queue-status-line">
        <span class="queue-status-text">Players in queue {{ playersInQueue }}/{{ maxPlayers }}</span>
        <span class="queue-indicator" aria-label="Queue status">
          <span
            class="queue-spinner"
            :class="{ 'is-hidden': !inQueue || matchAcceptActive }"
            aria-hidden="true"
          ></span>
          <span
            class="queue-tick"
            :class="{ 'is-hidden': !matchAcceptActive }"
            aria-hidden="true"
          >&#10003;</span>
        </span>
      </p>
    </div>

    <button
      v-if="!inQueue"
      @click="emit('join-queue')"
      :disabled="loading || isInLobby || isQueueFull || (isInGroup && !isGroupLeader) || !hasSteamId"
    >
      {{
        isInLobby
          ? "You're in a lobby"
          : !hasSteamId
            ? 'Set Steam ID in Profile'
          : isInGroup && !isGroupLeader
            ? "Group leader only"
          : isQueueFull
            ? 'Queue is full'
            : (loading
              ? 'Processing...'
              : (isInGroup && isGroupLeader
                ? `Queue as Group of ${groupMemberCount}`
                : 'Join Queue'))
      }}
    </button>

    <button
      v-if="inQueue"
      @click="emit('leave-queue')"
      :disabled="loading || (isInGroup && !isGroupLeader)"
    >
      {{
        isInGroup && !isGroupLeader
          ? 'Leave Group to Exit'
          : isInGroup && isGroupLeader
            ? `Leave Queue as Group of ${groupMemberCount}`
            : 'Leave Queue'
      }}
    </button>

    <button
      v-if="isDev"
      @click="emit('seed-queue')"
      :disabled="loading"
    >
      Seed Queue ({{ maxPlayers - 2 }})
    </button>

    <button
      v-if="isDev"
      @click="emit('clear-queue')"
      :disabled="loading"
    >
      Clear Queue
    </button>
  </section>
</template>

<style scoped>
.queue-column {
  width: 100%;
  text-align: center;
}

.queue-column h1 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: inherit;
  font-weight: 500;
}

.queue-status {
  text-align: center;
  margin-bottom: 2rem;
  color: inherit;
}

.queue-status-line {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
}

.queue-status-text {
  display: inline-block;
  text-align: center;
}

.queue-indicator {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 12px;
  height: 12px;
  margin-left: 8px;
  vertical-align: -2px;
  position: relative;
}

.queue-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  flex: 0 0 12px;
  box-sizing: border-box;
  border: 2px solid rgba(255, 255, 255, 0.25);
  border-top-color: rgba(255, 255, 255, 0.8);
  border-radius: 50%;
  animation: queue-spin 0.9s linear infinite;
  position: absolute;
  inset: 0;
}

.queue-tick {
  display: inline-block;
  font-size: 16px;
  line-height: 12px;
  font-weight: 800;
  color: #7ed957;
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
}

.queue-spinner.is-hidden {
  visibility: hidden;
  animation: none;
}

.queue-tick.is-hidden {
  visibility: hidden;
}

@keyframes queue-spin {
  to {
    transform: rotate(360deg);
  }
}

button {
  display: block;
  width: 200px;
  margin: 1rem auto;
  padding: 0.8rem;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

button:hover {
  background: #4a4f56;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 768px) {
  button {
    width: min(100%, 260px);
  }
}

@media (max-width: 480px) {
  .queue-status-line {
    flex-wrap: wrap;
  }
}
</style>
