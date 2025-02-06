<script setup>
import { ref, watch, onBeforeUnmount, onMounted, computed } from 'vue';
import { authState, logout } from '../stores/auth';
import { useRouter } from 'vue-router';
import { useSocket } from '../useSocket';
import { useQueueStore } from '../stores/queueStore';

const { socket, playersInQueue, inQueue, loading, findMatch, leaveQueue } = useSocket();
const router = useRouter();
const message = ref('');
const lobbyId = ref('');
const isLoggedIn = computed(() => !!localStorage.getItem('token'));
const username = ref(localStorage.getItem('username'));
const queueStore = useQueueStore();







const handleLogout = () => {
  logout(router); // Pass the router instance to the centralized logout method
};

const handleLobbyUpdate = (data) => {
  console.log('Lobby update received:', data);
  router.push({ name: 'lobby', params: { lobbyId: data.lobby_id } });
};

const handleJoinQueue = () => {
  console.log('Attempting to join queue with username:', username.value);
  if (!username.value) {
    message.value = 'No username found';
    return;
  }

  if (loading.value) {
    message.value = 'Already processing queue request';
    return;
  }

  findMatch(username.value);
};

const handleLeaveQueue = () => {
  console.log('Attempting to leave queue with username:', username.value);
  if (!username.value) {
    message.value = 'No username found';
    return;
  }

  leaveQueue(username.value);
};






// Add a watcher for loading state
watch(loading, (newValue) => {
  if (!newValue) {
    console.log('Queue operation completed, inQueue:', inQueue.value);
  }
});









onMounted(() => {
  if (!isLoggedIn.value) {
    router.push('/login');
    return;
  }


  console.log('Home component mounted');


  if (socket.value) {
    
    socket.value.on('queue_joined', (data) => {
      console.log('Queue joined response:', data);
      if (data.success) {
        message.value = 'Joined queue successfully';
      } else {
        message.value = data.message || 'Failed to join queue';
      }
    });

    socket.value.on('match_found', (data) => {
      router.push(`/match/${data.match_id}`);
      inQueue.value = false;
      playersInQueue.value = 0;
    });
 }
});






// Clean up listeners when component unmounts
onBeforeUnmount(() => {
  if (socket.value) {
    socket.value.off('queue_joined');
    socket.value.off('match_found');
  }
});



</script>

<template>
  <div v-if="isLoggedIn" class="queue-container">

    <div class="queue-status">
      <p v-if="queueStore.playersInQueue > 0" class="queue-count">
        Players in queue: {{ queueStore.playersInQueue }}
      </p>
      <p v-else class="queue-empty">
      No players in queue currently.
      </p>

      <p class="queue-status-text">
        Queue Status: {{  queueStore.inQueue ? 'In Queue' : 'Not in Queue' }}
      </p>

      <!-- Queue List -->
      <div v-if="queueStore.queueList.length" class="queue-list">
        <h3>Current Queue:</h3>
        <ul>
          <li v-for="player in queueStore.queueList" :key="player"
              :class="{ 'current-player': player === username }">
            {{ player }}
          </li>
        </ul>
      </div>
    </div>
    
      <!-- Queue Controls -->
    <div class="queue-controls">
      <button 
        @click="handleJoinQueue" 
        :disabled="queueStore.inQueue || loading"
        class="queue-button join-button"
      >
        Join Queue
      </button>

      <button 
        v-if="queueStore.inQueue" 
        @click="handleLeaveQueue"
        class="queue-button leave-button"
      >
        Leave Queue
      </button>

      <div v-if="loading" class="spinner">...</div>
      <p v-if="message" class="message">{{ message }}</p>
    </div>
  </div>
  <div v-else class="login-prompt">
    <p>Please log in to access the app.</p>
  </div>

</template>

<style scoped>
.queue-container {
  padding: 20px;
  max-width: 600px;
  margin: 0 auto;
}

.queue-status {
  margin-bottom: 20px;
}

.queue-count, .queue-empty {
  font-size: 1.2em;
  margin-bottom: 10px;
}

.queue-status-text {
  font-weight: bold;
  color: #2c3e50;
}
.queue-list {
  margin: 20px 0;
  padding: 10px;
  background: #f5f5f5;
  border-radius: 4px;
}

.queue-list ul {
  list-style: none;
  padding: 0;
}

.queue-list li {
  padding: 5px 10px;
  margin: 2px 0;
  border-radius: 3px;
}

.current-player {
  background: #e3f2fd;
  font-weight: bold;
}
.queue-controls {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
}

.queue-button {
  padding: 8px 16px;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-weight: bold;
  transition: all 0.3s ease;
}

.join-button {
  background: #4CAF50;
  color: white;
}
.join-button:disabled {
  background: #cccccc;
  cursor: not-allowed;
}

.leave-button {
  background: #f44336;
  color: white;
}
.spinner {
  margin-top: 20px;
  border: 4px solid transparent;
  border-top: 4px solid #f44336;
  border-radius: 50%;
  width: 50px;
  height: 50px;
  animation: spin 2s linear infinite;
}
.message {
  margin-top: 10px;
  padding: 10px;
  border-radius: 4px;
  background: #e3f2fd;
}

.login-prompt {
  text-align: center;
  padding: 20px;
  color: #666;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

</style>
