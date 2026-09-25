<script setup>
import { onMounted, ref } from 'vue';
import { API_BASE_URL } from '../config';
import { useProfileView } from '../features/profile/composables/useProfileView';

const { authStore, displayName, handleLogout, hasSteamId, steamId } = useProfileView();
const saving = ref(false);
const editing = ref(false);
const saveStatus = ref('');
const saveError = ref('');
const ratingLoading = ref(true);
const ratingError = ref('');
const latestRatedMatch = ref(null);

const startEditing = () => {
  displayName.value = authStore.playerName || '';
  saveStatus.value = '';
  saveError.value = '';
  editing.value = true;
};
const cancelEditing = () => {
  displayName.value = authStore.playerName || '';
  saveStatus.value = '';
  saveError.value = '';
  editing.value = false;
};

const saveDisplayName = async () => {
  saveStatus.value = '';
  saveError.value = '';
  if (!displayName.value.trim()) {
    saveError.value = 'Enter a display name.';
    return;
  }
  saving.value = true;
  try {
    const profile = await authStore.updateDisplayName(displayName.value);
    displayName.value = profile?.display_name || authStore.playerName || '';
    saveStatus.value = 'Display name saved.';
    editing.value = false;
  } catch (error) {
    saveError.value = error.message || 'Could not save the display name.';
  } finally {
    saving.value = false;
  }
};

onMounted(async () => {
  if (!authStore.token) {
    ratingLoading.value = false;
    return;
  }
  try {
    const response = await fetch(`${API_BASE_URL}/wardogs/matches/history?limit=30`, {
      headers: { Authorization: `Bearer ${authStore.token}` }
    });
    const payload = await response.json();
    if (!response.ok || !payload?.success || !Array.isArray(payload.matches)) throw new Error('Rating history unavailable.');
    latestRatedMatch.value = payload.matches.find((match) => Number.isFinite(match.rating?.after)) || null;
  } catch {
    ratingError.value = 'WARDOGS rating history is unavailable.';
  } finally {
    ratingLoading.value = false;
  }
});
</script>

<template>
  <div class="profile-page cmp-page cmp-page-content">
    <header class="cmp-page-header"><p class="cmp-kicker">Player identity</p><h1>Profile</h1></header>

    <section class="profile-identity" aria-label="Competitive identity">
      <div class="profile-name"><p class="cmp-kicker">Display name</p><div class="profile-name-line"><h2>{{ authStore.playerName || 'Player' }}</h2><button class="profile-edit-trigger cmp-button cmp-button--secondary" type="button" @click="startEditing">Edit</button></div><p>{{ hasSteamId ? 'Steam linked' : 'Steam not linked' }}<span v-if="authStore.isAdmin"> · Admin</span></p></div>
      <div class="profile-rating"><p class="cmp-kicker">After latest rated match</p><p v-if="ratingLoading" class="cmp-status" role="status">Loading…</p><p v-else-if="ratingError" class="profile-rating-unavailable" role="status">Unavailable</p><template v-else-if="latestRatedMatch"><strong>{{ latestRatedMatch.rating.after }}</strong></template><p v-else class="profile-rating-unavailable">—</p></div>
    </section>

    <section v-if="editing" class="profile-edit" aria-label="Edit display name">
      <form class="display-name-control" @submit.prevent="saveDisplayName">
        <label for="profile-display-name" class="sr-only">Display name</label>
        <input id="profile-display-name" v-model="displayName" class="cmp-input" type="text" maxlength="32" autocomplete="nickname" :disabled="saving" @input="saveStatus = ''; saveError = ''">
        <button class="cmp-button cmp-button--primary" type="submit" :disabled="saving" :aria-busy="saving">{{ saving ? 'Saving…' : 'Save name' }}</button>
        <button class="cmp-button cmp-button--secondary" type="button" :disabled="saving" @click="cancelEditing">Cancel</button>
      </form>
    </section>
    <p v-if="saveStatus" class="profile-feedback cmp-status cmp-status--success" role="status">{{ saveStatus }}</p>
    <p v-if="saveError" class="profile-feedback cmp-status cmp-status--danger" role="alert">{{ saveError }}</p>

    <details class="profile-account cmp-disclosure"><summary>Account details</summary><p>Steam ID: <span>{{ hasSteamId ? steamId : 'Not linked' }}</span></p></details>
    <button class="profile-logout cmp-button cmp-button--secondary" type="button" @click="handleLogout">Log out</button>
  </div>
</template>

<style scoped>
.profile-page { display: grid; gap: var(--cmp-section-gap); max-width: 720px; }
.profile-page .cmp-page-header { margin: 0; }
.profile-identity { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--cmp-space-5); padding: var(--cmp-space-3) 0; border-bottom: 1px solid var(--cmp-border); }
.profile-name, .profile-rating { display: grid; align-content: start; gap: var(--cmp-space-2); min-width: 0; }
.profile-name h2 { margin: 0; font-size: 1.5rem; line-height: 1.2; overflow-wrap: anywhere; }
.profile-name-line { display: flex; align-items: center; flex-wrap: wrap; gap: var(--cmp-space-3); }
.profile-name > p:last-child, .profile-rating > p:not(.cmp-kicker) { margin: 0; font-size: var(--cmp-type-meta); }
.profile-name > p:last-child, .profile-rating > p:not(.cmp-kicker):not(.cmp-status) { color: var(--cmp-text-secondary); }
.profile-rating { align-content: center; padding-left: var(--cmp-space-5); border-left: 1px solid var(--cmp-border); text-align: right; }
.profile-rating strong { font: 700 1.125rem var(--cmp-font-mono); }
.profile-rating-unavailable { color: var(--cmp-text-muted); }
.profile-edit { display: grid; gap: var(--cmp-space-3); }
.display-name-control { display: flex; gap: var(--cmp-space-2); max-width: 620px; }
.display-name-control input { flex: 1; min-width: 0; }
.display-name-control button { flex: none; }
.profile-feedback { margin: 0; font-size: var(--cmp-type-meta); }
.profile-account { font-size: var(--cmp-type-meta); }
.profile-account p { margin: 0 0 var(--cmp-space-3); color: var(--cmp-text-muted); }
.profile-account span { color: var(--cmp-text); overflow-wrap: anywhere; }
.profile-logout { justify-self: start; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 640px) { .profile-identity { grid-template-columns: minmax(0, 1fr) auto; }.profile-rating { padding-left: var(--cmp-space-3); }.display-name-control { flex-wrap: wrap; }.display-name-control input { flex-basis: 100%; }.display-name-control button { flex: 1; } }
</style>
