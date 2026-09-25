<script setup>
import { onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { API_BASE_URL } from '../config';
import { useAuthStore } from '../stores/authStore';

const authStore = useAuthStore();
const current = ref(null);
const history = ref([]);
const currentLoading = ref(false);
const historyLoading = ref(false);
const currentError = ref('');
const historyError = ref('');

const names = { valkyra: 'Valkyra', lonestar: 'Lonestar', manticore: 'Manticore' };
const factionName = (id) => names[id] || id || 'Faction unavailable';
const outcomeName = (outcome) => ({ win: 'Win', loss: 'Loss', tie: 'Tie', incomplete: 'Incomplete', void: 'Void' })[outcome]
  || 'Placement unavailable';
const placementName = (index) => ({ 1: '1st', 2: '2nd', 3: '3rd' })[index] || `${index}th`;
const placementContext = (groups) => Array.isArray(groups)
  ? groups.map((group, index) => {
    const rank = groups.slice(0, index).reduce((total, previous) => total + previous.length, 1);
    return `${placementName(rank)} ${group.map(factionName).join(' / ')}`;
  }).join(' · ') : '';
const matchDate = (value) => {
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date.toLocaleString() : 'Date unavailable';
};
const ratingText = (rating) => rating
  ? `${rating.delta > 0 ? '+' : ''}${rating.delta} → ${rating.after}` : 'No rating entry';
const ratingTone = (rating) => rating?.delta > 0 ? 'is-positive' : rating?.delta < 0 ? 'is-negative' : '';
const resultTone = (outcome) => ({ win: 'is-win', loss: 'is-loss', tie: 'is-tie', incomplete: 'is-unrated', void: 'is-unrated' })[outcome] || 'is-unrated';

const read = async (path) => {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { Authorization: `Bearer ${authStore.token}` }
  });
  const payload = await response.json();
  if (!response.ok || !payload?.success) throw new Error(payload?.message || 'Matches are unavailable');
  return payload;
};
const loadCurrent = async () => {
  if (!authStore.token) return;
  currentLoading.value = true;
  currentError.value = '';
  try {
    current.value = (await read('/wardogs/matches/current')).match || null;
  } catch (error) {
    currentError.value = error.message || 'Could not load your current match';
  } finally {
    currentLoading.value = false;
  }
};
const loadHistory = async () => {
  if (!authStore.token) return;
  historyLoading.value = true;
  historyError.value = '';
  try {
    history.value = (await read('/wardogs/matches/history?limit=30')).matches || [];
  } catch (error) {
    historyError.value = error.message || 'Could not load match history';
  } finally {
    historyLoading.value = false;
  }
};
onMounted(() => { loadCurrent(); loadHistory(); });
</script>

<template>
  <main class="matches-page cmp-page cmp-page-content">
    <header class="cmp-page-header matches-heading"><p class="cmp-kicker">Competitive record</p><h1>Matches</h1><p>Your current match and referee-confirmed history.</p></header>

    <section class="matches-section" aria-label="Current match">
      <div class="cmp-section-header"><h2>Current match</h2></div>
      <p v-if="currentLoading && !current" class="cmp-loading-state" role="status">Checking your current match…</p>
      <div v-if="current" class="matches-current cmp-surface" :class="`cmp-faction--${current.factionId}`">
        <div><p class="cmp-kicker">In progress</p><strong>{{ current.state === 'waiting_for_server' ? 'Waiting for server' : 'Server allocated' }}</strong><p class="cmp-faction-marker">{{ factionName(current.factionId) }} · {{ current.rosterStatus === 'reserve' ? 'Reserve' : 'Active' }}</p></div>
        <RouterLink class="cmp-button cmp-button--primary" :to="`/wardogs/lobby/${current.lobbyId}`">Open match</RouterLink>
      </div>
      <p v-else-if="!currentLoading && !currentError" class="matches-quiet">No current WARDOGS match. <RouterLink to="/play">Go to Play</RouterLink></p>
      <p v-if="currentError" class="cmp-error-state" role="alert">{{ currentError }} <button class="matches-retry cmp-button cmp-button--secondary" type="button" @click="loadCurrent">Retry</button></p>
    </section>

    <section class="matches-section" aria-label="Recent matches">
      <div class="cmp-section-header"><h2>Recent matches</h2><p v-if="history.length">{{ history.length }} shown</p></div>
      <p v-if="historyLoading && !history.length" class="cmp-loading-state" role="status">Loading match history…</p>
      <p v-if="historyError" class="cmp-error-state" role="alert">{{ historyError }} <button class="matches-retry cmp-button cmp-button--secondary" type="button" @click="loadHistory">Retry</button></p>
      <p v-else-if="!historyLoading && !history.length" class="cmp-empty-state">No referee-confirmed WARDOGS matches yet. Results appear here after confirmation.</p>
      <ol v-if="history.length" class="matches-history">
        <li v-for="match in history" :key="match.lobbyId" class="matches-row" :class="[`cmp-faction--${match.factionId}`, resultTone(match.result.outcome)]">
          <div class="matches-row-result"><strong>{{ outcomeName(match.result.outcome) }}</strong><span v-if="match.result.placement">{{ placementName(match.result.placement) }} place</span></div>
          <div class="matches-row-main"><strong class="cmp-faction-marker">{{ factionName(match.factionId) }} <small>· {{ match.rosterStatus === 'reserve' ? 'Reserve' : 'Active' }}</small></strong><time :datetime="match.matchAt">{{ matchDate(match.matchAt) }}</time></div>
          <div class="matches-row-rating"><span>WARDOGS rating</span><strong :class="ratingTone(match.rating)">{{ ratingText(match.rating) }}</strong></div>
          <p v-if="match.result.corrected || match.result.placementGroups" class="matches-row-context"><span v-if="match.result.corrected" class="matches-corrected">Corrected · revision {{ match.result.revisionNumber }}</span><span v-if="match.result.placementGroups">{{ placementContext(match.result.placementGroups) }}</span></p>
        </li>
      </ol>
    </section>
  </main>
