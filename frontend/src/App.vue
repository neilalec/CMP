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
onMounted(() => {
  if (!authStore.restoreAuth()) {
    router.push('/auth');
  }
});

// Handle logout
const handleLogout = async () => {
  try {
    await socketStore.cleanupSocket();
    authStore.logout();
    router.push('/auth');
  } catch (error) {
    rootStore.setError('Logout failed');
  }
};

// Initialize socket connection when authenticated
watch(() => authStore.isLoggedIn, async (isLoggedIn) => {
  if (isLoggedIn && authStore.token) {
    try {
      rootStore.setLoading(true);
      await socketStore.initSocket(authStore.token, authStore.username);
    } catch (error) {
      rootStore.setError('Failed to connect to server');
      authStore.logout();
    } finally {
      rootStore.setLoading(false);
    }
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
