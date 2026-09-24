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
  <div class="auth-container window-panel">
    <div class="window-titlebar">
      <span class="window-titlebar-label">{{ formType === 'login' ? 'Login' : 'Register' }}</span>
      <span class="window-titlebar-meta">Access</span>
    </div>
    <div class="auth-body">
      <button class="steam-button" type="button" @click="handleSteamSignIn">
        Continue with Steam
      </button>
      <p class="auth-copy steam-security-copy">
        You will be redirected to Steam's official sign-in page. We never see or store your Steam password.
      </p>
      <p class="auth-copy steam-security-copy">
        Steam only confirms your SteamID to us, which lets Squad Comp Matchmaking match your account to your player slot when you join a server.
      </p>
      <p class="auth-legal-copy">
        By continuing, you agree to the <RouterLink to="/terms">Terms</RouterLink> and acknowledge the <RouterLink to="/privacy">Privacy Policy</RouterLink>.
      </p>
      <div v-if="PASSWORD_AUTH_ENABLED" class="auth-divider">
        <span>or</span>
      </div>
      <form v-if="PASSWORD_AUTH_ENABLED" @submit.prevent="handleSubmit">
        <input
          v-model="username"
          type="text"
          placeholder="Username"
          required
        />
        <input
          v-model="password"
          type="password"
          placeholder="Password"
          required
        />
        <button type="submit" :disabled="loading">
          {{ loading ? 'Working...' : (formType === 'login' ? 'Login' : 'Register') }}
        </button>
      </form>

      <div v-if="PASSWORD_AUTH_ENABLED" class="toggle-form">
        <a href="#" @click.prevent="toggleForm">
          {{ formType === 'login' ? 'Create account' : 'Back to login' }}
        </a>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-container {
  width: min(100%, 420px);
  margin: 0 auto;
  overflow: hidden;
}

.auth-body {
  padding: 1rem 1.1rem 1.2rem;
}

.auth-container h2 {
  margin: 0 0 0.45rem;
  font-weight: 800;
  font-size: 1.28rem;
  line-height: 1.2;
}

.auth-copy {
  margin: 0 0 1rem;
  color: var(--text-muted);
}

.steam-button {
  width: 100%;
}

.steam-security-copy {
  margin: 0.7rem 0 0;
  line-height: 1.45;
}

.auth-legal-copy {
  margin: 0.9rem 0 0;
  color: var(--text-soft);
  font-size: 0.78rem;
  line-height: 1.45;
  text-align: center;
}

.auth-legal-copy a {
  color: var(--accent-strong);
  font-weight: 800;
}

.auth-divider {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 1rem 0;
  color: var(--text-muted);
  font-size: 0.82rem;
}

.auth-divider::before,
.auth-divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: var(--surface-border);
}

form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

input,
button {
  width: 100%;
}

.toggle-form {
  margin-top: 1rem;
  text-align: center;
  color: var(--text-muted);
}
</style>