</template>

<style scoped>
.matches-page { display: grid; gap: var(--cmp-section-gap); max-width: 1120px; }
.matches-heading { margin-bottom: 0; }
.matches-section { display: grid; gap: var(--cmp-space-3); min-width: 0; }
.matches-section .cmp-section-header { margin-bottom: 0; }
.matches-current { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-4); padding: var(--cmp-space-4) var(--cmp-space-5); border-left: 3px solid var(--cmp-faction-color, var(--cmp-primary)); }
.matches-current > div { display: grid; gap: var(--cmp-space-1); }
.matches-current strong { font-size: 1rem; }
.matches-current p:last-child { margin: 0; color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); }
.matches-quiet { margin: 0; color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.matches-quiet a { color: var(--cmp-primary-hover); }
.matches-retry { margin-left: var(--cmp-space-3); }
.matches-history { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--cmp-border); }
.matches-row { display: grid; grid-template-columns: 150px minmax(0, 1fr) 180px; align-items: center; gap: var(--cmp-space-2) var(--cmp-space-5); min-width: 0; padding: var(--cmp-space-3) var(--cmp-space-2); border-bottom: 1px solid var(--cmp-border); }
.matches-row:hover { background: var(--cmp-bg-elevated); }
.matches-row-result, .matches-row-main, .matches-row-rating { display: grid; gap: var(--cmp-space-1); min-width: 0; }
.matches-row-result strong { color: var(--cmp-text); font-size: 1.125rem; line-height: 1.2; }
.matches-row.is-win .matches-row-result strong { color: var(--cmp-success); }
.matches-row.is-loss .matches-row-result strong { color: var(--cmp-text-secondary); }
.matches-row.is-tie .matches-row-result strong { color: var(--cmp-warning); }
.matches-row-result span, .matches-row-main time, .matches-row-rating span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.matches-row-main strong { font-size: .875rem; font-weight: 650; }
.matches-row-main small { color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); font-weight: 400; }
.matches-row-rating strong { font: 700 .875rem var(--cmp-font-mono); }
.matches-row-rating strong.is-positive { color: var(--cmp-success); }
.matches-row-rating strong.is-negative { color: var(--cmp-warning); }
.matches-row-context { grid-column: 2 / -1; display: flex; flex-wrap: wrap; gap: var(--cmp-space-1) var(--cmp-space-4); margin: 0; color: var(--cmp-text-muted); font-size: .75rem; overflow-wrap: anywhere; }
.matches-corrected { color: var(--cmp-primary-hover); font-weight: 650; }
@media (max-width: 640px) { .matches-current { align-items: flex-start; flex-direction: column; }.matches-row { grid-template-columns: minmax(0, 1fr) auto; gap: var(--cmp-space-2); }.matches-row-result { grid-column: 1; }.matches-row-main { grid-column: 1 / -1; grid-row: 2; }.matches-row-rating { grid-column: 2; grid-row: 1; text-align: right; }.matches-row-context { grid-column: 1 / -1; }.matches-retry { display: flex; margin: var(--cmp-space-2) 0 0; } }
</style>
