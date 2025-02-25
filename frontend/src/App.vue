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

// Initialize auth state and socket on mount
onMounted(async () => {
  try {
    if (authStore.restoreAuth()) {
      console.log('Auth restored');
    }
  } catch (error) {
    console.error('Failed to restore session:', error);
    await authStore.logout();
    router.push('/auth');
  }
});

// Handle logout
const handleLogout = async () => {
  try {
    // First cleanup socket
    await socketStore.cleanupSocket();
    // Then logout auth
    await authStore.logout();
    // Finally redirect
    router.push('/auth');
  } catch (error) {
    rootStore.setError('Logout failed');
  }
};

// Initialize socket connection when authenticated
watch(() => authStore.isLoggedIn, async (isLoggedIn, oldValue) => {
  console.log('Auth state changed:', { isLoggedIn, oldValue });
  if (isLoggedIn && authStore.token && !socketStore.isConnected) {
    try {
      console.log('Attempting to initialize socket...');
      rootStore.setLoading(true);
      await socketStore.initSocket(authStore.token, authStore.username);
      console.log('Socket initialized successfully');
    } catch (error) {
      console.error('Socket initialization error:', error);
      rootStore.setError('Failed to connect to server');
      await authStore.logout();
    } finally {
      rootStore.setLoading(false);
    }
  } else if (!isLoggedIn && oldValue) {
    console.log('Cleaning up socket due to logout');
    await socketStore.cleanupSocket();
  }
}, { immediate: true });

// Cleanup on component unmount
onBeforeUnmount(() => {
  socketStore.cleanupSocket();
});
</script>

<template>
  <div class="app">
    <nav v-if="authStore.isLoggedIn">
      <RouterLink to="/">Home</RouterLink>
      <span class="username">{{ authStore.username }}</span>
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
  background: white;
  color: black;
}

nav {
  background: #f0f0f0;
  padding: 1rem;
  display: flex;
  justify-content: center;
  gap: 1rem;
}

.error-message {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: #ff0000;
  color: white;
  padding: 1rem;
}

button {
  padding: 0.5rem 1rem;
  cursor: pointer;
}
</style>
