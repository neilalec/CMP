<script setup>
import { computed, ref, watch } from 'vue';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';
import { useAuthStore } from './stores/authStore';
import { useSocketStore } from './stores/socketStore';
import { useRootStore } from './stores/rootStore';
import { useLobbyStore } from './stores/lobbyStore';
import { useQueueStore } from './stores/queueStore';
import { useGroupStore } from './stores/groupStore';
import { useAppSession } from './features/app/composables/useAppSession';
import { useMatchAcceptChime } from './features/app/composables/useMatchAcceptChime';
import MatchAcceptModal from './features/app/components/MatchAcceptModal.vue';

const router = useRouter();
const route = useRoute();
const authStore = useAuthStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();
const lobbyStore = useLobbyStore();
const queueStore = useQueueStore();
const groupStore = useGroupStore();
const mobileNavOpen = ref(false);

const {
  isMatchAcceptParticipant,
  isMatchAcceptCancelled,
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

const canViewAdmin = computed(() => authStore.isAdmin || authStore.canToggleAdmin);
const matchesActive = computed(() =>
  route.path === '/matches' || route.path.startsWith('/wardogs/lobby/')
);
const acceptedMatchPlayers = computed(() => queueStore.matchAccept.acceptedPlayers || []);
const waitingMatchPlayers = computed(() => {
  const accepted = new Set(acceptedMatchPlayers.value);
  return (queueStore.matchAccept.players || []).filter((player) => !accepted.has(player));
});

useMatchAcceptChime({ queueStore, authStore, isMatchAcceptParticipant });
watch(() => route.fullPath, () => { mobileNavOpen.value = false; });
</script>

<template>
  <div class="app" :class="{ 'legacy-ui': route.meta.legacyStyles }">
    <template v-if="authStore.isLoggedIn">
      <div class="app-shell cmp-page">
        <header class="app-header">
          <div class="header-inner">
            <RouterLink class="brand cmp-wordmark" to="/play" aria-label="CMP home" />

            <nav id="primary-navigation" class="primary-nav" :class="{ 'is-open': mobileNavOpen }" aria-label="Primary">
              <RouterLink to="/play" @click="mobileNavOpen = false">Play</RouterLink>
              <RouterLink to="/matches" :class="{ 'is-active': matchesActive }" @click="mobileNavOpen = false">Matches</RouterLink>
              <RouterLink to="/profile" @click="mobileNavOpen = false">Profile</RouterLink>
              <RouterLink v-if="canViewAdmin" to="/admin" @click="mobileNavOpen = false">Admin</RouterLink>
            </nav>

            <details class="account-menu">
              <summary :aria-label="`Account menu for ${authStore.playerName || authStore.username}`">
                <span class="account-avatar" aria-hidden="true">{{ (authStore.playerName || authStore.username || '?').slice(0, 1).toUpperCase() }}</span>
                <span class="account-name">{{ authStore.playerName || authStore.username }}</span>
              </summary>
              <div class="account-menu-items">
                <RouterLink to="/group">Group</RouterLink>
                <RouterLink to="/about">About</RouterLink>
                <RouterLink to="/discord">Discord</RouterLink>
              </div>
            </details>

            <button
              class="mobile-nav-toggle"
              type="button"
              :aria-expanded="mobileNavOpen"
              aria-controls="primary-navigation"
              :aria-label="mobileNavOpen ? 'Close navigation' : 'Open navigation'"
              @click="mobileNavOpen = !mobileNavOpen"
            >
              <span aria-hidden="true">{{ mobileNavOpen ? '×' : '☰' }}</span>
            </button>
          </div>
        </header>

        <main class="app-main">
          <RouterView />
        </main>

        <footer class="legal-footer" aria-label="Site links">
          <span>&copy; 2026 CMP</span>
          <RouterLink to="/terms">Terms</RouterLink>
          <RouterLink to="/privacy">Privacy</RouterLink>
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
        :finalizing-lobby="queueStore.matchAccept.finalizingLobby"
        @accept="handleAcceptMatch"
        @close="handleCloseMatchAccept"
        @dismiss="handleDismissMatchAccept"
      />
    </template>

    <div v-else class="auth-shell" :class="{ 'is-auth-view': route.path === '/auth' }">
      <RouterView />
    </div>

    <div v-if="rootStore.globalError" class="error-message" role="alert">
      <strong>{{ rootStore.globalError }}</strong>
      <span v-if="rootStore.globalErrorDetails">{{ rootStore.globalErrorDetails }}</span>
    </div>
  </div>
</template>

<style scoped>
.app { min-height: 100vh; min-height: 100dvh; width: 100%; }
.app-shell { min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; }
.app-header { position: relative; z-index: 20; display: flex; justify-content: center; border-bottom: 1px solid var(--cmp-border); background: color-mix(in srgb, var(--cmp-bg-elevated) 94%, transparent); backdrop-filter: blur(16px); }
.header-inner { width: min(100%, var(--cmp-content-max)); min-height: 70px; margin: 0 auto; padding: 0 var(--cmp-page-gutter); display: flex; align-items: center; gap: clamp(24px, 4vw, 58px); }
.brand { flex: 0 0 72px; width: 72px; height: 24px; text-decoration: none; }
.primary-nav { align-self: stretch; display: flex; align-items: stretch; gap: clamp(12px, 2vw, 28px); }
.primary-nav a { display: inline-flex; align-items: center; position: relative; padding: 0 4px; color: var(--cmp-text-secondary); font-size: .88rem; font-weight: 700; text-decoration: none; }
.primary-nav a:hover { color: var(--cmp-text); }
.primary-nav a.router-link-active, .primary-nav a.is-active { color: var(--cmp-text); }
.primary-nav a.router-link-active::after, .primary-nav a.is-active::after { content: ''; position: absolute; inset: auto 0 0; height: 2px; background: var(--cmp-primary); }
.account-menu { position: relative; margin-left: auto; flex: 0 1 auto; min-width: 0; }
.account-menu summary { display: flex; align-items: center; gap: 9px; cursor: pointer; list-style: none; color: var(--cmp-text-secondary); font-size: .82rem; font-weight: 700; }
.account-menu summary::-webkit-details-marker { display: none; }
.account-menu summary:hover { color: var(--cmp-text); }
.account-avatar { display: grid; place-items: center; width: 30px; height: 30px; flex: 0 0 30px; border: 1px solid var(--cmp-border); border-radius: 50%; background: var(--cmp-surface-raised); color: var(--cmp-primary); font-size: .76rem; }
.account-name { max-width: 140px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.account-menu-items { position: absolute; right: 0; top: calc(100% + 17px); z-index: 30; display: grid; min-width: 168px; padding: 6px; border: 1px solid var(--cmp-border); border-radius: var(--cmp-radius-md); background: var(--cmp-surface-raised); box-shadow: var(--cmp-shadow-md); }
.account-menu-items a { padding: 10px 12px; border-radius: var(--cmp-radius-sm); color: var(--cmp-text-secondary); text-decoration: none; font-size: .85rem; }
.account-menu-items a:hover, .account-menu-items a:focus-visible { background: var(--cmp-surface-strong); color: var(--cmp-text); text-decoration: none; }
.mobile-nav-toggle { display: none; }
.app-main { width: min(100%, var(--cmp-content-max)); flex: 1; min-width: 0; margin: 0 auto; }
.legal-footer { width: min(100%, var(--cmp-content-max)); margin: 0 auto; padding: 20px var(--cmp-page-gutter) 24px; display: flex; gap: 18px; align-items: center; flex-wrap: wrap; color: var(--cmp-text-muted); font-size: .72rem; }
.legal-footer a { color: var(--cmp-text-secondary); text-decoration: none; }
.legal-footer a:hover { color: var(--cmp-text); }
.auth-shell { min-height: 100vh; min-height: 100dvh; display: flex; align-items: center; justify-content: center; padding: 32px var(--cmp-page-gutter); }
.error-message { position: fixed; right: 16px; bottom: 16px; z-index: 100; display: grid; gap: 4px; max-width: min(420px, calc(100vw - 32px)); padding: 12px 16px; border: 1px solid var(--cmp-danger); border-radius: var(--cmp-radius-md); background: var(--cmp-surface-raised); color: var(--cmp-text); box-shadow: var(--cmp-shadow-md); }
.error-message span { color: var(--cmp-text-secondary); }

@media (max-width: 760px) {
  .header-inner { min-height: 62px; flex-wrap: wrap; gap: 0 12px; }
  .brand { flex-basis: 64px; width: 64px; height: 22px; }
  .primary-nav { order: 4; width: 100%; display: none; align-self: auto; padding: 5px 0 12px; gap: 3px; }
  .primary-nav.is-open { display: grid; }
  .primary-nav a { min-height: 42px; padding: 0 12px; border-radius: var(--cmp-radius-sm); }
  .primary-nav a.router-link-active, .primary-nav a.is-active { background: var(--cmp-surface-strong); }
  .primary-nav a.router-link-active::after, .primary-nav a.is-active::after { inset: 8px auto 8px 0; width: 2px; height: auto; }
  .account-menu { margin-left: auto; }
  .account-name { display: none; }
  .account-menu-items { top: calc(100% + 14px); }
  .mobile-nav-toggle { display: grid; place-items: center; width: 38px; height: 38px; min-height: 38px; padding: 0; border: 1px solid var(--cmp-border); background: var(--cmp-surface-raised); color: var(--cmp-text); font-size: 1.1rem; }
  .legal-footer { padding-block: 16px 20px; }
}
</style>
