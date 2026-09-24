<script setup>
import { computed } from 'vue';

const props = defineProps({ match: { type: Object, required: true }, summaries: { type: Object, required: true }, rankedResults: { type: Array, required: true } });
const ordinal = (rank) => ({ 1: '1st', 2: '2nd', 3: '3rd' })[rank] || `${rank}th`;
const scoreNote = computed(() => {
  if (props.match.source === 'cmp-backend') {
    if (props.match.observation?.state === 'stale') return 'Last known server scores. The live observation may be stale.';
    if (props.match.observation?.state === 'unavailable') return 'Server observation unavailable. No scores have been confirmed.';
    if (props.match.result?.status !== 'unconfirmed') return 'Observed server scores are evidence. The referee-confirmed result is shown above.';
  }
  return props.match.phase === 'results' ? props.match.result.note
    : 'Scores may be delayed or unavailable. Current leader is not an authoritative winner.';
});
</script>

<template>
  <section class="wardogs-score-section">
    <div class="wardogs-section-heading">
      <div><p class="wardogs-kicker">{{ match.source === 'cmp-backend' ? 'Server score observation' : match.phase === 'live' ? 'Observed score snapshot' : 'Three-way result layout' }}</p><h2>{{ match.source === 'cmp-backend' ? 'Observed scores' : match.label }}</h2></div>
      <span>{{ match.source === 'cmp-backend' ? 'Not an official result' : 'Mock scores · no lifecycle inference' }}</span>
    </div>
    <p class="wardogs-result-note">{{ scoreNote }}</p>
    <div class="wardogs-score-grid">
      <article v-for="faction in match.factions" :key="faction.id" class="wardogs-score-card" :style="{ '--faction-color': faction.color }">
        <span>{{ faction.name }}</span>
        <strong>{{ match.scores[faction.id] ?? '—' }}</strong>
        <small v-if="match.source === 'cmp-backend' && ['none', 'unavailable'].includes(match.observation?.state)">Presence unknown</small>
        <small v-else>{{ summaries[faction.id].connected }}/{{ summaries[faction.id].active }} {{ match.observation?.state === 'stale' ? 'last seen connected' : 'connected' }}</small>
        <span v-if="rankedResults.length" class="wardogs-rank">
          {{ rankedResults.find((row) => row.faction.id === faction.id)?.tied ? 'Tied ' : '' }}{{ ordinal(rankedResults.find((row) => row.faction.id === faction.id)?.rank) }}
        </span>
      </article>
    </div>
    <div v-if="match.source === 'cmp-backend' && match.unexpectedPlayers?.length" class="cmp-surface wardogs-panel" aria-label="Unexpected server players">
      <header class="cmp-panel-header"><h3 class="cmp-heading wardogs-panel-heading">Unexpected server players</h3></header>
      <ul class="wardogs-observations"><li v-for="(player, index) in match.unexpectedPlayers" :key="`${player.steamId || 'unknown'}-${index}`">{{ player.displayName }} · {{ player.observedFactionName || 'Faction unknown' }}</li></ul>
    </div>
    <div v-if="match.phase === 'live' && match.source !== 'cmp-backend'" class="cmp-surface wardogs-panel">
      <header class="cmp-panel-header"><h3 class="cmp-heading wardogs-panel-heading">{{ match.source === 'cmp-backend' ? 'Server observations' : 'Recent demo observations' }}</h3></header>
      <ul class="wardogs-observations"><li v-for="observation in match.observations" :key="observation">{{ observation }}</li></ul>
    </div>
    <div v-else-if="match.source !== 'cmp-backend'" class="cmp-surface wardogs-panel">
      <header class="cmp-panel-header"><h3 class="cmp-heading wardogs-panel-heading">Sample player statistics</h3><span class="cmp-panel-meta">PRESENTATION ONLY</span></header>
      <p v-if="!rankedResults.length" class="wardogs-result-note">Ranking withheld until a complete, confirmed result is available.</p>
      <div v-for="faction in match.factions" :key="faction.id" class="wardogs-stat-row">
        <strong>{{ faction.name }}</strong>
        <span v-for="player in faction.groups.flatMap((group) => group.players).slice(0, 2)" :key="player.id">{{ player.displayName }} · K {{ player.stats.kills }} / D {{ player.stats.deaths }} / A {{ player.stats.assists }}</span>
      </div>
    </div>
  </section>
</template>
