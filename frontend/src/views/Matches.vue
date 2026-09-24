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
  <main class="matches-page cmp-page">
    <header class="matches-heading"><h1>Matches</h1></header>

    <section class="matches-section" aria-label="Current match">
      <h2>Current match</h2>
      <p v-if="currentLoading && !current" role="status">Checking your current match…</p>
      <div v-if="current" class="matches-current">
        <div>
          <strong>{{ current.state === 'waiting_for_server' ? 'Waiting for server' : 'Server allocated' }}</strong>
          <p>{{ factionName(current.factionId) }} · {{ current.rosterStatus === 'reserve' ? 'Reserve' : 'Active' }}</p>
        </div>
        <RouterLink class="cmp-button cmp-button--primary" :to="`/wardogs/lobby/${current.lobbyId}`">Open match</RouterLink>
      </div>
      <p v-else-if="!currentLoading && !currentError" class="matches-muted">No current WARDOGS match. <RouterLink to="/play">Go to Play</RouterLink></p>
      <p v-if="currentError" role="alert">{{ currentError }} <button class="matches-retry" type="button" @click="loadCurrent">Retry</button></p>
    </section>

    <section class="matches-section" aria-label="Recent matches">
      <div class="matches-section-heading"><h2>Recent matches</h2><span v-if="history.length">{{ history.length }} shown</span></div>
      <p v-if="historyLoading && !history.length" role="status">Loading match history…</p>
      <p v-if="historyError" role="alert">{{ historyError }} <button class="matches-retry" type="button" @click="loadHistory">Retry</button></p>
      <p v-else-if="!historyLoading && !history.length" class="matches-muted">No referee-confirmed WARDOGS matches yet. Your results will appear here after confirmation.</p>
      <ol v-if="history.length" class="matches-history">
        <li v-for="match in history" :key="match.lobbyId" class="matches-row">
          <div class="matches-row-main"><time>Confirmed {{ matchDate(match.matchAt) }}</time><strong>{{ factionName(match.factionId) }} <small>· {{ match.rosterStatus === 'reserve' ? 'Reserve' : 'Active' }}</small></strong></div>
          <div class="matches-row-result"><strong>{{ outcomeName(match.result.outcome) }}</strong><small v-if="match.result.placement">{{ placementName(match.result.placement) }} place</small><small v-if="match.result.corrected">Corrected · revision {{ match.result.revisionNumber }}</small></div>
          <div class="matches-row-rating"><span>WARDOGS rating</span><strong>{{ ratingText(match.rating) }}</strong></div>
          <p v-if="match.result.placementGroups" class="matches-placement">{{ placementContext(match.result.placementGroups) }}</p>
        </li>
      </ol>
    </section>
  </main>
</template>

<style scoped>
.matches-page { width: min(100%, 960px); margin: 0 auto; padding: clamp(18px, 3vw, 32px) var(--cmp-page-gutter); display: grid; gap: 24px; }
.matches-heading h1 { margin: 0; font: 800 clamp(1.5rem, 3vw, 2rem) var(--cmp-font-display); }
.matches-section { display: grid; gap: 10px; min-width: 0; }
.matches-section h2 { margin: 0; font: 800 1rem var(--cmp-font-display); }
.matches-section-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.matches-section-heading span, .matches-muted { color: var(--cmp-text-muted); font-size: .82rem; }
.matches-muted { margin: 0; }.matches-muted a { color: var(--cmp-primary-hover); }
.matches-current { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 14px 16px; border: 1px solid var(--cmp-border); border-left: 3px solid var(--cmp-primary-hover); background: var(--cmp-surface); }
.matches-current strong { font-size: .95rem; }.matches-current p { margin: 3px 0 0; color: var(--cmp-text-muted); font-size: .8rem; }
.matches-retry { border: 0; padding: 0; background: none; color: var(--cmp-primary-hover); cursor: pointer; font: inherit; text-decoration: underline; }
.matches-history { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.matches-row { display: grid; grid-template-columns: minmax(180px, 1.5fr) minmax(125px, 1fr) minmax(130px, .8fr); align-items: center; gap: 8px 16px; min-width: 0; padding: 11px 14px; border: 1px solid var(--cmp-border); background: var(--cmp-surface); }
.matches-row-main, .matches-row-result, .matches-row-rating { display: grid; gap: 3px; min-width: 0; }
.matches-row-main time, .matches-row-result small, .matches-row-rating span { color: var(--cmp-text-muted); font-size: .71rem; }
.matches-row-main strong, .matches-row-result strong, .matches-row-rating strong { font-size: .85rem; }
.matches-row-main small { color: var(--cmp-text-muted); font-weight: 400; }
.matches-row-rating strong { font-family: var(--cmp-font-mono); }
.matches-placement { grid-column: 1 / -1; margin: 0; color: var(--cmp-text-muted); font-size: .72rem; overflow-wrap: anywhere; }
@media (max-width: 600px) { .matches-current { align-items: flex-start; flex-direction: column; }.matches-row { grid-template-columns: 1fr 1fr; }.matches-row-rating { grid-column: 1 / -1; }.matches-placement { grid-column: 1 / -1; } }
</style>
