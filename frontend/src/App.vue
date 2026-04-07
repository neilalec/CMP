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
const currentLobbyCaptains = ref(null);
try {
  const saved = localStorage.getItem('currentLobbyCaptains');
  currentLobbyCaptains.value = saved ? JSON.parse(saved) : null;
} catch (error) {
  currentLobbyCaptains.value = null;
}
const canReturnToLobby = computed(() => !!currentLobbyId.value && !isInLobby.value);
const activeLobbyId = computed(() => {
  return route.params.lobbyId || lobbyStore.lobbyId || currentLobbyId.value;
});
const activeCaptains = computed(() => {
  if (lobbyStore.captains?.team1 && lobbyStore.captains?.team2) {
    return lobbyStore.captains;
  }
  return currentLobbyCaptains.value;
});
const lobbyLabel = computed(() => {
  if (activeCaptains.value?.team1 && activeCaptains.value?.team2) {
    return `Lobby ${activeCaptains.value.team1} vs ${activeCaptains.value.team2}`;
  }
  return activeLobbyId.value;
});
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
    localStorage.removeItem('currentLobbyCaptains');
    currentLobbyId.value = null;
    currentLobbyCaptains.value = null;
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
      localStorage.removeItem('currentLobbyCaptains');
      currentLobbyId.value = null;
      currentLobbyCaptains.value = null;
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

const handleLobbyIdClick = () => {
  if (!activeLobbyId.value) return;
  if (!isInLobby.value) {
    router.push(`/lobby/${activeLobbyId.value}`);
  }
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

watch(() => lobbyStore.captains, (captains) => {
  if (captains?.team1 && captains?.team2) {
    currentLobbyCaptains.value = captains;
    localStorage.setItem('currentLobbyCaptains', JSON.stringify(captains));
  }
}, { deep: true });

// Cleanup on component unmount
onBeforeUnmount(() => {
  socketStore.off(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE, handleCountdownPauseState);
  socketStore.off(SOCKET_EVENTS.CONNECTION.CONNECT, syncCountdownPauseState);
  socketStore.cleanupSocket();
});
</script>

<template>
  <div class="app">
    <div v-if="authStore.isLoggedIn" class="app-shell" :class="{ 'in-lobby': isInLobby }">
      <aside class="app-left">
        <RouterLink class="side-link" to="/">
          <span class="nav-icon">⌂</span>
          <span class="nav-label">Home</span>
        </RouterLink>
        <RouterLink class="side-link" to="/queue">
          <span class="nav-icon">≡</span>
          <span class="nav-label">Queue</span>
        </RouterLink>
        <RouterLink class="side-link" to="/lobbies">
          <span class="nav-icon">◉</span>
          <span class="nav-label">Lobbies</span>
        </RouterLink>
      </aside>

      <main class="app-main">
        <RouterView />
      </main>

      <aside class="app-right">
        <button class="profile-button" type="button" title="Profile page coming soon" @click="handleProfile">
          <span class="nav-icon">◎</span>
          <span class="nav-label">{{ authStore.username }}</span>
        </button>
        <div v-if="activeLobbyId" class="lobby-dropdown">
          <button class="lobby-id-button" type="button" @click="handleLobbyIdClick">
            <span class="lobby-label-row">
              <span class="nav-icon">◈</span>
              <span class="lobby-label nav-label">{{ lobbyLabel }}</span>
            </span>
          </button>
          <div v-if="isInLobby || showPauseButton" class="lobby-menu">
            <button @click="handleLeaveLobby">
              Permanently Leave Lobby
            </button>
            <button v-if="showPauseButton" @click="toggleCountdownPause">
              {{ isCountdownPaused ? 'Unpause Countdown' : 'Pause Countdown' }}
            </button>
          </div>
        </div>
      </aside>
    </div>

    <div v-else class="auth-shell">
      <RouterView />
    </div>

    <div v-if="rootStore.globalError" class="error-message">
      {{ rootStore.globalError }}
    </div>
  </div>
</template>

<style scoped>
.app {
  font-family: Arial, sans-serif;
  color: inherit;
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
  max-width: 100%;
  min-height: calc(100vh - 48px);
  background: var(--surface);
  border-radius: 14px;
  box-shadow: var(--surface-shadow);
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr) 120px;
  gap: 16px;
  padding: 0;
}

.app-shell.in-lobby {
  grid-template-columns: 64px minmax(0, 1fr) 64px;
}

.auth-shell {
  width: 100%;
  max-width: 800px;
  min-height: calc(100vh - 48px);
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-radius: 14px;
  box-shadow: var(--surface-shadow);
  padding: 24px;
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
  color: inherit;
  border: 1px solid transparent;
  border-radius: 4px;
  transition: background-color 0.2s, border-color 0.2s;
}

button:hover {
  background: #3d3d3d;
  border-color: #3d3d3d;
}

.app-left {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: stretch;
  justify-content: flex-start;
  padding: 16px 12px;
  border-right: 1px solid var(--surface-border);
}

.side-link {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  padding: 0.8rem;
  color: inherit;
  border-radius: 4px;
  border: 1px solid transparent;
  text-decoration: none;
  transition: background-color 0.2s, border-color 0.2s;
}

.side-link:hover {
  background: #4d4d4d;
  border-color: #4d4d4d;
}

.nav-label {
  display: inline-block;
  white-space: nowrap;
  transition: opacity 0.2s ease, max-width 0.2s ease;
  max-width: 140px;
  opacity: 1;
}

.in-lobby .side-link,
.in-lobby .profile-button,
.in-lobby .lobby-id-button {
  justify-content: flex-start;
  position: relative;
}

.in-lobby .nav-label {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: #2d2d2d;
  border: 1px solid #3d3d3d;
  border-radius: 4px;
  padding: 4px 8px;
  opacity: 0;
  pointer-events: none;
  max-width: none;
  transition: opacity 0.2s ease;
}

.in-lobby .app-left .nav-label {
  left: calc(100% + 8px);
}

.in-lobby .app-right .nav-label {
  right: calc(100% + 8px);
}

.in-lobby .side-link:hover .nav-label,
.in-lobby .profile-button:hover .nav-label,
.in-lobby .lobby-id-button:hover .nav-label {
  opacity: 1;
}

.app-main {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 16px;
  padding: 16px;
  min-width: 0;
}

.app-actions {
  display: flex;
  justify-content: center;
  width: 100%;
}

.app-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  justify-content: flex-start;
  gap: 12px;
  padding: 16px 12px;
  border-left: 1px solid var(--surface-border);
}

.lobby-dropdown {
  position: relative;
  display: inline-flex;
}

.lobby-id-button {
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 4px;
  flex-direction: column;
  align-items: flex-start;
  max-width: 100%;
}

.lobby-label-row {
  display: flex;
  align-items: center;
  gap: 8px;
  max-width: 100%;
}

.lobby-label {
  font-weight: 700;
  max-width: 100%;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.lobby-menu {
  display: none;
  position: absolute;
  top: 100%;
  left: 0;
  transform: none;
  margin-top: 0;
  background: #2d2d2d;
  border: 1px solid #3d3d3d;
  border-radius: 6px;
  padding: 8px;
  z-index: 10;
  min-width: 200px;
}

.app-right .lobby-menu {
  left: auto;
  right: 0;
}

.lobby-dropdown:hover .lobby-menu {
  display: block;
}

.lobby-menu button {
  width: 100%;
}

.profile-button {
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
}

.nav-icon {
  margin-right: 0;
  opacity: 0.8;
  font-size: 1.5em;
}

</style>
