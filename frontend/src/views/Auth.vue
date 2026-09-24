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
  overflow: hidden;
  background:
    radial-gradient(ellipse 56% 50% at 29% 23%, rgba(89, 115, 133, .24), transparent 74%),
    radial-gradient(ellipse 44% 42% at 78% 39%, rgba(35, 64, 81, .18), transparent 76%),
    linear-gradient(158deg, #172633 0%, #0b1822 38%, #07121b 72%, #050c12 100%);
}

:global(.auth-shell::before) {
  position: absolute;
  z-index: 0;
  inset: 0;
  background:
    linear-gradient(175deg, transparent 26%, rgba(10, 23, 29, .35) 49%, rgba(2, 8, 12, .78) 100%),
    repeating-linear-gradient(104deg, transparent 0 59px, rgba(164, 186, 193, .015) 60px 61px, transparent 62px 121px),
    radial-gradient(ellipse 69% 32% at 50% 76%, rgba(65, 86, 88, .12), transparent 74%);
  content: '';
  pointer-events: none;
}

:global(.auth-shell::after) {
  position: absolute;
  z-index: 0;
  inset: 0;
  background: radial-gradient(ellipse 72% 76% at 50% 43%, transparent 21%, rgba(2, 7, 11, .55) 100%);
  content: '';
  pointer-events: none;
}

.auth-container {
  position: relative;
  z-index: 1;
  width: min(100%, 480px);
  margin: 0 auto;
  padding: clamp(34px, 4vw, 48px);
  border: 1px solid rgba(165, 186, 196, .16);
  border-radius: 9px;
  background: linear-gradient(155deg, rgba(20, 32, 40, .87), rgba(9, 19, 27, .9));
  box-shadow: 0 28px 80px rgba(0, 0, 0, .43), inset 0 1px 0 rgba(230, 241, 245, .045);
  text-align: center;
}

.auth-brand {
  display: grid;
  justify-items: center;
  gap: 11px;
  margin-bottom: 42px;
}

.auth-mark {
  color: #edf2f4;
  font: 900 clamp(4rem, 6vw, 5rem)/.95 var(--font-display);
  letter-spacing: .085em;
  padding-left: .085em;
}

.auth-descriptor {
  color: #9aadb8;
  font-size: .78rem;
  font-weight: 600;
  letter-spacing: .18em;
  text-transform: uppercase;
}

.auth-content h1 {
  margin: 0 0 24px;
  color: #e6edf1;
  font-family: var(--font-display);
  font-size: 1.95rem;
  font-weight: 600;
  letter-spacing: -.02em;
}

.steam-button {
  width: 100%;
  min-height: 52px;
  border: 1px solid #367bb8;
  border-radius: 5px;
  background: linear-gradient(180deg, #1e75bf 0%, #155d9f 100%);
  box-shadow: 0 6px 18px rgba(0, 0, 0, .22), inset 0 1px 0 rgba(255, 255, 255, .13);
  color: #f4f8fb;
  font-size: 1.15rem;
  font-weight: 700;
  letter-spacing: .01em;
  transition: background .16s ease, box-shadow .16s ease, transform .16s ease;
}

.steam-button:hover:not(:disabled) {
  border-color: #5f9dd0;
  background: linear-gradient(180deg, #2884d1 0%, #1a6bad 100%);
  box-shadow: 0 9px 22px rgba(0, 0, 0, .26), inset 0 1px 0 rgba(255, 255, 255, .16);
  transform: translateY(-1px);
}

.steam-button:focus-visible,
.form-toggle:focus-visible,
.auth-local-access summary:focus-visible,
.auth-legal-copy a:focus-visible {
  outline: 2px solid #aac9e0;
  outline-offset: 4px;
}

.auth-security-copy {
  margin: 18px 0 0;
  color: #afbec8;
  font-size: .98rem;
}

.auth-legal-copy {
  max-width: 380px;
  margin: 24px auto 0;
  color: #91a3ae;
  font-size: .9rem;
  line-height: 1.6;
}

.auth-legal-copy a {
  color: #becdd5;
  text-decoration: underline;
  text-decoration-color: rgba(190, 205, 213, .4);
  text-underline-offset: 3px;
}

.auth-legal-copy a:hover {
  color: var(--text-primary);
}

.auth-local-access {
  width: 100%;
  margin: 28px auto 0;
  color: #a9bbc6;
  font-size: .94rem;
  text-align: left;
}

.auth-local-access summary {
  width: fit-content;
  margin: 0 auto;
  color: #a9bbc6;
  cursor: pointer;
  text-underline-offset: 4px;
}

.auth-local-access summary:hover {
  color: var(--text-primary);
}

.auth-local-form {
  display: grid;
  gap: 9px;
  width: 100%;
  margin: 20px auto 0;
  color: #b9c9d2;
  font-size: .95rem;
}

.auth-local-form input,
.auth-local-form button {
  width: 100%;
  min-height: 44px;
}

.auth-local-form input {
  margin-bottom: 5px;
  border-color: rgba(149, 172, 185, .25);
  background: #0c1a25;
  color: #edf2f4;
}

.auth-local-form .local-submit {
  margin-top: 6px;
  border-color: rgba(149, 172, 185, .3);
  background: #213746;
  color: #dbe5e9;
  box-shadow: none;
}

.auth-local-form .local-submit:hover:not(:disabled) {
  border-color: rgba(169, 191, 203, .45);
  background: #2b4658;
  box-shadow: none;
}

.auth-local-form .form-toggle {
  border-color: transparent;
  background: transparent;
  box-shadow: none;
  color: #a9bbc6;
  text-decoration: underline;
  text-underline-offset: 4px;
}

.auth-local-form .form-toggle:hover:not(:disabled) {
  border-color: transparent;
  background: transparent;
  color: var(--text-primary);
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
