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
  <main class="auth-container" aria-labelledby="auth-title">
    <header class="auth-brand" aria-label="CMP">
      <span class="auth-mark">CMP</span>
      <span class="auth-descriptor">WARDOGS matchmaking</span>
    </header>

    <section class="auth-content">
      <h1 id="auth-title">Sign in</h1>
      <button
        class="steam-button"
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
            type="text"
            autocomplete="username"
            required
          />
          <label for="auth-password">Password</label>
          <input
            id="auth-password"
            v-model="password"
            type="password"
            :autocomplete="formType === 'login' ? 'current-password' : 'new-password'"
            required
          />
          <button class="local-submit" type="submit" :disabled="loading">
            {{ loading ? 'Working...' : (formType === 'login' ? 'Login' : 'Register') }}
          </button>
          <button class="form-toggle" type="button" @click="toggleForm">
            {{ formType === 'login' ? 'Create account' : 'Back to login' }}
          </button>
        </form>
      </details>
    </section>
  </main>
</template>

<style scoped>
:global(.auth-shell) {
  position: relative;
  isolation: isolate;
  background:
    radial-gradient(ellipse at 50% 40%, rgba(27, 57, 83, .38), transparent 55%),
    radial-gradient(ellipse at 50% 110%, rgba(18, 39, 59, .55), transparent 58%),
    linear-gradient(180deg, #080f1b 0%, #0a1421 52%, #070d16 100%);
}

:global(.auth-shell::before) {
  position: absolute;
  z-index: -1;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 38%, rgba(2, 7, 14, .42) 100%);
  content: '';
  pointer-events: none;
}

.auth-container {
  position: relative;
  z-index: 1;
  width: min(100%, 420px);
  margin: 0 auto;
  text-align: center;
}

.auth-brand {
  display: grid;
  justify-items: center;
  gap: 10px;
  margin-bottom: clamp(38px, 7vh, 64px);
}

.auth-mark {
  color: var(--text-primary);
  font: 850 clamp(3rem, 7vw, 4rem)/.95 var(--font-display);
  letter-spacing: .2em;
  padding-left: .2em;
  text-shadow: 0 8px 32px rgba(0, 0, 0, .35);
}

.auth-descriptor {
  color: var(--text-muted);
  font-size: .78rem;
  font-weight: 650;
  letter-spacing: .16em;
  text-transform: uppercase;
}

.auth-content h1 {
  margin: 0 0 28px;
  color: var(--text-primary);
  font-family: var(--font-display);
  font-size: clamp(1.7rem, 4vw, 2rem);
  font-weight: 650;
  letter-spacing: -.025em;
}

.steam-button {
  width: 100%;
  min-height: 56px;
  border: 1px solid rgba(132, 216, 255, .62);
  border-radius: var(--radius-md);
  background: linear-gradient(180deg, #45c4fb 0%, #1ca7e8 100%);
  box-shadow: 0 10px 30px rgba(13, 135, 196, .2), inset 0 1px 0 rgba(255, 255, 255, .2);
  color: #061624;
  font-size: 1rem;
  font-weight: 750;
  letter-spacing: .005em;
  transition: background .16s ease, box-shadow .16s ease, transform .16s ease;
}

.steam-button:hover:not(:disabled) {
  border-color: #b4eaff;
  background: linear-gradient(180deg, #72d4ff 0%, #36b7f2 100%);
  box-shadow: 0 12px 36px rgba(13, 135, 196, .3), inset 0 1px 0 rgba(255, 255, 255, .25);
  transform: translateY(-1px);
}

.steam-button:focus-visible,
.form-toggle:focus-visible,
.auth-local-access summary:focus-visible,
.auth-legal-copy a:focus-visible {
  outline: 3px solid #d7f3ff;
  outline-offset: 4px;
}

.auth-security-copy {
  margin: 18px 0 0;
  color: var(--text-secondary);
  font-size: .9rem;
}

.auth-legal-copy {
  max-width: 380px;
  margin: 30px auto 0;
  color: var(--text-muted);
  font-size: .82rem;
  line-height: 1.6;
}

.auth-legal-copy a {
  color: var(--text-secondary);
  text-decoration: underline;
  text-decoration-color: rgba(185, 200, 217, .45);
  text-underline-offset: 3px;
}

.auth-legal-copy a:hover {
  color: var(--text-primary);
}

.auth-local-access {
  width: max-content;
  max-width: 100%;
  margin: 38px auto 0;
  color: var(--text-secondary);
  font-size: .88rem;
  text-align: left;
}

.auth-local-access summary {
  width: fit-content;
  margin: 0 auto;
  color: var(--text-secondary);
  cursor: pointer;
  text-underline-offset: 4px;
}

.auth-local-access summary:hover {
  color: var(--text-primary);
}

.auth-local-form {
  display: grid;
  gap: 9px;
  width: min(100%, 360px);
  margin: 20px auto 0;
  color: var(--text-secondary);
  font-size: .82rem;
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
  color: var(--text-secondary);
  text-decoration: underline;
  text-underline-offset: 4px;
}

.auth-local-form .form-toggle:hover:not(:disabled) {
  border-color: transparent;
  background: transparent;
  color: var(--text-primary);
}

@media (max-width: 480px) {
  .auth-brand {
    margin-bottom: 34px;
  }

  .auth-content h1 {
    margin-bottom: 24px;
  }

  .auth-legal-copy {
    margin-top: 26px;
    font-size: .8rem;
  }
}
</style>
