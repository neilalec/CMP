<script setup>
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../stores/authStore';
import { useLobbyStore } from '../stores/lobbyStore';
import { useRootStore } from '../stores/rootStore';
import { setCurrentLobbyId } from '../utils/lobbyPersistence';

const router = useRouter();
const authStore = useAuthStore();
const lobbyStore = useLobbyStore();
const rootStore = useRootStore();
const message = ref('Finishing Steam sign-in...');

const decodePayload = () => {
  const hash = new URLSearchParams(window.location.hash.replace(/^#/, ''));
  const encodedPayload = hash.get('payload');
  if (!encodedPayload) {
    throw new Error('Missing Steam auth payload');
  }

  const padded = encodedPayload.padEnd(encodedPayload.length + ((4 - encodedPayload.length % 4) % 4), '=');
  return JSON.parse(atob(padded.replace(/-/g, '+').replace(/_/g, '/')));
};

onMounted(async () => {
  try {
    const payload = decodePayload();
    if (!payload.success || !payload.access_token || !payload.username) {
      throw new Error(payload.message || 'Steam sign-in failed');
    }

    await authStore.setAuth(payload.access_token, payload.username, payload.profile);

    if (payload.active_lobby) {
      setCurrentLobbyId(payload.active_lobby);
      router.replace(`/lobby/${payload.active_lobby}`);
      return;
    }

    lobbyStore.leaveLobby();
    router.replace('/');
  } catch (error) {
    message.value = 'Steam sign-in failed.';
    rootStore.setError(error.message || 'Steam sign-in failed');
    router.replace('/auth');
  }
});
</script>

<template>
  <div class="steam-callback content-panel">
    <div class="steam-callback-card">
      <h1>Steam Sign-In</h1>
      <p>{{ message }}</p>
    </div>
  </div>
</template>

<style scoped>
.steam-callback {
  width: min(100%, 520px);
  margin: clamp(20px, 5vw, 56px) auto 0;
  text-align: center;
}

.steam-callback-card {
  padding: 1.25rem;
  background: var(--panel-bg);
  border: 1px solid var(--surface-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--surface-shadow);
}

.steam-callback-card p {
  margin-top: 0.75rem;
  color: var(--text-muted);
}
</style>
