<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { API_BASE_URL } from '../config';
import { useProfileView } from '../features/profile/composables/useProfileView';

const { authStore, displayName, handleLogout, hasSteamId, steamId } = useProfileView();
const saving = ref(false);
const saveStatus = ref('');
const saveError = ref('');
const ratingLoading = ref(true);
const ratingError = ref('');
const latestRatedMatch = ref(null);

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
  <main class="profile-page cmp-page cmp-page-content">
    <header class="cmp-page-header"><p class="cmp-kicker">Player identity</p><h1>Profile</h1></header>

    <section class="profile-identity cmp-surface" aria-label="Competitive identity">
      <div class="profile-name"><p class="cmp-kicker">Display name</p><h2>{{ authStore.playerName || 'Player' }}</h2><p>{{ hasSteamId ? 'Steam linked' : 'Steam not linked' }}<span v-if="authStore.isAdmin"> · Admin</span></p></div>
      <div class="profile-rating"><p class="cmp-kicker">WARDOGS rating</p><p v-if="ratingLoading" role="status">Checking recent rating…</p><p v-else-if="ratingError" role="alert">{{ ratingError }}</p><template v-else-if="latestRatedMatch"><strong>{{ latestRatedMatch.rating.after }}</strong><span>After your latest rated match</span></template><p v-else>No recent rating entry.</p></div>
    </section>

    <section class="profile-edit" aria-labelledby="display-name-title">
      <div class="cmp-section-header"><h2 id="display-name-title">Display name</h2><p>How other players see you</p></div>
      <form class="display-name-control" @submit.prevent="saveDisplayName">
        <label for="profile-display-name" class="sr-only">Display name</label>
        <input id="profile-display-name" v-model="displayName" class="cmp-input" type="text" maxlength="32" autocomplete="nickname" :disabled="saving" @input="saveStatus = ''; saveError = ''">
        <button class="cmp-button cmp-button--primary" type="submit" :disabled="saving" :aria-busy="saving">{{ saving ? 'Saving…' : 'Save name' }}</button>
      </form>
      <p v-if="saveStatus" class="profile-feedback is-success" role="status">{{ saveStatus }}</p>
      <p v-if="saveError" class="profile-feedback is-error" role="alert">{{ saveError }}</p>
    </section>

    <section class="profile-group cmp-disclosure" aria-label="Group access"><div><h2>Group</h2><p>Manage your premade for matchmaking.</p></div><RouterLink class="cmp-button cmp-button--secondary" to="/group">Open group</RouterLink></section>
    <details class="profile-account cmp-disclosure"><summary>Account details</summary><p>Steam ID: <span>{{ hasSteamId ? steamId : 'Not linked' }}</span></p></details>
    <button class="profile-logout cmp-button cmp-button--secondary" type="button" @click="handleLogout">Log out</button>
  </main>
</template>

<style scoped>
.profile-page { display: grid; gap: var(--cmp-section-gap); max-width: 880px; }
.profile-page .cmp-page-header { margin: 0; }
.profile-identity { display: grid; grid-template-columns: minmax(0, 1fr) minmax(190px, .6fr); gap: var(--cmp-space-5); padding: var(--cmp-space-5); border-top: 3px solid var(--cmp-primary); }
.profile-name, .profile-rating { display: grid; align-content: start; gap: var(--cmp-space-2); min-width: 0; }
.profile-name h2 { margin: 0; font-size: 1.5rem; line-height: 1.2; overflow-wrap: anywhere; }
.profile-name > p:last-child, .profile-rating > p:not(.cmp-kicker) { margin: 0; color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); }
.profile-rating { padding-left: var(--cmp-space-5); border-left: 1px solid var(--cmp-border); }
.profile-rating strong { font: 700 1.5rem var(--cmp-font-mono); }
.profile-rating span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.profile-edit { display: grid; gap: var(--cmp-space-3); }
.profile-edit .cmp-section-header { margin: 0; }
.display-name-control { display: flex; gap: var(--cmp-space-2); max-width: 620px; }
.display-name-control input { flex: 1; min-width: 0; }
.profile-feedback { margin: 0; font-size: var(--cmp-type-meta); }
.profile-feedback.is-success { color: var(--cmp-success); }
.profile-feedback.is-error { color: var(--cmp-danger); }
.profile-group { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-4); padding-top: var(--cmp-space-4); }
.profile-group h2 { margin: 0 0 var(--cmp-space-1); font-size: var(--cmp-type-section); }
.profile-group p { margin: 0; color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); }
.profile-account { font-size: var(--cmp-type-meta); }
.profile-account p { margin: 0 0 var(--cmp-space-3); color: var(--cmp-text-muted); }
.profile-account span { color: var(--cmp-text); overflow-wrap: anywhere; }
.profile-logout { justify-self: start; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 640px) { .profile-identity { grid-template-columns: 1fr; }.profile-rating { padding: var(--cmp-space-4) 0 0; border-left: 0; border-top: 1px solid var(--cmp-border); }.profile-group { align-items: flex-start; flex-direction: column; }.display-name-control { flex-direction: column; }.display-name-control button { width: 100%; } }
</style>
