<script setup>
import { computed, nextTick, ref, watch } from 'vue';
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
import MatchPhaseTracker from './features/match/components/MatchPhaseTracker.vue';
import scmLogo from './assets/scm-logo.png';

const router = useRouter();
const authStore = useAuthStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();
const lobbyStore = useLobbyStore();
const queueStore = useQueueStore();
const groupStore = useGroupStore();
const route = useRoute();
const mainWindowBody = ref(null);
const { themeLabel, themeIcon, nextThemeLabel, cycleTheme } = useThemeMode();
const {
  isInLobby,
  currentLobbyId,
  playRoute,
  isMatchAcceptParticipant,
  isMatchAcceptCancelled,
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
  if (route.path.startsWith('/play') || route.path === '/' || route.path.startsWith('/queue')) return 'Queue';
  if (route.path.startsWith('/lobbies')) return 'Lobbies';
  if (route.path.startsWith('/results')) return 'Results';
  if (route.path.startsWith('/discord')) return 'Discord';
  if (route.path.startsWith('/about')) return 'About';
  if (route.path.startsWith('/terms')) return 'Terms';
  if (route.path.startsWith('/privacy')) return 'Privacy';
  if (route.path.startsWith('/group')) return 'Group';
  if (route.path.startsWith('/profile')) return 'Profile';
  if (route.path.startsWith('/admin')) return 'Admin';
  if (route.path.startsWith('/auth')) return 'Authentication';
  return 'Play';
});

const isQueueRoute = computed(() => route.path === '/' || route.path.startsWith('/play') || route.path.startsWith('/queue'));
const isLobbiesRoute = computed(() => route.path.startsWith('/lobbies'));
const isResultsRoute = computed(() => route.path.startsWith('/results'));
const isDiscordRoute = computed(() => route.path.startsWith('/discord'));
const isAboutRoute = computed(() => route.path.startsWith('/about'));
const isProfileRoute = computed(() => route.path.startsWith('/profile'));
const isGroupRoute = computed(() => route.path.startsWith('/group'));
const isAdminRoute = computed(() => route.path.startsWith('/admin'));
const isPlayHighlighted = computed(() => {
  const hasQueueSession = queueStore.inQueue && !!queueStore.queueMode;
  const hasLobbySession = isInLobby.value || !!currentLobbyId.value;
  return hasQueueSession || hasLobbySession;
});
const currentLobbyPhase = computed(() => {
  if (lobbyStore.step === 5) return 'complete';
  if (lobbyStore.step === 4) return 'live';
  if (lobbyStore.step === 3) return 'server';
  return 'map';
});
const lobbyTrackerPhases = [
  { id: 'map', label: 'Map Vote' },
  { id: 'server', label: 'Join Server' },
  { id: 'live', label: 'Live' },
  { id: 'complete', label: 'Score' }
];

const resetLobbyScroll = async () => {
  if (!route.path.startsWith('/lobby/')) return;
  await nextTick();

  const scrollToTop = () => {
    mainWindowBody.value?.scrollTo?.({ top: 0, left: 0, behavior: 'auto' });
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    document.documentElement.scrollTop = 0;
    document.body.scrollTop = 0;
  };

  scrollToTop();
  requestAnimationFrame(scrollToTop);
  setTimeout(scrollToTop, 0);
};

watch(
  [
    () => route.fullPath,
    () => lobbyStore.lobbyId,
    () => lobbyStore.step
  ],
  resetLobbyScroll,
  { flush: 'post' }
);

</script>

