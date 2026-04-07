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
    return `Team ${activeCaptains.value.team1} vs Team ${activeCaptains.value.team2}`;
  }
  return activeLobbyId.value;
});
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
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 32 24" role="img">
              <circle cx="8" cy="7" r="3" fill="currentColor" />
              <circle cx="16" cy="7" r="3" fill="currentColor" />
              <circle cx="24" cy="7" r="3" fill="currentColor" />
              <path d="M2 22c0-3 3-5 6-5s6 2 6 5" fill="currentColor" />
              <path d="M10 22c0-3 3-5 6-5s6 2 6 5" fill="currentColor" />
              <path d="M18 22c0-3 3-5 6-5s6 2 6 5" fill="currentColor" />
            </svg>
          </span>
          <span class="nav-label">Queue</span>
        </RouterLink>
        <RouterLink class="side-link" to="/lobbies">
          <span class="nav-icon">◉</span>
          <span class="nav-label">Lobbies</span>
        </RouterLink>
        <div v-if="activeLobbyId" class="lobby-dropdown">
          <button class="lobby-id-button" type="button" @click="handleLobbyIdClick">
            <span class="lobby-label-row">
              <span class="nav-icon lobby-icon">◈</span>
              <span class="lobby-label nav-label">{{ lobbyLabel }}</span>
            </span>
          </button>
        </div>
      </aside>

      <main class="app-main">
        <RouterView />
      </main>

      <aside class="app-right">
        <button class="profile-button" type="button" title="Profile page coming soon" @click="handleProfile">
          <span class="nav-icon profile-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" role="img">
              <circle cx="12" cy="8" r="4" fill="currentColor" />
              <path d="M4 20c0-4 4-6 8-6s8 2 8 6" fill="currentColor" />
            </svg>
          </span>
          <span class="nav-label">{{ authStore.username }}</span>
        </button>
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
  padding: 0;
  width: 100%;
}

.app-shell {
  width: 100%;
  max-width: 100%;
  min-height: 100vh;
  --nav-icon-box: 36px;
  --nav-collapsed: 77px;
  --nav-offset: calc((var(--nav-collapsed) - var(--nav-icon-box)) / 2);
  background: var(--surface);
  border-radius: 0;
  box-shadow: none;
  display: grid;
  grid-template-columns: 144px minmax(0, 1fr) 120px;
  transition: grid-template-columns 0.7s ease;
  gap: 0;
  padding: 0;
}

.app-shell.in-lobby {
  grid-template-columns: 77px minmax(0, 1fr) 64px;
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
  gap: 16px;
  align-items: stretch;
  justify-content: flex-start;
  padding: 16px 12px;
  border-right: 1px solid var(--surface-border);
}

.app-shell:not(.in-lobby) .app-left {
  padding-left: var(--nav-offset);
}

.app-shell.in-lobby .app-left {
  padding-left: 0;
  padding-right: 0;
  align-items: center;
}

.side-link {
  display: grid;
  grid-template-columns: var(--nav-icon-box) 1fr;
  column-gap: 8px;
  align-items: center;
  justify-content: flex-start;
  padding: 0 0.3rem;
  height: 36px;
  color: inherit;
  border-radius: 4px;
  border: 1px solid transparent;
  text-decoration: none;
  transition: background-color 0.2s, border-color 0.2s;
}

.app-left .side-link {
  padding-left: 0;
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
  position: relative;
}

.in-lobby .app-left .side-link {
  display: flex;
  width: var(--nav-icon-box);
  height: var(--nav-icon-box);
  padding: 0;
  justify-content: center;
  align-items: center;
}

.in-lobby .app-left .lobby-id-button {
  width: var(--nav-icon-box);
  height: var(--nav-icon-box);
  padding: 0;
  justify-content: center;
  align-items: center;
}

.in-lobby .nav-label {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: #2d2d2d;
  border: 1px solid #3d3d3d;
  border-radius: 4px;
  padding: 2px 5px;
  opacity: 0;
  pointer-events: none;
  max-width: none;
  transition: opacity 0.2s ease;
}

.in-lobby .app-left .nav-label {
  left: calc(100% + 6px);
}

.in-lobby .app-right .nav-label {
  right: calc(100% + 6px);
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
  align-items: stretch;
  justify-content: stretch;
  gap: 0;
  padding: 0;
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
  gap: 16px;
  padding: 16px 12px;
  border-left: 1px solid var(--surface-border);
}

.lobby-dropdown {
  position: relative;
  display: inline-flex;
}

.app-left .lobby-dropdown {
  width: 100%;
}

.lobby-id-button {
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  flex-direction: row;
  align-items: center;
  max-width: 100%;
  padding: 0 0.3rem;
  height: 36px;
}

.app-left .lobby-id-button {
  width: 100%;
}

.lobby-label-row {
  display: grid;
  grid-template-columns: var(--nav-icon-box) 1fr;
  column-gap: 8px;
  align-items: center;
  max-width: 100%;
  line-height: 1;
  width: 100%;
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
  padding: 0 0.3rem;
  height: 36px;
}

.nav-icon {
  margin-right: 0;
  opacity: 0.8;
  font-size: 1.5em;
  width: var(--nav-icon-box);
  height: var(--nav-icon-box);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.nav-icon svg {
  display: block;
  width: 1em;
  height: 1em;
}

.lobby-icon {
  font-size: 2em;
}

</style>
