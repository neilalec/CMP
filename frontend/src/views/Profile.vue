<script setup>
import { useProfileView } from '../features/profile/composables/useProfileView';

const {
  authStore,
  displayName,
  handleDisplayNameSave,
  handleLogout,
  hasSteamId,
  steamId
} = useProfileView();
</script>

<template>
  <div class="profile-page content-panel">
    <div class="page-shell narrow">
      <p class="profile-name current-user">
        <span class="profile-name-text">{{ authStore.playerName }}</span>
      </p>
      <p v-if="authStore.isAdmin" class="admin-badge">Admin</p>

      <div class="profile-card window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Elo Rating</span>
          <span class="window-titlebar-meta">{{ authStore.eloMatches }} rated</span>
        </div>
        <div class="profile-card-body panel-body">
          <div class="profile-value-row rating-row">
            <span class="field-label">Current Rating</span>
            <strong class="elo-value">{{ authStore.eloRating }}</strong>
          </div>
        </div>
      </div>

      <div class="profile-card window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Steam Account</span>
          <span class="window-titlebar-meta" v-if="hasSteamId">Ready</span>
        </div>
        <div class="profile-card-body panel-body">
          <div class="profile-value-row">
            <span class="field-label">Steam ID64</span>
            <strong>{{ steamId || 'Not linked' }}</strong>
          </div>
        </div>
      </div>

      <div class="profile-card window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Display Name</span>
          <span class="window-titlebar-meta">{{ authStore.displayNameSource === 'steam' ? 'Steam' : 'Custom' }}</span>
        </div>
        <div class="profile-card-body panel-body">
          <div class="display-name-control">
            <input
              v-model="displayName"
              type="text"
              maxlength="32"
              autocomplete="nickname"
            />
            <button type="button" @click="handleDisplayNameSave">
              Save
            </button>
          </div>
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
  font-weight: 600;
  color: var(--text-muted);
}

.profile-name {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  max-width: 100%;
  padding: 5px 10px;
  border: 1px solid var(--title-plate-border);
  border-radius: var(--radius-md);
  background: var(--title-plate-bg);
  box-shadow: var(--title-plate-shadow);
  font-weight: 700;
  color: inherit;
  margin: 0 0 0.75rem;
}

.profile-name-text {
  min-width: 0;
  color: var(--text-main);
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 800;
  line-height: 1;
  overflow-wrap: anywhere;
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

.profile-value-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.display-name-control {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 8px;
}

.display-name-control input {
  min-width: 0;
}

.profile-value-row strong {
  font-size: 1rem;
  overflow-wrap: anywhere;
  text-align: right;
}

.rating-row {
  align-items: baseline;
}

.elo-value {
  color: var(--accent-strong);
  font-family: var(--font-display);
  font-size: 1.65rem !important;
  font-weight: 900;
  line-height: 1;
}

.profile-actions {
  margin-top: 1rem;
  display: flex;
  justify-content: center;
}

.profile-actions button {
  width: 200px;
}

@media (max-width: 480px) {
  .profile-name {
    align-items: stretch;
    flex-direction: column;
    gap: 6px;
    width: min(100%, 320px);
  }

  .profile-value-row {
    align-items: stretch;
    flex-direction: column;
  }

  .display-name-control {
    grid-template-columns: 1fr;
  }

  .profile-actions button {
    width: 100%;
  }
}
</style>
