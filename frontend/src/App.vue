<script setup>
import { computed } from 'vue';
import { RouterLink, RouterView } from 'vue-router';
import { useRouter, useRoute } from 'vue-router';
import { useAuthStore } from './stores/authStore';
import { useSocketStore } from './stores/socketStore';
import { useRootStore } from './stores/rootStore';
import { useLobbyStore } from './stores/lobbyStore';
import { useQueueStore } from './stores/queueStore';
import { useGroupStore } from './stores/groupStore';
import { useAppSession } from './features/app/composables/useAppSession';
import { useThemeMode } from './features/app/composables/useThemeMode';
import { useMatchAcceptChime } from './features/app/composables/useMatchAcceptChime';
import MatchAcceptModal from './features/app/components/MatchAcceptModal.vue';

const router = useRouter();
const authStore = useAuthStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();
const lobbyStore = useLobbyStore();
const queueStore = useQueueStore();
const groupStore = useGroupStore();
const route = useRoute();
const { isDarkMode } = useThemeMode();
const {
  isInLobby,
  currentLobbyId,
  canReturnToLobby,
  playRoute,
  isMatchAcceptParticipant,
  isMatchAcceptCancelled,
  handleLogout,
  handleLeaveLobby,
  handleReturnToLobby,
  handleProfile,
  handleGroup,
  handleAcceptMatch,
  handleCloseMatchAccept,
  handleDismissMatchAccept
} = useAppSession({
  router,
  route,
  authStore,
  socketStore,
  rootStore,
  lobbyStore,
  queueStore,
  groupStore
});

const acceptedMatchPlayers = computed(() => queueStore.matchAccept.acceptedPlayers || []);
const waitingMatchPlayers = computed(() => {
  const accepted = new Set(acceptedMatchPlayers.value);
  return (queueStore.matchAccept.players || []).filter((player) => !accepted.has(player));
});

useMatchAcceptChime({
  queueStore,
  authStore,
  isMatchAcceptParticipant
});

const currentWindowTitle = computed(() => {
  if (route.path.startsWith('/lobby/')) return 'Lobby';
  if (route.path.startsWith('/play') || route.path === '/' || route.path.startsWith('/queue')) return 'Play';
  if (route.path.startsWith('/lobbies')) return 'Lobbies';
  if (route.path.startsWith('/results')) return 'Results';
  if (route.path.startsWith('/group')) return 'Group';
  if (route.path.startsWith('/profile')) return 'Profile';
  if (route.path.startsWith('/admin')) return 'Admin';
  if (route.path.startsWith('/auth')) return 'Authentication';
  return 'Play';
});

</script>

