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
  isAdmin: {
    type: Boolean,
    default: false
  },
  getLobbyLabel: {
    type: Function,
    required: true
  }
})

const emit = defineEmits(['join-lobby', 'delete-lobby'])
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
                class="open-lobby info-row is-roomy"
            >
              <div class="open-lobby-info info-stack">
                <strong>{{ getLobbyLabel(lobby) }}</strong>
                <span class="info-row-meta">{{ lobby.players.length }}/{{ lobby.max_players }}</span>
              </div>
              <div class="open-lobby-actions">
                <button
                  v-if="isAdmin"
                  class="delete-button"
                  @click="emit('delete-lobby', lobby.lobby_id)"
                  :disabled="loading"
                >
                  Delete
                </button>
                <button
                  @click="emit('join-lobby', lobby.lobby_id)"
                  :disabled="loading || isInLobby"
                >
                  {{ isInLobby ? "You're in a Lobby" : 'Join Lobby' }}
                </button>
              </div>
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
                class="open-lobby info-row is-roomy"
            >
              <div class="open-lobby-info info-stack">
                <strong>{{ getLobbyLabel(lobby) }}</strong>
                <span class="info-row-meta">{{ lobby.players.length }}/{{ lobby.max_players }}</span>
              </div>
              <div v-if="isAdmin" class="open-lobby-actions">
                <button
                  class="delete-button"
                  @click="emit('delete-lobby', lobby.lobby_id)"
                  :disabled="loading"
                >
                  Delete
                </button>
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
  margin-bottom: 10px;
}

.open-lobby-info {
  text-align: left;
  color: inherit;
  font-size: 0.95em;
}

.open-lobby-actions {
  display: flex;
  align-items: center;
  gap: 8px;
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

.delete-button {
  background: color-mix(in srgb, var(--danger-soft) 88%, var(--panel-bg) 12%);
  color: var(--danger);
  border-color: color-mix(in srgb, var(--danger) 28%, var(--surface-border));
}

button:disabled {
  background: var(--control-bg-active);
  color: var(--text-muted);
  border-color: var(--control-border);
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

  .open-lobby-actions {
    width: 100%;
    flex-direction: column;
  }

  button {
    width: min(100%, 260px);
    margin-inline: auto;
  }
}
</style>
