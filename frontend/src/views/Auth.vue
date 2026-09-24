<script setup>
import { RouterLink, useRouter } from 'vue-router';
import { PASSWORD_AUTH_ENABLED } from '../config';
import { useAuthStore } from '../stores/authStore';
import { useLobbyStore } from '../stores/lobbyStore';
import { useRootStore } from '../stores/rootStore';
import { useSocketStore } from '../stores/socketStore';
import { useAuthView } from '../features/auth/composables/useAuthView';

const router = useRouter();
const authStore = useAuthStore();
const rootStore = useRootStore();
const socketStore = useSocketStore();
const lobbyStore = useLobbyStore();

const {
  formType,
  username,
  password,
  loading,
  handleSubmit,
  toggleForm,
  handleSteamSignIn
} = useAuthView({
  router,
  authStore,
  rootStore,
  socketStore,
  lobbyStore
});
</script>

<template>
  <main class="auth-layout cmp-page">
    <section class="auth-container cmp-surface cmp-surface--floating" aria-labelledby="auth-title">
      <header class="auth-brand">
        <span class="auth-mark cmp-wordmark" role="img" aria-label="CMP"></span>
        <span class="auth-descriptor">WARDOGS matchmaking</span>
      </header>

      <div class="auth-content">
        <h1 id="auth-title" class="cmp-heading">Sign in</h1>
        <button
          class="steam-button cmp-button cmp-button--primary"
          type="button"
          aria-label="Continue with Steam"
          @click="handleSteamSignIn"
        >
          Continue with Steam
        </button>
        <p class="auth-security-copy">Sign in securely with Steam.</p>

        <p class="auth-legal-copy">
          By continuing, you agree to the <RouterLink to="/terms">Terms</RouterLink>
          and acknowledge the <RouterLink to="/privacy">Privacy Policy</RouterLink>.
        </p>

        <details v-if="PASSWORD_AUTH_ENABLED" class="auth-local-access">
          <summary>Use local account</summary>
          <form class="auth-local-form" @submit.prevent="handleSubmit">
            <label for="auth-username">Username</label>
            <input
              id="auth-username"
              v-model="username"
              class="cmp-input"
              type="text"
              autocomplete="username"
              required
            />
            <label for="auth-password">Password</label>
            <input
              id="auth-password"
              v-model="password"
              class="cmp-input"
              type="password"
              :autocomplete="formType === 'login' ? 'current-password' : 'new-password'"
              required
            />
            <button class="local-submit cmp-button cmp-button--secondary" type="submit" :disabled="loading">
              {{ loading ? 'Working...' : (formType === 'login' ? 'Login' : 'Register') }}
            </button>
            <button class="form-toggle cmp-button" type="button" @click="toggleForm">
              {{ formType === 'login' ? 'Create account' : 'Back to login' }}
            </button>
          </form>
        </details>
      </div>
    </section>

    <section class="auth-features" aria-label="WARDOGS features">
      <div class="auth-feature">
        <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
          <rect x="4" y="7" width="24" height="21" rx="2" />
          <path d="M10 4v6M22 4v6M4 13h24M10 18h4M18 18h4M10 23h4M18 23h4" />
        </svg>
        <h2>Organised Matches</h2>
        <p>Structured three-faction matchmaking</p>
      </div>
      <div class="auth-feature">
        <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
          <circle cx="16" cy="11" r="4" />
          <path d="M8 27v-2a8 8 0 0 1 16 0v2H8ZM6 12a3 3 0 1 0 0 6M26 12a3 3 0 1 1 0 6M4 27v-2a6 6 0 0 1 4-5.7M28 27v-2a6 6 0 0 0-4-5.7" />
        </svg>
        <h2>Play Together</h2>
        <p>Queue solo or with your group</p>
      </div>
      <div class="auth-feature">
        <svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">
          <rect x="5" y="5" width="22" height="9" rx="2" />
          <rect x="5" y="18" width="22" height="9" rx="2" />
          <path d="M10 9.5h.01M10 22.5h.01M16 14v4M22 14v4" />
        </svg>
        <h2>Live Match Rooms</h2>
        <p>Rosters, join details and live state</p>
      </div>
    </section>
  </main>
</template>

<style scoped>
:global(.auth-shell.is-auth-view) {
  position: relative;
  isolation: isolate;
  overflow: hidden;
  background: var(--cmp-bg) url('../assets/brand/cmp-auth-background.webp') center 44% / cover no-repeat;
}

