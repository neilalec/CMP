<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useQueueStore } from '../stores/queueStore';
import { useSocketStore } from '../stores/socketStore';
import { useAuthStore } from '../stores/authStore';
import { useLobbyStore } from '../stores/lobbyStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { useRootStore } from '../stores/rootStore';

const router = useRouter();
const route = useRoute();
const queueStore = useQueueStore();
const socketStore = useSocketStore();
const authStore = useAuthStore();
const lobbyStore = useLobbyStore();
const rootStore = useRootStore();
const loading = ref(false);
const isInLobby = computed(() => {
  return !!lobbyStore.lobbyId || !!localStorage.getItem('currentLobby');
});
const activeView = computed(() => {
  if (route.path === '/queue') return 'queue';
  if (route.path === '/lobbies') return 'lobbies';
  return null;
});

onMounted(async () => {
  console.log('Home component mounted');
  
  // Wait for socket to be ready
  while (!socketStore.isConnected) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  console.log('Socket connected, syncing with server...');

  // Now safe to sync - pass username to get accurate queue status
  await queueStore.syncWithServer(authStore.username);
  try {
    const openLobbies = await socketStore.emit(SOCKET_EVENTS.OPEN_LOBBIES.STATUS);
    if (openLobbies?.openLobbies) {
      queueStore.updateOpenLobbies(openLobbies.openLobbies);
    }
    if (openLobbies?.activeLobbies) {
      queueStore.updateActiveLobbies(openLobbies.activeLobbies);
    }
  } catch (error) {
    // ignore
  }

  // Listen for queue updates
  socketStore.on(SOCKET_EVENTS.QUEUE.UPDATE, (data) => {
    console.log('Queue update received:', data);
    queueStore.updateQueueState({
      ...data,
      inQueue: data.queue?.includes(authStore.username)
    });
  });

  socketStore.on(SOCKET_EVENTS.OPEN_LOBBIES.UPDATE, (data) => {
    if (data?.openLobbies) {
      queueStore.updateOpenLobbies(data.openLobbies);
    }
    if (data?.activeLobbies) {
      queueStore.updateActiveLobbies(data.activeLobbies);
    }
  });

  // Listen for lobby creation
  socketStore.on(SOCKET_EVENTS.LOBBY.CREATED, (data) => {
    console.log('Lobby created event received:', data);
    if (data?.lobby_id) {
      queueStore.resetQueue();
      console.log('Redirecting to lobby:', data.lobby_id);
      router.push(`/lobby/${data.lobby_id}`);
    } else {
      console.error('Invalid lobby data received:', data);
    }
  });
});

onBeforeUnmount(() => {
  socketStore.off(SOCKET_EVENTS.QUEUE.UPDATE);
  socketStore.off(SOCKET_EVENTS.LOBBY.CREATED);
  socketStore.off(SOCKET_EVENTS.OPEN_LOBBIES.UPDATE);
});

const joinQueue = async () => {
  if (isInLobby.value) {
    rootStore.setError('You are already in a lobby. Return to the lobby to continue.');
    return;
  }
  loading.value = true;
  try {
    await queueStore.joinQueue(authStore.username);
  } finally {
    loading.value = false;
  }
};

const joinOpenLobby = async (lobbyId) => {
  if (isInLobby.value) {
    rootStore.setError('You are already in a lobby. Return to the lobby to continue.');
    return;
  }
  loading.value = true;
  try {
    const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.JOIN, {
      lobby_id: lobbyId,
      username: authStore.username,
      allow_new: true
    });
    if (response?.success) {
      localStorage.setItem('currentLobby', lobbyId);
      router.push(`/lobby/${lobbyId}`);
    } else {
      throw new Error(response?.message || 'Failed to join lobby');
    }
  } catch (error) {
    rootStore.setError(error.message || 'Failed to join lobby');
  } finally {
    loading.value = false;
  }
};