<template>
  <div class="app">
    <template v-if="authStore.isLoggedIn">
      <div class="app-shell" :class="{ 'in-lobby': isInLobby }">
        <aside class="app-left window-panel">
          <div class="window-titlebar">
            <span class="window-titlebar-label">Navigate</span>
          </div>
          <div class="sidebar-body">
            <RouterLink class="side-link" :to="playRoute">
              <span class="nav-icon" :class="{ 'in-queue': queueStore.inQueue }" aria-hidden="true">
                <svg viewBox="0 0 24 24" role="img">
                  <polygon points="4,5 12,12 4,19" fill="#959ca6" stroke="currentColor" stroke-width="1.6" />
                  <polygon points="12,5 20,12 12,19" fill="#959ca6" stroke="currentColor" stroke-width="1.6" />
                </svg>
              </span>
              <span class="nav-label">Play</span>
              <span v-if="queueStore.inQueue" class="queue-spinner" aria-hidden="true"></span>
            </RouterLink>
            <RouterLink class="side-link" to="/lobbies">
              <span class="nav-icon">&#9673;</span>
              <span class="nav-label">Lobbies</span>
            </RouterLink>
            <RouterLink class="side-link" to="/results">
              <span class="nav-icon">R</span>
              <span class="nav-label">Results</span>
            </RouterLink>
          </div>
        </aside>

        <main class="app-main window-panel">
          <div class="window-titlebar">
            <span class="window-titlebar-label">Competitive Matchmaking Platform</span>
            <span class="window-titlebar-meta">{{ currentWindowTitle }}</span>
          </div>
          <div class="main-window-body">
            <RouterView />
          </div>
        </main>

        <aside class="app-right window-panel">
          <div class="window-titlebar">
            <span class="window-titlebar-label">Session</span>
          </div>
          <div class="sidebar-body">
            <button class="profile-button" type="button" title="Profile page" @click="handleProfile">
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
            <button
              v-if="authStore.isAdmin"
              class="admin-button"
              type="button"
              title="Admin diagnostics"
              @click="router.push('/admin')"
            >
              <span class="nav-icon admin-icon" aria-hidden="true">A</span>
              <span class="nav-label">Admin</span>
            </button>
            <button
              class="theme-button"
              type="button"
              :aria-pressed="isDarkMode"
              :title="isDarkMode ? 'Switch to light mode' : 'Switch to dark mode'"
              @click="isDarkMode = !isDarkMode"
            >
              <span class="nav-icon theme-icon" aria-hidden="true">{{ isDarkMode ? 'L' : 'D' }}</span>
              <span class="nav-label">{{ isDarkMode ? 'Light' : 'Dark' }}</span>
            </button>
          </div>
        </aside>
      </div>

      <MatchAcceptModal
        :active="isMatchAcceptParticipant"
        :is-cancelled="isMatchAcceptCancelled"
        :cancel-reason="queueStore.matchAccept.cancelReason"
        :countdown="queueStore.matchAccept.countdown ?? 0"
        :accepted-count="queueStore.matchAccept.acceptedCount"
        :required-count="queueStore.matchAccept.requiredCount"
        :accepted-players="acceptedMatchPlayers"
        :waiting-players="waitingMatchPlayers"
        :loading="queueStore.loading"
        :has-accepted="queueStore.matchAccept.hasAccepted"
        @accept="handleAcceptMatch"
        @close="handleCloseMatchAccept"
        @dismiss="handleDismissMatchAccept"
      />
    </template>

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
  color: inherit;
  min-height: 100vh;
  min-height: 100dvh;
  height: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  padding: 0;
  width: 100%;
  overflow-x: hidden;
}

.app-shell {
  width: 100%;
  max-width: 100%;
  min-height: 100vh;
  min-height: 100dvh;
  height: auto;
  --nav-icon-box: 32px;
  --nav-column-width: 168px;
  background: var(--surface);
  display: grid;
  grid-template-columns: var(--nav-column-width) minmax(0, 1fr) var(--nav-column-width);
  gap: 12px;
  padding: 12px;
}

.auth-shell {
  width: 100%;
  min-height: 100vh;
  min-height: 100dvh;
  display: flex;
  justify-content: flex-start;
  align-items: flex-start;
  padding: clamp(24px, 6vw, 64px) clamp(16px, 4vw, 24px) 24px;
}

.error-message {
  position: fixed;
  bottom: 20px;
  right: 20px;
  background: var(--danger-soft);
  color: var(--danger);
  padding: 1rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--danger);
  box-shadow: var(--surface-shadow), var(--window-shadow);
}

.app-left {
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: sticky;
  top: 12px;
  height: calc(100dvh - 24px);
  align-self: start;
}

.side-link {
  display: flex;
  align-items: center;
  gap: 10px;
  justify-content: flex-start;
  min-height: 44px;
  padding: 0 10px;
  color: var(--text-main);
  border-radius: var(--radius-sm);
  border: 1px solid var(--control-border);
  text-decoration: none;
  background: var(--control-bg);
  box-shadow: var(--surface-shadow);
  transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
}

.nav-label {
  display: inline-block;
  white-space: nowrap;
}

.app-main {
  display: flex;
  flex-direction: column;
  padding: 0;
  min-width: 0;
  overflow-y: auto;
  overflow-x: hidden;
}

