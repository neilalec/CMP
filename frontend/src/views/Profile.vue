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
    <div class="page-shell narrow">
      <p class="profile-name current-user">{{ authStore.username }}</p>
      <p v-if="authStore.isAdmin" class="admin-badge">Admin</p>

      <div class="profile-card window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Steam ID</span>
          <span class="window-titlebar-meta" v-if="hasSteamId">Ready</span>
        </div>
        <div class="profile-card-body panel-body">
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
          <button
            class="save-button"
            @click="saveSteamId"
            :disabled="isSteamIdLocked || socketStore.loading || !steamId || steamId === authStore.steamId"
          >
            {{ savingSteamId ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>

      <div class="profile-actions">
        <button @click="handleLogout">Logout</button>
      </div>

    </div>
  </div>
</template>

<style scoped>
.profile-page {
  text-align: center;
}

.profile-card {
  width: min(100%, 420px);
  margin: 1.5rem auto 0;
  text-align: left;
  overflow: hidden;
}

.field-label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 600;
}

.steam-input {
  width: 100%;
}

.steam-input.is-locked {
  opacity: 0.7;
  cursor: not-allowed;
}

.profile-name {
  font-weight: 700;
  font-size: 1.5rem;
  color: inherit;
  margin: 0 0 0.75rem;
}

.admin-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 28px;
  padding: 0.25rem 0.65rem;
  border-radius: var(--radius-sm);
  background: var(--accent-soft);
  border: 1px solid var(--accent-border);
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: 0.78rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.save-button {
  margin: 1rem 0 0;
}

.profile-actions {
  margin-top: 1.5rem;
}

.profile-actions button {
  width: 200px;
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