const leaveQueue = async () => {
  loading.value = true;
  try {
    await queueStore.leaveQueue(authStore.username);
  } finally {
    loading.value = false;
  }
};

const getLobbyLabel = (lobby) => {
  const captains = lobby?.captains;
  if (captains?.team1 && captains?.team2) {
    return `Team ${captains.team1} vs Team ${captains.team2}`;
  }
  return lobby?.lobby_id || 'Lobby';
};

</script>

<template>
  <div class="home-content content-panel">
      <section v-if="activeView === 'queue'" class="queue-column">
        <h1>Queue</h1>

        <div class="queue-status">
          <p>
            Players in queue {{ queueStore.playersInQueue }}/2
          </p>
          <p v-if="queueStore.countdown" class="countdown">
            Lobby created in: {{ queueStore.countdown }}s
          </p>
        </div>

        <button 
          v-if="!queueStore.inQueue"
          @click="joinQueue" 
          :disabled="loading || isInLobby"
        >
          {{ isInLobby ? 'In Lobby' : (loading ? 'Processing...' : 'Join Queue') }}
        </button>

        <button 
          v-if="queueStore.inQueue" 
          @click="leaveQueue"
          :disabled="loading"
        >
          Leave Queue
        </button>
      </section>

      <section v-else-if="activeView === 'lobbies'" class="queue-column">
        <h1>Lobbies</h1>
        <div class="lobbies-grid">
          <div class="lobbies-column">
            <h3>Players needed</h3>
            <div v-if="queueStore.openLobbies.length" class="open-lobbies">
              <div
                v-for="lobby in queueStore.openLobbies"
                :key="lobby.lobby_id"
                class="open-lobby"
              >
            <div class="open-lobby-info">
              <div>{{ getLobbyLabel(lobby) }}</div>
              <div>Players {{ lobby.players.length }}/2</div>
            </div>
                <button
                  @click="joinOpenLobby(lobby.lobby_id)"
                  :disabled="loading || isInLobby"
                >
                  {{ isInLobby ? 'In Lobby' : 'Join Lobby' }}
                </button>
              </div>
            </div>
            <p v-else class="none-text">None</p>
          </div>

          <div class="lobbies-column">
            <h3>Ongoing</h3>
            <div v-if="queueStore.activeLobbies.length" class="open-lobbies">
              <div
                v-for="lobby in queueStore.activeLobbies"
                :key="lobby.lobby_id"
                class="open-lobby"
              >
            <div class="open-lobby-info">
              <div>{{ getLobbyLabel(lobby) }}</div>
              <div>Players {{ lobby.players.length }}/2</div>
            </div>
              </div>
            </div>
            <p v-else class="none-text">None</p>
          </div>
        </div>
      </section>

      <section v-else class="home-about">
        <h1>Competitive Matchmaking Platform</h1>
        <p>
          The purpose of this web app is to allow players to queue for a competitive Squad match in a straightforward manner
        </p>
      </section>
  </div>
</template>

<style scoped>
.home-content {
  width: 100%;
  max-width: 100%;
  margin: 0;
}

.home-about {
  width: 100%;
  max-width: 100%;
  text-align: center;
  margin: 1rem 0;
}

.queue-column {
  width: 100%;
  text-align: center;
}

.queue-column h1 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: inherit;
}

.queue-status {
  text-align: center;
  margin-bottom: 2rem;
  color: inherit;
}

.queue-status p {
  margin: 0.5rem 0;
}

.countdown {
  font-size: 1.2em;
  color: #4CAF50;
  font-weight: bold;
  margin-top: 1rem;
}

.open-lobbies {
  width: 100%;
  margin: 0 auto;
  text-align: center;
}

.open-lobbies h3 {
  color: inherit;
  margin-bottom: 0.8rem;
}

.queue-column h3 {
  color: inherit;
  margin: 0.8rem 0;
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
  background: #3d3d3d;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

button:hover {
  background: #4d4d4d;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