:global(.auth-shell.is-auth-view::before) {
  position: absolute;
  z-index: 0;
  inset: 0;
  background: linear-gradient(180deg, rgba(3, 9, 14, .42), rgba(3, 9, 14, .58) 56%, rgba(3, 9, 14, .83));
  content: '';
  pointer-events: none;
}

:global(.auth-shell.is-auth-view::after) {
  position: absolute;
  z-index: 0;
  inset: 0;
  background: radial-gradient(ellipse 72% 76% at 50% 43%, transparent 21%, rgba(2, 7, 11, .55) 100%);
  content: '';
  pointer-events: none;
}

.auth-layout {
  position: relative;
  z-index: 1;
  display: grid;
  justify-items: center;
  gap: 44px;
  width: min(100%, 920px);
  margin: 0 auto;
}

.auth-container {
  width: min(100%, 480px);
  padding: clamp(34px, 4vw, 48px);
  text-align: center;
}

.auth-brand {
  display: grid;
  justify-items: center;
  gap: 11px;
  margin-bottom: 42px;
}

.auth-mark {
  width: 185px;
}

.auth-descriptor {
  color: var(--cmp-text-muted);
  font-size: .78rem;
  font-weight: 600;
  letter-spacing: .18em;
  text-transform: uppercase;
}

.auth-content h1 {
  margin: 0 0 24px;
  font-size: 1.95rem;
  letter-spacing: -.02em;
}

.steam-button {
  width: 100%;
  min-height: 52px;
  font-size: 1.15rem;
  letter-spacing: .01em;
}

.steam-button:focus-visible,
.form-toggle:focus-visible,
.auth-local-access summary:focus-visible,
.auth-legal-copy a:focus-visible {
  outline: 2px solid var(--cmp-focus);
  outline-offset: 4px;
}

.auth-security-copy {
  margin: 18px 0 0;
  color: var(--cmp-text-secondary);
  font-size: .98rem;
}

.auth-legal-copy {
  max-width: 380px;
  margin: 24px auto 0;
  color: var(--cmp-text-muted);
  font-size: .9rem;
  line-height: 1.6;
}

.auth-legal-copy a {
  color: var(--cmp-text-secondary);
  text-decoration: underline;
  text-decoration-color: var(--cmp-border-strong);
  text-underline-offset: 3px;
}

.auth-legal-copy a:hover {
  color: var(--cmp-text);
}

.auth-local-access {
  width: 100%;
  margin: 28px auto 0;
  color: var(--cmp-text-secondary);
  font-size: .94rem;
  text-align: left;
}

.auth-local-access summary {
  width: fit-content;
  margin: 0 auto;
  color: var(--cmp-text-secondary);
  cursor: pointer;
  text-underline-offset: 4px;
}

.auth-local-access summary:hover {
  color: var(--cmp-text);
}

.auth-local-form {
  display: grid;
  gap: 9px;
  width: 100%;
  margin: 20px auto 0;
  color: var(--cmp-text-secondary);
  font-size: .95rem;
}

.auth-local-form input,
.auth-local-form button {
  width: 100%;
  min-height: 44px;
}

.auth-local-form input {
  margin-bottom: 5px;
}

.auth-local-form .local-submit {
  margin-top: 6px;
}

.auth-local-form .form-toggle {
  border-color: transparent;
  background: transparent;
  box-shadow: none;
  color: var(--cmp-text-secondary);
  text-decoration: underline;
  text-underline-offset: 4px;
}

.auth-local-form .form-toggle:hover:not(:disabled) {
  border-color: transparent;
  background: transparent;
  color: var(--cmp-text);
}

.auth-features {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(24px, 4vw, 64px);
  width: min(100%, 820px);
  color: var(--cmp-text);
  text-align: center;
}

.auth-feature {
  display: grid;
  justify-items: center;
  align-content: start;
}

.auth-feature svg {
  width: 34px;
  height: 34px;
  margin-bottom: 12px;
  color: var(--cmp-text-secondary);
}

.auth-feature h2 {
  margin: 0 0 7px;
  font-family: var(--cmp-font-display);
  font-size: 1.18rem;
  font-weight: 650;
  line-height: 1.25;
}

.auth-feature p {
  max-width: 190px;
  margin: 0;
  color: var(--cmp-text-muted);
  font-size: .98rem;
  line-height: 1.45;
}

@media (max-width: 700px) {
  .auth-features {
    grid-template-columns: 1fr;
    gap: 28px;
  }
}

@media (max-width: 480px) {
  .auth-container {
    padding: 30px 24px;
  }

  .auth-brand {
    margin-bottom: 34px;
  }

  .auth-legal-copy {
    font-size: .9rem;
  }
}
</style>