<template>
  <div class="app">
    <template v-if="authStore.isLoggedIn">
      <div class="app-shell" :class="{ 'in-lobby': isInLobby }">
        <header class="app-header">
          <div class="top-banner">
            <span class="header-heading app-brand-title" aria-label="Squad Comp Matchmaking">
              <span class="brand-mark">
                <img class="brand-logo" :src="scmLogo" alt="" aria-hidden="true">
              </span>
              <span class="brand-divider" aria-hidden="true"></span>
              <span class="brand-name">Squad Comp Matchmaking</span>
            </span>
          </div>
        </header>

        <aside class="app-left window-panel">
          <div class="window-titlebar">
            <span class="window-titlebar-label">Navigate</span>
          </div>
          <div class="sidebar-body">
            <RouterLink
              class="side-link chrome-nav-item"
              :class="{ active: isQueueRoute, 'play-highlighted': isPlayHighlighted }"
              :to="playRoute"
            >
              <span class="nav-icon" :class="{ 'in-queue': queueStore.inQueue }" aria-hidden="true">
                <svg viewBox="0 0 24 24" role="img">
                  <polygon points="4,5 12,12 4,19" fill="currentColor" fill-opacity="0.28" stroke="currentColor" stroke-width="1.6" />
                  <polygon points="12,5 20,12 12,19" fill="currentColor" fill-opacity="0.42" stroke="currentColor" stroke-width="1.6" />
                </svg>
              </span>
              <span class="nav-label">Play</span>
              <span v-if="isPlayHighlighted" class="queue-spinner" aria-hidden="true"></span>
            </RouterLink>
            <RouterLink class="side-link chrome-nav-item" :class="{ active: isLobbiesRoute }" to="/lobbies">
              <span class="nav-icon">&#9673;</span>
              <span class="nav-label">Lobbies</span>
            </RouterLink>
            <RouterLink class="side-link chrome-nav-item" :class="{ active: isResultsRoute }" to="/results">
              <span class="nav-icon">R</span>
              <span class="nav-label">Results</span>
            </RouterLink>
            <RouterLink class="side-link chrome-nav-item" :class="{ active: isDiscordRoute }" to="/discord">
              <span class="nav-icon">D</span>
              <span class="nav-label">Discord</span>
            </RouterLink>
            <RouterLink class="side-link chrome-nav-item" :class="{ active: isAboutRoute }" to="/about">
              <span class="nav-icon">?</span>
              <span class="nav-label">About</span>
            </RouterLink>
          </div>
        </aside>

        <main class="app-main window-panel">
          <div :class="['window-titlebar', { 'lobby-titlebar': isInLobby }]">
            <span class="window-titlebar-label">{{ currentWindowTitle }}</span>
            <MatchPhaseTracker
              v-if="isInLobby"
              :current-phase="currentLobbyPhase"
              :phases="lobbyTrackerPhases"
              compact
            />
            <span v-else class="window-titlebar-meta">{{ currentWindowTitle }}</span>
          </div>
          <div ref="mainWindowBody" class="main-window-body">
            <RouterView />
          </div>
        </main>

        <aside class="app-right window-panel">
          <div class="window-titlebar">
            <span class="window-titlebar-label">Session</span>
          </div>
          <div class="sidebar-body">
            <button class="profile-button chrome-nav-item" :class="{ active: isProfileRoute }" type="button" title="Profile page" @click="handleProfile">
              <span class="nav-icon profile-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" role="img">
                  <circle cx="12" cy="8" r="4" fill="currentColor" />
                  <path d="M4 20c0-4 4-6 8-6s8 2 8 6" fill="currentColor" />
                </svg>
              </span>
              <span class="nav-label">{{ authStore.playerName }}</span>
            </button>
            <button
              class="group-button chrome-nav-item"
              :class="{ active: isGroupRoute, 'group-highlighted': groupStore.inGroup }"
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
              <span v-if="groupStore.inGroup" class="group-status-check" aria-hidden="true">✓</span>
            </button>
            <button
              v-if="authStore.isAdmin || authStore.canToggleAdmin"
              class="admin-button chrome-nav-item"
              :class="{ active: isAdminRoute }"
              type="button"
              title="Admin diagnostics"
              @click="router.push('/admin')"
            >
              <span class="nav-icon admin-icon" aria-hidden="true">A</span>
              <span class="nav-label">Admin</span>
            </button>
            <button
              class="theme-button chrome-nav-item"
              type="button"
              :aria-label="`Current theme: ${themeLabel}. Switch to ${nextThemeLabel}`"
              :title="`Switch to ${nextThemeLabel}`"
              @click="cycleTheme"
            >
              <span class="nav-icon theme-icon" aria-hidden="true">{{ themeIcon }}</span>
              <span class="nav-label">{{ themeLabel }}</span>
            </button>
          </div>
        </aside>

        <footer class="legal-footer" aria-label="Legal notice">
          <span>&copy; 2026 Squad Comp Matchmaking. All rights reserved.</span>
          <RouterLink to="/terms">Terms</RouterLink>
          <RouterLink to="/privacy">Privacy</RouterLink>
          <span>Independent community tool. Not affiliated with, endorsed by, or sponsored by Offworld Industries, Valve, or Steam.</span>
        </footer>
      </div>

      <MatchAcceptModal
        :active="isMatchAcceptParticipant"
        :is-cancelled="isMatchAcceptCancelled"
        :cancel-reason="queueStore.matchAccept.cancelReason"
        :countdown="queueStore.matchAccept.countdown ?? 0"
        :accepted-count="queueStore.matchAccept.acceptedCount"
        :required-count="queueStore.matchAccept.requiredCount"
        :accepted-players="acceptedMatchPlayers"
        :player-profiles="queueStore.matchAccept.playerProfiles"
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
      <strong>{{ rootStore.globalError }}</strong>
      <span v-if="rootStore.globalErrorDetails">{{ rootStore.globalErrorDetails }}</span>
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
  max-width: var(--page-width);
  min-height: 0;
  height: 100vh;
  height: 100dvh;
  --nav-icon-box: 30px;
  --nav-column-width: 140px;
  --shell-gap: 8px;
  background: transparent;
  display: grid;
  grid-template-columns: var(--nav-column-width) minmax(0, 1fr) var(--nav-column-width);
  grid-template-rows: auto minmax(0, 1fr) auto;
  gap: var(--shell-gap);
  padding: 8px;
  align-content: start;
}

