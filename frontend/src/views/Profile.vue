<script setup>
import { useProfileView } from '../features/profile/composables/useProfileView';

const {
  authStore,
  handleLogout,
  hasSteamId,
  isSteamIdLocked,
  saveSteamId,
  savingSteamId,
  socketStore,
  steamId
} = useProfileView();
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
  margin: clamp(20px, 5vw, 56px) auto 0;
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

@media (max-width: 480px) {
  .profile-card {
    padding: 1rem;
  }

  .save-button,
  .profile-actions button {
    width: 100%;
  }
}
</style>