.main-window-body {
  flex: 1;
  min-height: 0;
  background: linear-gradient(180deg, var(--app-bg-soft) 0%, var(--app-bg) 100%);
}

.app-actions {
  display: flex;
  justify-content: center;
  width: 100%;
}

.app-right {
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: sticky;
  top: 12px;
  height: calc(100dvh - 24px);
  align-self: start;
}

.app-right .profile-button,
.app-right .group-button,
.app-right .admin-button,
.app-right .theme-button {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 44px;
  padding: 0 10px;
  border: 1px solid var(--control-border);
  background: var(--control-bg);
  box-shadow: var(--surface-shadow);
  text-align: left;
}

.sidebar-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px;
  flex: 1;
  min-height: 0;
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
  gap: 8px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  max-width: 100%;
  min-height: 44px;
  padding: 0 10px;
  background: transparent;
  border: 1px solid var(--surface-border);
}

.app-left .lobby-id-button {
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
  margin-top: 6px;
  background: var(--panel-bg-strong);
  border: 1px solid var(--surface-border-strong);
  border-radius: var(--radius-md);
  box-shadow: var(--surface-shadow), var(--window-shadow);
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
  height: 38px;
}

.group-button,
.admin-button,
.theme-button {
  font-weight: 700;
  padding: 0 0.3rem;
  height: 38px;
}

.theme-button {
  margin-top: auto;
}

.theme-icon {
  font-family: var(--font-mono);
  font-size: 1.1rem;
}

.group-button.in-group .nav-icon {
  color: var(--accent-strong);
}

.admin-button .nav-icon {
  color: var(--warning);
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 800;
}

.nav-icon {
  opacity: 1;
  font-size: 1.4em;
  width: var(--nav-icon-box);
  height: var(--nav-icon-box);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: currentColor;
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
  color: var(--accent-strong);
}

.side-link:hover,
.profile-button:hover,
.group-button:hover,
.admin-button:hover,
.theme-button:hover,
.lobby-id-button:hover,
.side-link.router-link-active {
  background: var(--control-bg-hover);
  border-color: var(--surface-border-strong);
  color: var(--text-main);
  text-decoration: none;
}

.side-link:has(.queue-spinner) {
  background: var(--accent-soft);
  border-color: var(--accent-border);
  color: var(--accent-strong);
}

.side-link:has(.queue-spinner):hover,
.side-link:has(.queue-spinner).router-link-active {
  background: var(--accent-soft);
  border-color: var(--accent-strong);
}

.queue-spinner {
  width: 13px;
  height: 13px;
  margin-left: auto;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: queue-spin 0.9s steps(8) infinite;
}

@keyframes queue-spin {
  to {
    transform: rotate(1turn);
  }
}

@media (max-width: 1024px) {
  .app-shell {
    --nav-column-width: 148px;
  }
}

@media (max-width: 768px) {
  .app-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto minmax(0, 1fr) auto;
    min-height: 100vh;
    min-height: 100dvh;
    gap: 10px;
    padding: 10px;
  }

  .app-left,
  .app-right {
    width: 100%;
    position: static;
    height: auto;
  }

  .app-left .side-link,
  .app-left .lobby-id-button,
  .app-right .profile-button,
  .app-right .group-button,
  .app-right .admin-button,
  .app-right .theme-button {
    width: auto;
    min-width: 0;
    display: inline-flex;
    gap: 8px;
    padding: 0 10px;
  }

  .sidebar-body {
    flex-direction: row;
    justify-content: center;
    flex-wrap: wrap;
  }

  .theme-button {
    margin-top: 0;
  }
}

@media (max-width: 480px) {
  .auth-shell {
    padding-inline: 12px;
  }

  .app-left .side-link,
  .app-left .lobby-id-button,
  .app-right .profile-button,
  .app-right .group-button,
  .app-right .admin-button,
  .app-right .theme-button {
    width: 100%;
    justify-content: center;
  }

}

</style>