.legal-footer {
  grid-column: 1 / -1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px 14px;
  flex-wrap: wrap;
  min-height: 24px;
  padding: 3px 8px 0;
  color: var(--text-soft);
  font-family: var(--font-mono);
  font-size: 0.62rem;
  line-height: 1.25;
  text-align: center;
}

.legal-footer a {
  color: var(--accent-strong);
  font-weight: 800;
  text-decoration: none;
}

.legal-footer a:hover {
  text-decoration: underline;
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
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: grid;
  gap: 4px;
  max-width: min(360px, calc(100vw - 32px));
  width: max-content;
  background: var(--danger-soft);
  color: var(--danger);
  padding: 0.9rem;
  border-radius: var(--radius-md);
  border: 1px solid color-mix(in srgb, var(--danger) 35%, var(--surface-border));
  box-shadow: var(--window-shadow);
  z-index: 9999;
}

.error-message strong,
.error-message span {
  display: block;
}

.app-left {
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: sticky;
  top: 8px;
  height: fit-content;
  align-self: start;
  z-index: 2;
}

.nav-label {
  display: block;
  flex: 1 1 auto;
  white-space: nowrap;
  text-align: center;
  position: relative;
  left: -6px;
  padding-right: 6px;
}

.app-main {
  display: flex;
  flex-direction: column;
  padding: 0;
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  position: relative;
  z-index: 1;
}

.main-window-body {
  flex: 1;
  min-height: 0;
  overflow: auto;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), transparent 18%),
    var(--panel-bg-muted);
}

.lobby-titlebar {
  height: 40px;
  min-height: 40px;
  align-items: center;
  padding: 0 0 0 12px;
}

.lobby-titlebar .window-titlebar-label {
  flex: 0 0 auto;
  align-self: center;
  min-width: 64px;
  margin-right: 6px;
}

