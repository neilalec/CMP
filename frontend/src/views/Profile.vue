<script setup>
import { RouterLink } from 'vue-router';
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
  <div class="profile-page content-panel page-shell narrow">
    <header class="profile-heading">
      <p class="eyebrow">Account</p>
      <h1>Profile</h1>
      <p>{{ authStore.playerName }}</p>
      <span v-if="authStore.isAdmin" class="admin-badge">Admin</span>
    </header>

    <section class="profile-section" aria-labelledby="display-name-title">
      <h2 id="display-name-title">Display name</h2>
      <div class="display-name-control">
        <input v-model="displayName" type="text" maxlength="32" autocomplete="nickname" aria-label="Display name" />
        <button type="button" @click="handleDisplayNameSave">Save</button>
      </div>
    </section>

    <section class="profile-section" aria-label="Group">
      <div class="profile-row">
        <div>
          <h2>Group</h2>
          <p>Queue with your group.</p>
        </div>
        <RouterLink to="/group">Open group</RouterLink>
      </div>
    </section>

    <details class="account-details">
      <summary>Account details</summary>
      <p>Steam ID: {{ hasSteamId ? steamId : 'Not linked' }}</p>
    </details>

    <button class="logout-button" type="button" @click="handleLogout">Log out</button>
  </div>
</template>

<style scoped>
.profile-page { display: grid; gap: 18px; padding-top: clamp(28px, 5vw, 60px); }
.profile-heading { display: grid; justify-items: start; gap: 8px; margin-bottom: 8px; }
.profile-heading h1 { margin: 0; font-size: clamp(2rem, 4vw, 3rem); letter-spacing: -.03em; }
.profile-heading p { margin: 0; color: var(--text-secondary); }
.admin-badge { padding: 4px 8px; border: 1px solid var(--border); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: .7rem; font-weight: 700; text-transform: uppercase; }
.profile-section { padding: 22px; border: 1px solid var(--border-muted); border-radius: var(--radius-lg); background: var(--surface); }
.profile-section h2 { margin: 0 0 14px; font-size: 1rem; }
.profile-section p { margin: 0; color: var(--text-secondary); font-size: .84rem; }
.display-name-control { display: flex; align-items: center; gap: 8px; }
.display-name-control input { flex: 1; min-width: 0; }
.display-name-control button { width: auto; min-height: 38px; }
.profile-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.profile-row h2 { margin-bottom: 6px; }
.profile-row a { white-space: nowrap; font-size: .84rem; font-weight: 700; }
.account-details { color: var(--text-secondary); font-size: .82rem; }
.account-details summary { width: max-content; cursor: pointer; }
.account-details p { overflow-wrap: anywhere; }
.logout-button { width: max-content; margin-top: 10px; color: var(--text-secondary); }
@media (max-width: 520px) {
  .display-name-control { align-items: stretch; flex-direction: column; }
  .display-name-control input, .display-name-control button { width: 100%; }
}
</style>
