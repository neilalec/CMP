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
import { useGroupStore } from './stores/groupStore';

const router = useRouter();
const authStore = useAuthStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();
const lobbyStore = useLobbyStore();
const queueStore = useQueueStore();
const groupStore = useGroupStore();
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
const handleGroupUpdate = (data) => {
  groupStore.handleUpdate(data);
};
const handleLobbyCreated = (data) => {
  const isParticipant = data?.players?.includes(authStore.username);
  if (!isParticipant) return;
  if (data?.lobby_id) {
    lobbyStore.reset();
    lobbyStore.updateLobbyState(data);
    localStorage.setItem('currentLobby', data.lobby_id);
    queueStore.resetQueue();
    router.push(`/lobby/${data.lobby_id}`);
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
    
    // Redirect if not authenticated
    if (!isAuthenticated) {
      router.push('/auth');
    }
    socketStore.on(SOCKET_EVENTS.CONNECTION.CONNECT, syncLobbyPresence);
    socketStore.on(SOCKET_EVENTS.GROUP.UPDATE, handleGroupUpdate);
    socketStore.on(SOCKET_EVENTS.LOBBY.CREATED, handleLobbyCreated);
    await syncLobbyPresence();
    if (authStore.username) {
      await groupStore.syncStatus(authStore.username);
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
    groupStore.resetGroup();
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

const handleGroup = () => {
  router.push('/group');
};

const handleLobbyIdClick = () => {
  if (!activeLobbyId.value) return;
  if (!isInLobby.value) {
    router.push(`/lobby/${activeLobbyId.value}`);
  }
};

const syncLobbyPresence = async () => {
  if (!currentLobbyId.value || !socketStore.isConnected) return;
  try {
    const response = await socketStore.emit(SOCKET_EVENTS.OPEN_LOBBIES.STATUS);
    const openLobbies = response?.openLobbies || [];
    const activeLobbies = response?.activeLobbies || [];
    const exists = [...openLobbies, ...activeLobbies].some(
      lobby => lobby.lobby_id === currentLobbyId.value
    );
    if (!exists) {
      lobbyStore.leaveLobby();
      localStorage.removeItem('currentLobbyCaptains');
      currentLobbyId.value = null;
      currentLobbyCaptains.value = null;
    }
  } catch (error) {
    // Ignore transient errors during reconnects
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
      socketStore.on(SOCKET_EVENTS.GROUP.UPDATE, handleGroupUpdate);
      socketStore.on(SOCKET_EVENTS.LOBBY.CREATED, handleLobbyCreated);
      await groupStore.syncStatus(authStore.username);
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
  } else if (!localStorage.getItem('currentLobby')) {
    currentLobbyId.value = null;
    currentLobbyCaptains.value = null;
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
  socketStore.off(SOCKET_EVENTS.CONNECTION.CONNECT, syncLobbyPresence);
  socketStore.off(SOCKET_EVENTS.GROUP.UPDATE, handleGroupUpdate);
  socketStore.off(SOCKET_EVENTS.LOBBY.CREATED, handleLobbyCreated);
  socketStore.cleanupSocket();
});
</script>

<template>
  <div class="app">
    <div v-if="authStore.isLoggedIn" class="app-shell" :class="{ 'in-lobby': isInLobby }">
      <aside class="app-left">
        <RouterLink class="side-link" to="/">
          <span class="nav-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" role="img">
              <path d="M3 11.5L12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" fill="currentColor" />
            </svg>
          </span>
          <span class="nav-label">Home</span>
        </RouterLink>
        <RouterLink class="side-link" to="/queue">
          <span class="nav-icon" :class="{ 'in-queue': queueStore.inQueue }" aria-hidden="true">
            <svg viewBox="0 0 24 24" role="img">
              <polygon points="4,5 12,12 4,19" fill="#4a4f56" stroke="currentColor" stroke-width="1.6" />
              <polygon points="12,5 20,12 12,19" fill="#4a4f56" stroke="currentColor" stroke-width="1.6" />
            </svg>
          </span>
          <span class="nav-label">Play</span>
        </RouterLink>
        <RouterLink class="side-link" to="/lobbies">
          <span class="nav-icon">&#9673;</span>
          <span class="nav-label">Lobbies</span>
        </RouterLink>
        <div v-if="activeLobbyId" class="lobby-dropdown">
          <button class="lobby-id-button" type="button" @click="handleLobbyIdClick">
            <span class="nav-icon lobby-icon">&#9671;</span>
            <span class="lobby-label nav-label">{{ lobbyLabel }}</span>
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
          <span class="nav-label current-user">{{ authStore.username }}</span>
        </button>
        <button
          class="group-button"
          :class="{ 'in-group': groupStore.inGroup }"
          type="button"
          title="Group page"
          @click="handleGroup"
        >
          <span class="nav-icon group-icon" aria-hidden="true">
            <svg viewBox="0 0 28 22" role="img">
              <circle cx="8" cy="7" r="3" fill="currentColor" />
              <circle cx="20" cy="7" r="3" fill="currentColor" />
              <path d="M2 21c0-3 3-5 6-5s6 2 6 5" fill="currentColor" />
              <path d="M14 21c0-3 3-5 6-5s6 2 6 5" fill="currentColor" />
            </svg>
          </span>
          <span class="nav-label">Group</span>
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
  height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 0;
  width: 100%;
  overflow: hidden;
}

.app-shell {
  width: 100%;
  max-width: 100%;
  min-height: 100vh;
  height: 100vh;
  --nav-icon-box: 36px;
  --nav-collapsed: 40px;
  --nav-right-width: 56px;
  --nav-collapsed-right: var(--nav-right-width);
  --nav-offset: calc((var(--nav-collapsed) - var(--nav-icon-box)) / 2);
  --nav-link-pad: 0.3rem;
  --nav-hover-bg: #4d4d4d;
  --nav-hover-width: calc(100% - (var(--nav-link-pad) + var(--nav-offset)) - 6px);
  background: var(--surface);
  border-radius: 0;
  box-shadow: none;
  display: grid;
  grid-template-columns: 120px minmax(0, 1fr) var(--nav-right-width);
  transition: grid-template-columns 0.7s ease;
  gap: 0;
  padding: 0;
}

.app-shell.in-lobby {
  grid-template-columns: 52px minmax(0, 1fr) var(--nav-right-width);
  --nav-hover-width: var(--nav-icon-box);
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
  padding: 20px 0px;
  border-right: 1px solid var(--surface-border);
}

.side-link {
  display: grid;
  grid-template-columns: var(--nav-collapsed) 1fr;
  column-gap: 8px;
  align-items: center;
  justify-content: flex-start;
  padding: 0 var(--nav-link-pad);
  height: 36px;
  color: inherit;
  border-radius: 4px;
  border: 1px solid transparent;
  text-decoration: none;
  transition: background-color 0.2s, border-color 0.2s;
}

.side-link:hover {
  background: transparent;
  border-color: transparent;
}

.app-left .side-link,
.app-left .lobby-id-button {
  display: grid;
  grid-template-columns: var(--nav-collapsed) 1fr;
  column-gap: 8px;
  align-items: center;
}

.app-left .nav-icon {
  justify-self: center;
}

.nav-label {
  display: inline-block;
  white-space: nowrap;
  transition: opacity 0.2s ease, max-width 0.2s ease;
  max-width: 0;
  opacity: 0;
  overflow: hidden;
}

.app-shell:not(.in-lobby) {
  grid-template-columns: 150px minmax(0, 1fr) var(--nav-right-width);
}

.app-left .side-link,
.app-left .lobby-id-button {
  position: relative;
}

.app-left .side-link::before,
.app-left .lobby-id-button::before {
  content: "";
  position: absolute;
  top: 50%;
  left: calc(var(--nav-link-pad) + var(--nav-offset));
  transform: translateY(-50%);
  width: var(--nav-hover-width);
  height: 36px;
  background: var(--nav-hover-bg);
  border-radius: 4px;
  opacity: 0;
  transition: opacity 0.2s;
  z-index: 0;
  pointer-events: none;
}

.app-left .side-link:hover::before,
.app-left .lobby-id-button:hover::before {
  opacity: 1;
}

.app-left .side-link > *,
.app-left .lobby-id-button > * {
  position: relative;
  z-index: 1; 
}

.app-shell:not(.in-lobby) .app-left .nav-label {
  max-width: 140px;
  opacity: 1;
}

.app-shell.in-lobby .app-left .nav-label {
  transition-delay: 0s;
}


.app-right .nav-label {
  opacity: 0;
  pointer-events: none;
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: #2d2d2d;
  border: 1px solid #3d3d3d;
  border-radius: 4px;
  padding: 2px 5px;
  max-width: none;
  right: calc(100% + 6px);
}

.app-right .profile-button:hover .nav-label,
.app-right .group-button:hover .nav-label {
  opacity: 1;
}


.in-lobby .side-link,
.in-lobby .profile-button,
.in-lobby .lobby-id-button {
  position: relative;
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

.app-right .profile-button:hover,
.app-right .group-button:hover {
  background: transparent;
  border-color: transparent;
}

.app-right .profile-button:hover .nav-icon,
.app-right .group-button:hover .nav-icon {
  background: var(--nav-hover-bg);
  border-radius: 4px;
}

/* Use the same hover bubble in both views */
.app-left .side-link {
  position: relative;
}

/* Match hover bubble brightness across views (right column icons) */
.app-right .profile-button:hover .nav-icon,
.app-right .group-button:hover .nav-icon {
  opacity: 1;
}

.app-main {
  display: block;
  flex: 1;
  padding: 0;
  min-width: 0;
  background: var(--panel-bg);
  overflow-y: auto;
  overflow-x: hidden;
  scrollbar-width: thin;
  scrollbar-color: #3a3a3a #1f1f1f;
}

.app-main::-webkit-scrollbar {
  width: 10px;
}

.app-main::-webkit-scrollbar-track {
  background: #1f1f1f;
}

.app-main::-webkit-scrollbar-thumb {
  background: #3a3a3a;
  border-radius: 6px;
}

.app-main::-webkit-scrollbar-thumb:hover {
  background: #4a4a4a;
}

.app-actions {
  display: flex;
  justify-content: center;
  width: 100%;
}

.app-right {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  gap: 16px;
  padding: 16px 0px;
  border-left: 1px solid var(--surface-border);
  position: relative;
  width: var(--nav-right-width);
}

.app-right .profile-button {
  position: relative;
  width: 100%;
  display: grid;
  grid-template-columns: var(--nav-collapsed-right) 1fr;
  column-gap: 8px;
  align-items: center;
  justify-content: flex-start;
  padding: 0 0rem;
  height: 36px;
  box-sizing: border-box;
  text-align: left;
}

.app-right .nav-icon {
  justify-self: center;
}

.app-right .group-button {
  position: relative;
  width: 100%;
  display: grid;
  grid-template-columns: var(--nav-collapsed-right) 1fr;
  column-gap: 8px;
  align-items: center;
  justify-content: flex-start;
  padding: 0 0rem;
  height: 36px;
  box-sizing: border-box;
  text-align: left;
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
  max-width: 100%;
  padding: 0 0.3rem;
  height: 36px;
  background: #16202a;
  border: 1px solid transparent;
}

.app-left .lobby-id-button {
  width: 100%;
}

.lobby-id-button:hover {
  background: #22303c;
  border-color: #22303c;
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
  padding: 0 0.3rem;
  height: 36px;
}

.group-button {
  font-weight: 700;
  padding: 0 0.3rem;
  height: 36px;
}

.group-button.in-group .nav-icon {
  color: #7ed957;
}

.nav-icon {
  margin-right: 0;
  opacity: 0.8;
  font-size: 1.7em;
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

.nav-icon.in-queue {
  color: #7ed957;
}

</style>