.lobby-titlebar :deep(.phase-tracker) {
  --tracker-arrow: #6f9f75;
  align-self: center;
  flex: 1 1 auto;
  height: 100%;
  min-width: 0;
  border: 0;
  background: transparent;
}

.lobby-titlebar :deep(.phase-tracker.compact .phase-step) {
  min-height: 0;
  height: 100%;
  padding: 5px 6px;
  border-right-color: rgba(255, 255, 255, 0.16);
  color: rgba(248, 251, 255, 0.72);
  font-family: var(--font-display);
  font-size: clamp(0.66rem, 0.82vw, 0.82rem);
  font-weight: 800;
  letter-spacing: 0.018em;
  text-shadow:
    0 1px 0 rgba(255, 255, 255, 0.2),
    0 3px 10px rgba(93, 86, 73, 0.14);
}

.lobby-titlebar :deep(.phase-connector.is-complete) {
  background: var(--tracker-arrow);
  box-shadow:
    0 0 5px rgba(111, 159, 117, 0.42),
    0 1px 0 rgba(0, 0, 0, 0.28);
}

.lobby-titlebar :deep(.phase-connector.is-leading::after) {
  border-left-color: var(--tracker-arrow);
  filter: drop-shadow(0 0 4px rgba(111, 159, 117, 0.52)) drop-shadow(0 1px 0 rgba(0, 0, 0, 0.32));
}

.lobby-titlebar :deep(.phase-step.is-complete),
.lobby-titlebar :deep(.phase-step.is-current) {
  color: var(--text-main);
}

.lobby-titlebar :deep(.phase-dot) {
  border-color: rgba(255, 255, 255, 0.38);
  background: rgba(255, 255, 255, 0.12);
}

.lobby-titlebar :deep(.phase-step.is-complete .phase-dot) {
  background: color-mix(in srgb, var(--tracker-arrow) 72%, var(--text-main) 28%);
  border-color: color-mix(in srgb, var(--tracker-arrow) 82%, var(--text-main) 18%);
  color: var(--phase-check-text);
}

.lobby-titlebar :deep(.phase-step.is-current .phase-dot) {
  border-color: var(--tracker-arrow);
  box-shadow:
    0 0 0 2px var(--tracker-arrow),
    0 0 7px rgba(111, 159, 117, 0.42);
}

.lobby-titlebar :deep(.phase-step.is-current .phase-dot::after) {
  background: var(--tracker-arrow);
}

.app-right {
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: sticky;
  top: 8px;
  height: fit-content;
  align-self: start;
  z-index: 2;
}

.sidebar-body {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px;
  flex: 1;
  min-height: 0;
}

.profile-button {
  font-weight: 700;
  padding: 0 0.3rem;
  height: 31px;
}

.group-button,
.add-server-button,
.admin-button,
.theme-button {
  font-weight: 700;
  padding: 0 0.3rem;
  height: 31px;
}

.theme-button {
  margin-top: auto;
}

.theme-icon {
  font-family: var(--font-mono);
  font-size: 1.3rem;
}

.admin-button .nav-icon {
  font-family: var(--font-mono);
  font-size: 1.3rem;
  font-weight: 800;
}

.add-server-button .nav-icon {
  font-family: var(--font-mono);
  font-size: 1.52rem;
  font-weight: 800;
}

