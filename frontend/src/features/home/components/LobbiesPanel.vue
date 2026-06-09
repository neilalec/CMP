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
  getLobbyLabel: {
    type: Function,
    required: true
  }
})

const emit = defineEmits(['join-lobby'])
</script>

<template>
  <section class="queue-column">
    <div class="lobbies-grid">
      <div class="lobbies-column window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Joinable</span>
          <span class="window-titlebar-meta">{{ openLobbies.length }}</span>
        </div>
        <div class="lobbies-column-body panel-body">
          <div v-if="openLobbies.length" class="open-lobbies">
            <div
              v-for="lobby in openLobbies"
                :key="lobby.lobby_id"
                class="open-lobby"
            >
              <div class="open-lobby-info">
                <strong>{{ getLobbyLabel(lobby) }}</strong>
                <span>{{ lobby.players.length }}/{{ lobby.max_players }}</span>
              </div>
              <button
                @click="emit('join-lobby', lobby.lobby_id)"
                :disabled="loading || isInLobby"
              >
                {{ isInLobby ? "You're in a Lobby" : 'Join Lobby' }}
              </button>
            </div>
          </div>
          <p v-else class="empty-state">None</p>
        </div>
      </div>

      <div class="lobbies-column window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Active</span>
          <span class="window-titlebar-meta">{{ activeLobbies.length }}</span>
        </div>
        <div class="lobbies-column-body panel-body">
          <div v-if="activeLobbies.length" class="open-lobbies">
            <div
              v-for="lobby in activeLobbies"
                :key="lobby.lobby_id"
                class="open-lobby"
            >
              <div class="open-lobby-info">
                <strong>{{ getLobbyLabel(lobby) }}</strong>
                <span>{{ lobby.players.length }}/{{ lobby.max_players }}</span>
              </div>
            </div>
          </div>
          <p v-else class="empty-state">None</p>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.queue-column {
  width: 100%;
  text-align: left;
}

.open-lobbies {
  width: 100%;
  margin: 0 auto;
  text-align: center;
}

.lobbies-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
  width: 100%;
  margin-top: 0;
}

.lobbies-column {
  width: 100%;
  overflow: hidden;
}

.open-lobby {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  background: var(--panel-bg-strong);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-sm);
  margin-bottom: 10px;
  box-shadow: var(--surface-shadow);
}

.open-lobby-info {
  text-align: left;
  color: inherit;
  font-size: 0.95em;
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.open-lobby-info span {
  color: var(--text-muted);
  font-size: 0.86rem;
}

button {
  display: block;
  width: auto;
  min-width: 126px;
  margin: 0;
  padding: 0.7rem 0.95rem;
  background: var(--accent-soft);
  color: var(--accent-strong);
  border: 1px solid var(--accent-border);
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-weight: 800;
  transition: background-color 0.12s ease, transform 0.08s ease;
  box-shadow: var(--surface-shadow);
}

button:hover {
  background: var(--control-bg-hover);
  transform: translateY(-1px);
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
    margin-inline: auto;
  }
}
</style>
