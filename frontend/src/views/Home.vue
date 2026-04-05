<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useQueueStore } from '../stores/queueStore';
import { useSocketStore } from '../stores/socketStore';
import { useAuthStore } from '../stores/authStore';
import { useLobbyStore } from '../stores/lobbyStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { useRootStore } from '../stores/rootStore';

const router = useRouter();
const queueStore = useQueueStore();
const socketStore = useSocketStore();
const authStore = useAuthStore();
const lobbyStore = useLobbyStore();
const rootStore = useRootStore();
const loading = ref(false);
const isInLobby = computed(() => {
  return !!lobbyStore.lobbyId || !!localStorage.getItem('currentLobby');
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

  // Listen for queue updates
  socketStore.on(SOCKET_EVENTS.QUEUE.UPDATE, (data) => {
    console.log('Queue update received:', data);
    queueStore.updateQueueState({
      ...data,
      inQueue: data.queue?.includes(authStore.username)
    });
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
</script>

<template>
  <div class="queue-grid content-panel">
    <section class="queue-column">
      <h1>Pickup Game Queue</h1>
      
      <div class="queue-status">
        <p v-if="queueStore.playersInQueue > 0">
          Players in queue: {{ queueStore.playersInQueue }}/2
        </p>
        <p v-else>
          No players in queue currently.
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

    <section class="queue-column">
      <h1>Lobby's Missing Players</h1>
      <div v-if="queueStore.openLobbies.length" class="open-lobbies">
        <div
          v-for="lobby in queueStore.openLobbies"
          :key="lobby.lobby_id"
          class="open-lobby"
        >
          <div class="open-lobby-info">
            <div>Lobby: {{ lobby.lobby_id }}</div>
            <div>Players: {{ lobby.players.length }}/2</div>
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
    </section>
  </div>
</template>

<style scoped>
.queue-grid {
  width: 100%;
  max-width: 900px;
  margin: 1rem auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 24px;
  align-items: start;
}

.queue-column {
  width: 100%;
  text-align: center;
}

.queue-column h1 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: #ffffff;
}

.queue-status {
  text-align: center;
  margin-bottom: 2rem;
  color: #cccccc;
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
  color: #cccccc;
  margin-bottom: 0.8rem;
}

.open-lobby {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  background: #3d3d3d;
  border-radius: 6px;
  margin-bottom: 10px;
}

.open-lobby-info {
  text-align: left;
  color: #ffffff;
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
  color: white;
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
