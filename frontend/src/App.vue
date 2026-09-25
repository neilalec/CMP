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
const accountMenu = ref(null);

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
watch(() => route.fullPath, () => {
  mobileNavOpen.value = false;
  if (accountMenu.value) accountMenu.value.open = false;
});
</script>

<template>
  <div class="app" :class="{ 'legacy-ui': route.meta.legacyStyles }">
    <template v-if="authStore.isLoggedIn">
      <div class="app-shell cmp-page">
        <header class="app-header">
          <div class="header-inner">
            <RouterLink class="brand" to="/play" aria-label="CMP home">
              <span class="brand-mark cmp-wordmark" aria-hidden="true" />
              <span class="brand-divider" aria-hidden="true" />
              <span class="brand-product">WARDOGS</span>
            </RouterLink>

            <nav id="primary-navigation" class="primary-nav" :class="{ 'is-open': mobileNavOpen }" aria-label="Primary">
              <RouterLink to="/play" @click="mobileNavOpen = false">Play</RouterLink>
              <RouterLink to="/matches" :class="{ 'is-active': matchesActive }" @click="mobileNavOpen = false">Matches</RouterLink>
              <RouterLink to="/group" @click="mobileNavOpen = false">Group</RouterLink>
              <RouterLink class="mobile-profile-link" to="/profile" @click="mobileNavOpen = false">Profile</RouterLink>
              <RouterLink v-if="canViewAdmin" class="admin-nav-link" to="/admin" @click="mobileNavOpen = false">Admin</RouterLink>
            </nav>

            <RouterLink
              v-if="queueStore.wardogsLobbyId"
              class="current-match-link"
              :to="`/wardogs/lobby/${queueStore.wardogsLobbyId}`"
              @click="mobileNavOpen = false"
            >
              <span class="current-match-indicator" aria-hidden="true" />
              <span class="current-match-full">Open match</span>
              <span class="current-match-short">Match</span>
            </RouterLink>

            <details ref="accountMenu" class="account-menu">
              <summary :aria-label="`Account menu for ${authStore.playerName || authStore.username}`">
                <span class="account-avatar" aria-hidden="true">{{ (authStore.playerName || authStore.username || '?').slice(0, 1).toUpperCase() }}</span>
                <span class="account-name">{{ authStore.playerName || authStore.username }}</span>
              </summary>
              <div class="account-menu-items">
                <RouterLink to="/profile">Profile</RouterLink>
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
              <span class="nav-toggle-lines" aria-hidden="true"><i></i><i></i><i></i></span>
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
.app-header { position: relative; z-index: 20; border-bottom: 1px solid var(--cmp-border); background: var(--cmp-bg-elevated); }
.header-inner { width: min(100%, var(--cmp-content-max)); min-height: 62px; margin: 0 auto; padding: 0 var(--cmp-page-gutter); display: flex; align-items: center; gap: clamp(18px, 2.4vw, 32px); }
.brand { display: inline-flex; align-items: center; gap: 11px; flex: none; text-decoration: none; }
.brand-mark { width: 77px; height: 26px; }
.brand-divider { width: 1px; height: 19px; background: var(--cmp-border-strong); }
.brand-product { color: var(--cmp-text-secondary); font-size: .68rem; font-weight: 800; letter-spacing: .16em; }
.primary-nav { align-self: stretch; display: flex; align-items: stretch; gap: clamp(8px, 1.5vw, 20px); }
.primary-nav a { display: inline-flex; align-items: center; position: relative; padding: 0 4px; color: var(--cmp-text-muted); font-size: .83rem; font-weight: 650; text-decoration: none; white-space: nowrap; }
.primary-nav a:hover { color: var(--cmp-text); }
.primary-nav a.router-link-active, .primary-nav a.is-active { color: var(--cmp-text); }
.primary-nav a.router-link-active::after, .primary-nav a.is-active::after { content: ''; position: absolute; inset: auto 0 0; height: 2px; background: var(--cmp-primary-hover); }
.primary-nav .mobile-profile-link { display: none; }
.primary-nav .admin-nav-link { margin-left: 3px; color: var(--cmp-text-muted); }
.current-match-link { display: inline-flex; align-items: center; gap: 8px; flex: none; min-height: 42px; margin-left: auto; padding: 7px 9px; color: var(--cmp-text); font-size: .78rem; font-weight: 700; text-decoration: none; white-space: nowrap; }
.current-match-link:hover { color: var(--cmp-primary-hover); }
.current-match-indicator { width: 6px; height: 6px; border-radius: 50%; background: var(--cmp-success); }
.current-match-short { display: none; }
.account-menu { position: relative; flex: 0 1 auto; min-width: 0; margin-left: auto; }
.current-match-link + .account-menu { margin-left: 0; }
.account-menu summary { display: flex; align-items: center; justify-content: center; gap: 8px; min-width: 42px; min-height: 42px; cursor: pointer; list-style: none; color: var(--cmp-text-secondary); font-size: .8rem; font-weight: 650; }
.account-menu summary::-webkit-details-marker { display: none; }
.account-menu summary:hover { color: var(--cmp-text); }
.account-avatar { display: grid; place-items: center; width: 30px; height: 30px; flex: 0 0 30px; border: 1px solid var(--cmp-border-strong); border-radius: 50%; background: var(--cmp-surface); color: var(--cmp-text); font-size: .72rem; }
.account-name { max-width: 120px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.account-menu-items { position: absolute; right: 0; top: calc(100% + 9px); z-index: 30; display: grid; min-width: 164px; padding: 6px; border: 1px solid var(--cmp-border-strong); border-radius: var(--cmp-radius-md); background: var(--cmp-surface-raised); box-shadow: var(--cmp-shadow-md); }
.account-menu-items a { padding: 10px 12px; border-radius: var(--cmp-radius-sm); color: var(--cmp-text-secondary); text-decoration: none; font-size: .83rem; }
.account-menu-items a:hover, .account-menu-items a:focus-visible { background: var(--cmp-surface-strong); color: var(--cmp-text); text-decoration: none; }
.mobile-nav-toggle { display: none; }
.app-main { width: min(100%, var(--cmp-content-max)); flex: 1; min-width: 0; margin: 0 auto; }
.legal-footer { width: min(100%, var(--cmp-content-max)); margin: 0 auto; padding: 20px var(--cmp-page-gutter) 24px; display: flex; gap: 18px; align-items: center; flex-wrap: wrap; color: var(--cmp-text-muted); font-size: .75rem; }
.legal-footer a { color: var(--cmp-text-secondary); text-decoration: none; }
.legal-footer a:hover { color: var(--cmp-text); }
.auth-shell { min-height: 100vh; min-height: 100dvh; display: flex; align-items: center; justify-content: center; padding: 32px var(--cmp-page-gutter); }
.error-message { position: fixed; right: 16px; bottom: 16px; z-index: 100; display: grid; gap: 4px; max-width: min(420px, calc(100vw - 32px)); padding: 12px 16px; border: 1px solid var(--cmp-danger); border-radius: var(--cmp-radius-md); background: var(--cmp-surface-raised); color: var(--cmp-text); box-shadow: var(--cmp-shadow-md); }
.error-message span { color: var(--cmp-text-secondary); }
:where(.brand, .primary-nav a, .current-match-link, .account-menu summary, .mobile-nav-toggle, .legal-footer a):focus-visible { outline: 2px solid var(--cmp-focus); outline-offset: 3px; }

@media (max-width: 900px) {
  .header-inner { min-height: 58px; flex-wrap: wrap; gap: 0 12px; }
  .brand-mark { width: 70px; height: 24px; }
  .primary-nav { order: 4; width: 100%; display: none; align-self: auto; padding: 8px 0 14px; gap: 2px; border-top: 1px solid var(--cmp-border); }
  .primary-nav.is-open { display: grid; }
  .primary-nav a { min-height: 44px; padding: 0 12px; border-radius: var(--cmp-radius-sm); }
  .primary-nav .mobile-profile-link { display: inline-flex; }
  .primary-nav a.router-link-active, .primary-nav a.is-active { background: var(--cmp-surface); }
  .primary-nav a.router-link-active::after, .primary-nav a.is-active::after { inset: 8px auto 8px 0; width: 2px; height: auto; }
  .primary-nav .admin-nav-link { margin-left: 0; border-top: 1px solid var(--cmp-border); border-radius: 0; }
  .current-match-link { margin-left: auto; }
  .account-menu { margin-left: 0; }
  .mobile-nav-toggle { display: grid; place-items: center; width: 42px; height: 42px; min-height: 42px; padding: 0; border: 1px solid var(--cmp-border); border-radius: var(--cmp-radius-sm); background: transparent; color: var(--cmp-text); cursor: pointer; }
  .nav-toggle-lines { display: grid; gap: 4px; }
  .nav-toggle-lines i { display: block; width: 16px; height: 1px; background: currentColor; }
  .legal-footer { padding-block: 16px 20px; }
}
@media (max-width: 520px) {
  .brand { gap: 8px; }
  .brand-divider { height: 16px; }
  .brand-product { font-size: .62rem; letter-spacing: .11em; }
  .account-name { display: none; }
  .current-match-link { font-size: .72rem; gap: 6px; padding-inline: 4px; }
  .current-match-full { display: none; }
  .current-match-short { display: inline; }
}
</style>
