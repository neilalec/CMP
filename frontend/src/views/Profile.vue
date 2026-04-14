<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../stores/authStore';
import { useQueueStore } from '../stores/queueStore';
import { useLobbyStore } from '../stores/lobbyStore';
import { useSocketStore } from '../stores/socketStore';
import { useRootStore } from '../stores/rootStore';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const queueStore = useQueueStore();
const lobbyStore = useLobbyStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();
const router = useRouter();
const steamId = ref('');
const loading = ref(false);
const savingSteamId = ref(false);

const isSteamIdLocked = computed(() => {
  return (
    loading.value ||
    savingSteamId.value ||
    queueStore.inQueue ||
    !!lobbyStore.lobbyId ||
    authStore.steamIdLocked
  );
});
const hasSteamId = computed(() => !!authStore.steamId);

const loadProfile = async () => {
  loading.value = true;
  try {
    const profile = await authStore.syncProfile();
    steamId.value = profile?.steam_id || '';
  } catch (error) {
    rootStore.setError(error.message || 'Failed to load profile');
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  steamId.value = authStore.steamId || '';
  try {
    await queueStore.syncWithServer(authStore.username);
  } catch (error) {
    // ignore queue sync failures here
  }
  await loadProfile();
});

const saveSteamId = async () => {
  savingSteamId.value = true;
  rootStore.clearError();
  try {
    const profile = await authStore.updateSteamId(steamId.value);
    steamId.value = profile?.steam_id || '';
  } catch (error) {
    rootStore.setError(error.message || 'Failed to save Steam ID');
  } finally {
    savingSteamId.value = false;
  }
};

const handleLogout = async () => {
  try {
    await socketStore.cleanupSocket();
    authStore.logout();
    localStorage.removeItem('currentLobby');
    await socketStore.initSocket();
    router.push('/auth');
  } catch (error) {
    rootStore.setError('Logout failed');
  }
};
</script>

<template>
  <div class="profile-page content-panel">
    <h1>Profile</h1>
    <p class="profile-name current-user">{{ authStore.username }}</p>
    <div class="profile-card">
      <label class="field-label" for="steam-id">Steam ID64</label>
      <input
        id="steam-id"
        v-model="steamId"
        :class="['steam-input', { 'is-locked': isSteamIdLocked }]"
        type="text"
        inputmode="numeric"
        placeholder="7656119..."
        maxlength="17"
        :disabled="isSteamIdLocked || socketStore.loading || !authStore.username"
        :readonly="isSteamIdLocked || socketStore.loading || !authStore.username"
      />
      <p class="profile-note">
        {{ hasSteamId ? 'Used to verify you on the Squad server.' : 'Required before you can join the queue.' }}
      </p>
      <p class="profile-note lock-note">
        Leave the queue or lobby before changing your Steam ID.
      </p>
      <button
        class="save-button"
        @click="saveSteamId"
        :disabled="isSteamIdLocked || socketStore.loading || !steamId || steamId === authStore.steamId"
      >
        {{ savingSteamId ? 'Saving...' : 'Save Steam ID' }}
      </button>
    </div>
    <div class="profile-actions">
      <button @click="handleLogout">Logout</button>
    </div>
  </div>
</template>

<style scoped>
h1 {
  color: inherit;
  font-weight: 500;
}
.profile-page {
  width: min(100%, 760px);
  max-width: 760px;
  margin: 56px auto 0;
  text-align: center;
}

.profile-card {
  width: min(100%, 420px);
  margin: 1.5rem auto 0;
  padding: 1.25rem;
  background: var(--surface);
  border: 1px solid var(--surface-border);
  border-radius: 14px;
  box-shadow: var(--surface-shadow);
  text-align: left;
}

.field-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.steam-input {
  width: 100%;
  padding: 0.8rem 0.9rem;
  border-radius: 8px;
  border: 1px solid var(--surface-border);
  background: rgba(255, 255, 255, 0.04);
  color: inherit;
}

.steam-input.is-locked {
  opacity: 0.7;
  cursor: not-allowed;
}

.profile-name {
  font-weight: 700;
  font-size: 1.3rem;
  color: inherit;
  margin: 0.5rem 0 0.75rem;
}

.profile-note {
  color: inherit;
  margin: 0.85rem 0 0;
}

.lock-note {
  opacity: 0.75;
}

.save-button {
  margin: 1rem 0 0;
}

.profile-actions {
  margin-top: 1.5rem;
}

button {
  display: block;
  width: 200px;
  margin: 1rem auto;
  padding: 0.8rem;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

button:hover {
  background: #4a4f56;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
