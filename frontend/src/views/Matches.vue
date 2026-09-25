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
const matchDate = (value) => {
  const date = new Date(value);
  return value && !Number.isNaN(date.getTime()) ? date.toLocaleString() : 'Date unavailable';
};
const ratingText = (rating) => rating
  ? `${rating.delta > 0 ? '+' : ''}${rating.delta} → ${rating.after}` : '—';
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
  <div class="matches-page cmp-page cmp-page-content">
    <header class="cmp-page-header matches-heading"><h1>Matches</h1></header>

    <section v-if="currentLoading || current || currentError" class="matches-section" aria-label="Current match">
      <div class="cmp-section-header"><h2>Current match</h2></div>
      <p v-if="currentLoading && !current" class="cmp-loading-state" role="status">Checking your current match…</p>
      <div v-if="current" class="matches-current" :class="`cmp-faction--${current.factionId}`">
        <div><p class="cmp-kicker">In progress</p><strong>{{ current.state === 'waiting_for_server' ? 'Waiting for server' : 'Server allocated' }}</strong><p class="cmp-faction-marker">{{ factionName(current.factionId) }} · {{ current.rosterStatus === 'reserve' ? 'Reserve' : 'Active' }}</p></div>
        <RouterLink class="cmp-button cmp-button--primary" :to="`/wardogs/lobby/${current.lobbyId}`">Open match</RouterLink>
      </div>
      <p v-if="currentError" class="cmp-error-state" role="alert">{{ currentError }} <button class="matches-retry cmp-button cmp-button--secondary" type="button" @click="loadCurrent">Retry</button></p>
    </section>

    <section class="matches-section" aria-label="Recent matches">
      <div class="cmp-section-header"><h2>Recent history</h2></div>
      <p v-if="historyLoading && !history.length" class="cmp-loading-state" role="status">Loading match history…</p>
      <p v-if="historyError" class="cmp-error-state" role="alert">{{ historyError }} <button class="matches-retry cmp-button cmp-button--secondary" type="button" @click="loadHistory">Retry</button></p>
      <p v-else-if="!historyLoading && !history.length" class="cmp-empty-state">No confirmed matches yet.</p>
      <ol v-if="history.length" class="matches-history">
        <li v-for="match in history" :key="match.lobbyId" class="matches-row" :class="[`cmp-faction--${match.factionId}`, resultTone(match.result.outcome)]">
          <div class="matches-row-result"><strong>{{ match.result.placement ? placementName(match.result.placement) : outcomeName(match.result.outcome) }}</strong><span v-if="match.result.placement">{{ outcomeName(match.result.outcome) }}</span></div>
          <div class="matches-row-main"><strong class="cmp-faction-marker">{{ factionName(match.factionId) }} <small>· {{ match.rosterStatus === 'reserve' ? 'Reserve' : 'Active' }}</small></strong><time :datetime="match.matchAt">{{ matchDate(match.matchAt) }}</time></div>
          <div class="matches-row-rating"><span v-if="match.rating">After match</span><strong :aria-label="match.rating ? `Rating change ${ratingText(match.rating)}` : 'No rating change recorded'" :class="ratingTone(match.rating)">{{ ratingText(match.rating) }}</strong></div>
          <details v-if="match.result.corrected" class="matches-row-context"><summary class="matches-corrected">Corrected</summary><span v-if="match.result.revisionNumber">Confirmed revision {{ match.result.revisionNumber }}</span></details>
        </li>
      </ol>
    </section>
  </div>
</template>

<style scoped>
.matches-page { display: grid; gap: var(--cmp-section-gap); max-width: 920px; }
.matches-heading { margin-bottom: 0; }
.matches-section { display: grid; gap: var(--cmp-space-3); min-width: 0; }
.matches-section .cmp-section-header { margin-bottom: 0; }
.matches-current { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-4); padding: var(--cmp-space-3) var(--cmp-space-2); border-bottom: 1px solid var(--cmp-border); border-left: 2px solid var(--cmp-faction-color, var(--cmp-primary)); }
.matches-current > div { display: grid; gap: var(--cmp-space-1); }
.matches-current strong { font-size: 1rem; }
.matches-current p:last-child { margin: 0; color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); }
.matches-retry { margin-left: var(--cmp-space-3); }
.matches-history { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--cmp-border); }
.matches-row { display: grid; grid-template-columns: 104px minmax(0, 1fr) 125px; align-items: center; gap: var(--cmp-space-2) var(--cmp-space-4); min-width: 0; padding: var(--cmp-space-3) var(--cmp-space-2); border-bottom: 1px solid var(--cmp-border); }
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
.matches-row-context { grid-column: 2 / -1; display: flex; flex-wrap: wrap; gap: var(--cmp-space-1) var(--cmp-space-3); margin: 0; color: var(--cmp-text-muted); font-size: .75rem; overflow-wrap: anywhere; }
.matches-corrected { color: var(--cmp-primary-hover); font-weight: 650; }
@media (max-width: 640px) { .matches-current { align-items: flex-start; flex-direction: column; padding: var(--cmp-space-4); }.matches-row { grid-template-columns: minmax(0, 1fr) auto; gap: var(--cmp-space-2); }.matches-row-result { grid-column: 1; }.matches-row-main { grid-column: 1 / -1; grid-row: 2; }.matches-row-rating { grid-column: 2; grid-row: 1; text-align: right; }.matches-row-context { grid-column: 1 / -1; }.matches-retry { display: flex; margin: var(--cmp-space-2) 0 0; } }
</style>
