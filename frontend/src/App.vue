<script setup>
import { onMounted, onBeforeUnmount, watch, ref, computed } from 'vue';
import { RouterLink, RouterView } from 'vue-router';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from './stores/authStore';
import { useSocketStore } from './stores/socketStore';
import { useRootStore } from './stores/rootStore';
import { SOCKET_EVENTS } from './constants/socketEvents';
import { useLobbyStore } from './stores/lobbyStore';
import { useQueueStore } from './stores/queueStore';

const router = useRouter();
const authStore = useAuthStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();
const lobbyStore = useLobbyStore();
const queueStore = useQueueStore();
const route = useRoute();
const isCountdownPaused = ref(false);
const isInLobby = computed(() => route.path.startsWith('/lobby/'));
const currentLobbyId = ref(localStorage.getItem('currentLobby'));
const canReturnToLobby = computed(() => !!currentLobbyId.value && !isInLobby.value);
const showPauseButton = computed(() => {
  return !!queueStore.countdown || lobbyStore.countdown !== null || lobbyStore.votingCountdown !== null || lobbyStore.teamCountdown !== null;
});
const handleCountdownPauseState = (data) => {
  if (data && typeof data.paused === 'boolean') {
    isCountdownPaused.value = data.paused;
  }
};
const syncCountdownPauseState = async () => {
  if (!socketStore.isConnected) return;
  try {
    const response = await socketStore.emit(SOCKET_EVENTS.COUNTDOWN.STATUS);
    if (response && typeof response.paused === 'boolean') {
      isCountdownPaused.value = response.paused;
    }
  } catch (error) {
    // Avoid noisy errors during reconnects
  }
};

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
    
    socketStore.on(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE, handleCountdownPauseState);
    socketStore.on(SOCKET_EVENTS.CONNECTION.CONNECT, syncCountdownPauseState);
    await syncCountdownPauseState();

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
    localStorage.removeItem('currentLobby');
    currentLobbyId.value = null;
    // Reinitialize unauthenticated socket after logout
    await socketStore.initSocket();
    router.push('/auth');
  } catch (error) {
    rootStore.setError('Logout failed');
  }
};

const handleLeaveLobby = async () => {
  if (!route.params.lobbyId) return;
  try {
    const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.LEAVE, {
      lobby_id: route.params.lobbyId,
      username: authStore.username
    });
    if (response?.success) {
      lobbyStore.leaveLobby();
      localStorage.removeItem('currentLobby');
      currentLobbyId.value = null;
      router.push('/');
    } else {
      throw new Error(response?.message || 'Failed to leave lobby');
    }
  } catch (error) {
    rootStore.setError('Failed to leave lobby');
  }
};

const handleReturnToLobby = async () => {
  if (!currentLobbyId.value) return;
  router.push(`/lobby/${currentLobbyId.value}`);
};

const handleProfile = () => {
  router.push('/profile');
};

const toggleCountdownPause = async () => {
  const nextPaused = !isCountdownPaused.value;
  isCountdownPaused.value = nextPaused;
  try {
    const response = await socketStore.emit(SOCKET_EVENTS.COUNTDOWN.TOGGLE_PAUSE, {
      paused: nextPaused
    });
    if (response && typeof response.paused === 'boolean') {
      isCountdownPaused.value = response.paused;
    }
  } catch (error) {
    isCountdownPaused.value = !nextPaused;
    rootStore.setError('Failed to toggle countdown pause');
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
      socketStore.on(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE, handleCountdownPauseState);
      socketStore.on(SOCKET_EVENTS.CONNECTION.CONNECT, syncCountdownPauseState);
      await syncCountdownPauseState();
   
    } catch (error) {
      rootStore.setError('Failed to connect to server');
      authStore.logout();
    } finally {
      rootStore.setLoading(false);
    }
  }
});

watch(() => lobbyStore.lobbyId, (id) => {
  if (id) {
    currentLobbyId.value = id;
    localStorage.setItem('currentLobby', id);
  }
});

// Cleanup on component unmount
onBeforeUnmount(() => {
  socketStore.off(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE, handleCountdownPauseState);
  socketStore.off(SOCKET_EVENTS.CONNECTION.CONNECT, syncCountdownPauseState);
  socketStore.cleanupSocket();
});
</script>

<template>
  <div class="app">
    <div class="app-shell">
      <nav v-if="authStore.isLoggedIn">
        <div class="nav-left">
          <RouterLink to="/">Home</RouterLink>
        </div>
        <div class="nav-center">
          <button v-if="showPauseButton" @click="toggleCountdownPause">
            {{ isCountdownPaused ? 'Unpause Countdown' : 'Pause Countdown' }}
          </button>
          <button v-if="isInLobby" @click="handleLeaveLobby">
            Permanently Leave Lobby
          </button>
          <button v-if="canReturnToLobby" @click="handleReturnToLobby">
            Currently in Lobby 
          </button>
        </div>
        <div class="nav-right">
          <button class="profile-button" type="button" title="Profile page coming soon" @click="handleProfile">
            {{ authStore.username }}
          </button>
        </div>
    </nav>

      <div class="app-body">
        <RouterView />
      </div>
    </div>

    <div v-if="rootStore.globalError" class="error-message">
      {{ rootStore.globalError }}
    </div>
  </div>
</template>

<style scoped>
.app {
  font-family: Arial, sans-serif;
  color: #ffffff;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 24px;
  width: 100%;
}

.app-shell {
  width: 100%;
  max-width: 1100px;
  min-height: calc(100vh - 48px);
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-radius: 14px;
  box-shadow: var(--surface-shadow);
  display: flex;
  flex-direction: column;
}

.app-body {
  flex: 1;
  padding: 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
}

nav {
  background: transparent;
  padding: 1rem 1.5rem;
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  border-bottom: 1px solid var(--surface-border);
  flex-wrap: wrap;
  align-items: center;
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
  background: transparent;
  color: white;
  border: 1px solid transparent;
  border-radius: 4px;
  transition: background-color 0.2s, border-color 0.2s;
}

button:hover {
  background: #3d3d3d;
  border-color: #3d3d3d;
}

.nav-left {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-width: 120px;
}

.nav-center {
  display: flex;
  align-items: center;
  gap: 1rem;
  flex: 1;
  justify-content: center;
  flex-wrap: wrap;
}

.nav-right {
  display: flex;
  align-items: center;
  gap: 1rem;
  min-width: 120px;
  justify-content: flex-end;
}

.profile-button {
  font-weight: 700;
  background: #2f2f2f;
}
</style>
