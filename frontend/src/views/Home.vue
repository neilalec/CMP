<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { useQueueStore } from '../stores/queueStore';
import { useSocketStore } from '../stores/socketStore';
import { useAuthStore } from '../stores/authStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';

const router = useRouter();
const queueStore = useQueueStore();
const socketStore = useSocketStore();
const authStore = useAuthStore();
const loading = ref(false);

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
  loading.value = true;
  try {
    await queueStore.joinQueue(authStore.username);
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
  <div class="queue-container">
    <h1>Game Queue</h1>
    
    <div class="queue-status">
      <p v-if="queueStore.playersInQueue > 0">
        Players in queue: {{ queueStore.playersInQueue }}
      </p>
      <p v-else>
        No players in queue currently.
      </p>
      <p v-if="queueStore.countdown" class="countdown">
        Match starting in: {{ queueStore.countdown }}s
      </p>
    </div>

    <button 
      v-if="!queueStore.inQueue"
      @click="joinQueue" 
      :disabled="loading"
    >
      {{ loading ? 'Processing...' : 'Join Queue' }}
    </button>

    <button 
      v-if="queueStore.inQueue" 
      @click="leaveQueue"
      :disabled="loading"
    >
      Leave Queue
    </button>
  </div>
</template>

<style scoped>
.queue-container {
  max-width: 400px;
  margin: 2rem auto;
  padding: 2rem;
  background: #2d2d2d;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

.queue-container h1 {
  text-align: center;
  margin-bottom: 2rem;
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
