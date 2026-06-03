<script setup>
defineProps({
  openLobbies: {
    type: Array,
    default: () => []
  },
  activeLobbies: {
    type: Array,
    default: () => []
  },
  loading: {
    type: Boolean,
    required: true
  },
  isInLobby: {
    type: Boolean,
    required: true
  },
  maxPlayers: {
    type: Number,
    required: true
  },
  getLobbyLabel: {
    type: Function,
    required: true
  }
})

const emit = defineEmits(['join-lobby'])
</script>

<template>
  <section class="queue-column">
    <h1>Lobbies</h1>
    <div class="lobbies-grid">
      <div class="lobbies-column">
        <h3>Players needed</h3>
        <div v-if="openLobbies.length" class="open-lobbies">
          <div
            v-for="lobby in openLobbies"
            :key="lobby.lobby_id"
            class="open-lobby"
          >
            <div class="open-lobby-info">
              <div>{{ getLobbyLabel(lobby) }}</div>
              <div>Players {{ lobby.players.length }}/{{ maxPlayers }}</div>
            </div>
            <button
              @click="emit('join-lobby', lobby.lobby_id)"
              :disabled="loading || isInLobby"
            >
              {{ isInLobby ? "You're in a Lobby" : 'Join Lobby' }}
            </button>
          </div>
        </div>
        <p v-else class="none-text">None</p>
      </div>

      <div class="lobbies-column">
        <h3>Full and ongoing</h3>
        <div v-if="activeLobbies.length" class="open-lobbies">
          <div
            v-for="lobby in activeLobbies"
            :key="lobby.lobby_id"
            class="open-lobby"
          >
            <div class="open-lobby-info">
              <div>{{ getLobbyLabel(lobby) }}</div>
              <div>Players {{ lobby.players.length }}/{{ maxPlayers }}</div>
            </div>
          </div>
        </div>
        <p v-else class="none-text">None</p>
      </div>
    </div>
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

.queue-column h3 {
  color: inherit;
  margin: 0.8rem 0;
}

.open-lobbies {
  width: 100%;
  margin: 0 auto;
  text-align: center;
}

.lobbies-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 24px;
  width: 100%;
  margin-top: 1rem;
}

.lobbies-column {
  width: 100%;
}

.open-lobby {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: var(--panel-bg);
  border-radius: 6px;
  margin-bottom: 10px;
}

.open-lobby-info {
  text-align: left;
  color: inherit;
  font-size: 0.95em;
}

.none-text {
  color: #888;
  margin-top: 1rem;
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
  .lobbies-grid {
    grid-template-columns: 1fr;
  }

  .open-lobby {
    flex-direction: column;
    align-items: stretch;
    text-align: center;
  }

  .open-lobby-info {
    text-align: center;
  }

  button {
    width: min(100%, 260px);
  }
}
</style>
