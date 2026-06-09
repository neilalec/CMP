<script setup>
import { useRouter } from 'vue-router';
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
    </div>
    <div class="auth-body">
      <h2>{{ formType === 'login' ? 'Login' : 'Register' }}</h2>
      <button class="steam-button" type="button" @click="handleSteamSignIn">
        Steam
      </button>
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
  width: min(100%, 360px);
  margin: 0 auto;
  overflow: hidden;
}

.auth-body {
  padding: 1rem 1.1rem 1.1rem;
}

.auth-container h2 {
  margin: 0 0 1rem;
  font-weight: 800;
  font-size: 1.25rem;
}

.steam-button {
  width: 100%;
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
