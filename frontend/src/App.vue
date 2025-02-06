<script setup>
import { ref, onMounted, onBeforeUnmount, onUnmounted, watchEffect, computed } from 'vue';  // Import ref and onMounted for reactivity
import { RouterLink, RouterView } from 'vue-router'
import { useRouter } from 'vue-router'; // For redirecting during logout
import { authState, logout, login } from './stores/auth';
import { useSocket } from './useSocket'; // Import useSocket

// Reactive variables for handling login state and WebSocket communication
const router = useRouter();
const { 
  socket,
  cleanupSocket,
  playersInQueue
} = useSocket();

const message = ref('');  // Reactive variable to store the message from Flask
const socketMessage = ref(''); // Reactive variable to store the real-time message from Socket.IO
const inputMessage = ref(''); // Reactive variable to store the message to be sent
const username = ref(localStorage.getItem('username') || '');
const isLoggedIn = computed(() => !!localStorage.getItem('token')); // Check if user is logged inconst playersInQueue = ref(0); // track number of players in queue

watchEffect(() => {
  username.value = localStorage.getItem('username') || '';
});

const handleLogout = () => {
  logout(router); // Pass the router instance to the centralized logout method
};

onMounted(() => {
  if (isLoggedIn.value && socket.value) {
        // Request initial queue status
    socket.value.emit('get-queue-status', { 
      username: localStorage.getItem('username') 
    });

    socket.value.on('message', (data) => {
      console.log('Received message from server:', data);
      socketMessage.value = data.data;  // Store the message globally
    });

    socket.value.on('match_found', (data) => {
      alert(`Queue filled! Match: ${data.players.join(' vs ')} with match_id: ${data.match_id}`);
    });
  }
});

onBeforeUnmount(() => {
  if (socket.value) {
    socket.value.off('message');
    socket.value.off('match_found');
  }
});

// Socket event handlers
const sendMessage = () => {
  if (socket.value && inputMessage.value) {
    socket.value.emit('message', inputMessage.value);
    inputMessage.value = '';
  }
};
</script>

<template>
    <h1>Squad Competitive Matchmaking</h1>
    <p> </p>
    <div id="app">
      <nav>
        <RouterLink v-if="!authState.isLoggedIn" to="/login">Login</RouterLink>
        <RouterLink v-if="!authState.isLoggedIn" to="/register">Register</RouterLink>
        <button v-if="authState.isLoggedIn" @click="handleLogout">Logout</button>
        <div class="user-info" v-if="isLoggedIn">
           Logged in as: {{ username }}
        </div>
      </nav>
      <router-view></router-view> <!-- Dynamic view based on route -->
    </div>
</template>

<style scoped>
/* Global styles for the app */
body {
  font-family: Arial, sans-serif;
  background-color: #222;
  color: white;
  margin: 0;
  padding: 0;
}

#app {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start; /* Adjusts for top-to-bottom layout */
  min-height: 100vh; /* Ensures full-page height */
  width: 100%;
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* Center-align main content */
main {
  width: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 20px;
}

nav {
  background-color: #333;
  color: white;
  display: flex;
  justify-content: center;
  padding: 1rem;
  position: sticky;
  top: 0;
}

nav a, nav button {
  color: white;
  text-decoration: none;
  padding: 0.5rem 1rem;
}

nav a:hover, nav button:hover {
  background-color: #555;
}

.content {
  padding: 20px;
  max-width: 800px;
  margin: 20px auto;
  text-align: center;
}

input, button {
  width: 100%;
  max-width: 300px;
  padding: 10px;
  margin: 10px auto;
  display: block;
}

button {
  background-color: #f44336;
  color: white;
  border: none;
  cursor: pointer;
}

button:hover {
  background-color: #ff3333;
}

p {
  margin: 10px 0;
} 

.user-info {
  position: absolute;
  top: 10px;
  left: -200px;
  font-size: 1rem;
  color: #fff;
}

</style>
