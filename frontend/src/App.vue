<script setup>
import { onMounted, onBeforeUnmount, watch } from 'vue';
import { RouterLink, RouterView } from 'vue-router';
import { useRouter } from 'vue-router';
import { useAuthStore } from './stores/authStore';
import { useSocketStore } from './stores/socketStore';
import { useRootStore } from './stores/rootStore';

const router = useRouter();
const authStore = useAuthStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();

// Initialize socket and auth state on mount
onMounted(async () => {
  console.log('App mounted, initializing base socket connection...');
  try {
    // First restore auth state
    const isAuthenticated = authStore.restoreAuth();
    
    // Initialize socket with auth credentials if available
    if (isAuthenticated) {
      await socketStore.initSocket(authStore.token, authStore.username);
    } else {
      await socketStore.initSocket();
    }
    
    // Redirect if not authenticated
    if (!isAuthenticated) {
      router.push('/auth');
    }
  } catch (error) {
    console.error('Failed to initialize socket:', error);
    rootStore.setError('Failed to connect to server');
  }
});

// Handle logout
const handleLogout = async () => {
  try {
    await socketStore.cleanupSocket();
    authStore.logout();
    // Reinitialize unauthenticated socket after logout
    await socketStore.initSocket();
    router.push('/auth');
  } catch (error) {
    rootStore.setError('Logout failed');
  }
};

// Watch for auth state changes to update socket connection
watch(() => authStore.isLoggedIn, async (isLoggedIn) => {
  if (isLoggedIn && authStore.token) {
    try {
      rootStore.setLoading(true);
      // Cleanup existing socket and create new authenticated connection
      await socketStore.cleanupSocket();
      await socketStore.initSocket(authStore.token, authStore.username);
   
    } catch (error) {
      rootStore.setError('Failed to connect to server');
      authStore.logout();
    } finally {
      rootStore.setLoading(false);
    }
  }
});

// Cleanup on component unmount
onBeforeUnmount(() => {
  socketStore.cleanupSocket();
});
</script>

<template>
  <div class="app">
    <nav v-if="authStore.isLoggedIn">
      <RouterLink to="/">Home</RouterLink>
      <span class="username">User: {{ authStore.username }}</span>
      <button @click="handleLogout">Logout</button>
    </nav>

    <RouterView />

    <div v-if="rootStore.globalError" class="error-message">
      {{ rootStore.globalError }}
    </div>
  </div>
</template>

<style scoped>
.app {
  font-family: Arial, sans-serif;
  background: #1a1a1a;
  color: #ffffff;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

nav {
  background: #2d2d2d;
  padding: 1rem;
  display: flex;
  justify-content: center;
  gap: 1rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

nav a {
  color: #ffffff;
  text-decoration: none;
  padding: 0.5rem 1rem;
  border-radius: 4px;
  transition: background-color 0.2s;
}

nav a:hover {
  background: #3d3d3d;
}

.error-message {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: #ff4444;
  color: white;
  padding: 1rem;
  border-radius: 4px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
}

button {
  padding: 0.5rem 1rem;
  cursor: pointer;
  background: #3d3d3d;
  color: white;
  border: none;
  border-radius: 4px;
  transition: background-color 0.2s;
}

button:hover {
  background: #4d4d4d;
}

.username {
  color: #888;
  line-height: 1;
  display: inline-flex;
  align-items: center;
}
</style>