.nav-icon {
  opacity: 1;
  font-size: 1.42em;
  flex: 0 0 var(--nav-icon-box);
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

.side-link:has(.queue-spinner) {
  background: var(--nav-card-active-bg);
  border-color: var(--nav-card-active-border);
  box-shadow: var(--nav-card-active-shadow);
  color: var(--text-main);
}

.side-link.play-highlighted,
.side-link.play-highlighted:hover,
.side-link.play-highlighted.router-link-active,
.side-link.play-highlighted.active,
.group-button.group-highlighted,
.group-button.group-highlighted:hover,
.group-button.group-highlighted.active {
  background: var(--nav-card-active-bg);
  border-color: var(--nav-card-active-border);
  box-shadow: var(--nav-card-active-shadow);
  color: var(--text-main);
}

.side-link:has(.queue-spinner):hover,
.side-link:has(.queue-spinner).router-link-active,
.side-link.play-highlighted:focus-visible,
.group-button.group-highlighted:focus-visible {
  background: var(--nav-card-active-bg);
  border-color: var(--nav-card-active-border);
}

.side-link.router-link-active,
.profile-button:active,
.group-button:active,
.admin-button:active,
.theme-button:active {
  background: var(--nav-card-active-bg);
  border-color: var(--nav-card-active-border);
  box-shadow: var(--nav-card-active-shadow);
}

.side-link.router-link-active .nav-icon,
.side-link:has(.queue-spinner) .nav-icon,
.side-link.play-highlighted .nav-icon,
.group-button.group-highlighted .nav-icon,
.admin-button .nav-icon {
  color: currentColor;
}

.queue-spinner {
  position: absolute;
  right: 8px;
  width: 12px;
  height: 12px;
  border: 2px solid currentColor;
  border-right-color: transparent;
  border-radius: 50%;
  animation: queue-spin 0.9s steps(8) infinite;
}

.group-status-check {
  position: absolute;
  right: 8px;
  width: 15px;
  height: 15px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid currentColor;
  border-radius: 50%;
  color: currentColor;
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 900;
  line-height: 1;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22);
}

@keyframes queue-spin {
  to {
    transform: rotate(1turn);
  }
}

@media (max-width: 1024px) {
  .app-shell {
    --nav-column-width: 144px;
  }
}

@media (max-width: 768px) {
  .app-shell {
    grid-template-columns: 1fr;
    grid-template-rows: auto auto auto minmax(0, 1fr) auto;
    min-height: 0;
    height: auto;
    min-height: 100vh;
    min-height: 100dvh;
    gap: 8px;
    padding: 8px;
  }

  .app-left,
  .app-right {
    width: 100%;
    position: static;
    height: auto;
  }

  .app-main {
    overflow: visible;
  }

  .main-window-body {
    overflow: visible;
  }

  .app-left .side-link,
  .app-right .profile-button,
  .app-right .group-button,
  .app-right .add-server-button,
  .app-right .admin-button,
  .app-right .theme-button {
    width: max-content;
    min-width: 0;
    display: inline-flex;
    gap: 8px;
    padding: 0 12px;
  }

  .sidebar-body {
    flex-direction: row;
    justify-content: flex-start;
    flex-wrap: nowrap;
    gap: 6px;
    padding: 8px;
    overflow-x: auto;
    scrollbar-width: thin;
    -webkit-overflow-scrolling: touch;
  }

  .theme-button {
    margin-top: 0;
  }

}

@media (max-width: 480px) {
  .auth-shell {
    padding-inline: 12px;
  }

  .app-shell {
    gap: 6px;
    padding: 6px;
  }

  .top-banner {
    min-height: 48px;
    padding: 0;
  }

  .brand-mark {
    width: 36px;
    height: 36px;
  }

  .app-left .side-link,
  .app-right .profile-button,
  .app-right .group-button,
  .app-right .add-server-button,
  .app-right .admin-button,
  .app-right .theme-button {
    width: max-content;
    justify-content: center;
  }

  .nav-label {
    left: 0;
    padding-right: 0;
  }

  .lobby-titlebar {
    height: auto;
    min-height: 34px;
    flex-wrap: wrap;
    padding: 7px 8px;
  }

  .lobby-titlebar .window-titlebar-label {
    min-width: 0;
  }

  .lobby-titlebar :deep(.phase-tracker) {
    flex-basis: 100%;
    min-height: 34px;
  }

  .legal-footer {
    padding-inline: 4px;
    font-size: 0.56rem;
  }

}

</style>
