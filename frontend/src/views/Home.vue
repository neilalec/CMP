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

  // Listen for queue updates
  socketStore.on(SOCKET_EVENTS.QUEUE.UPDATE, (data) => {
    console.log('Received queue update:', data);
    queueStore.updateQueueState({
      ...data,
      inQueue: data.queue?.includes(authStore.username)
    });
  });

  // Listen for lobby creation
  socketStore.on(SOCKET_EVENTS.LOBBY.CREATED, (data) => {
    console.log('Lobby created:', data);
    if (!data || !data.lobby_id) {
      console.error('Invalid lobby data received:', data);
      return;
    }

    try {
      queueStore.resetQueue();
      router.push(`/lobby/${data.lobby_id}`);
    } catch (error) {
      console.error('Failed to navigate to lobby:', error);
    }
  });

  // Get initial queue status
  try {
    const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.STATUS, { 
      username: authStore.username 
    });
    if (response && response.success) {
      queueStore.updateQueueState({
        ...response,
         inQueue: response.queue?.includes(authStore.username)
        });
    }
  } catch (error) {
    console.error('Failed to get queue status:', error);
  }
});

onBeforeUnmount(() => {
  socketStore.off(SOCKET_EVENTS.QUEUE.UPDATE);
  socketStore.off(SOCKET_EVENTS.LOBBY.CREATED);
});

const joinQueue = async () => {
  try {
    loading.value = true;
    await queueStore.joinQueue(authStore.username);
  } catch (error) {
    console.error('Join queue error:', error);
  } finally {
    loading.value = false;
  }
};

const leaveQueue = async () => {
  try {
    loading.value = true;
    console.log('Leaving queue for:', authStore.username);
    await queueStore.leaveQueue(authStore.username);
  } catch (error) {
    console.error('Leave queue error:', error);
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
      <p v-if="queueStore.countdown !== null" class="countdown">
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
