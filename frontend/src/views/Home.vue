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
  // Initial queue sync
  await queueStore.syncWithServer();

  // Listen for queue updates
  socketStore.on(SOCKET_EVENTS.QUEUE.UPDATE, (data) => {
    queueStore.updateQueueState({
      ...data,
      inQueue: data.queue?.includes(authStore.username)
    });
  });

  // Listen for lobby creation
  socketStore.on(SOCKET_EVENTS.LOBBY.CREATED, (data) => {
    if (data?.lobby_id) {
      queueStore.resetQueue();
      router.push(`/lobby/${data.lobby_id}`);
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
  padding: 1rem;
}

button {
  display: block;
  width: 200px;
  margin: 1rem auto;
  padding: 0.5rem;
  cursor: pointer;
}

button:disabled {
  opacity: 0.5;
}
.countdown {
  font-size: 1.2em;
  color: #4CAF50;
  font-weight: bold;
  margin-top: 1rem;
}
</style>
