<script setup>
import { computed } from 'vue';

const props = defineProps({ match: { type: Object, required: true }, summaries: { type: Object, required: true }, rankedResults: { type: Array, required: true } });
const ordinal = (rank) => ({ 1: '1st', 2: '2nd', 3: '3rd' })[rank] || `${rank}th`;
const scoreNote = computed(() => {
  if (props.match.source === 'cmp-backend') {
    if (props.match.observation?.state === 'stale') return 'Last known server scores. The live observation may be stale.';
    if (props.match.observation?.state === 'unavailable') return 'Server observation unavailable. No scores have been confirmed.';
    if (props.match.observation?.state === 'none') return 'No successful server score observation yet.';
    if (props.match.result?.status !== 'unconfirmed') return 'Observed server scores are evidence. The referee-confirmed result is shown above.';
    return 'Observed server scores are evidence only. No result has been confirmed.';
  }
  return props.match.phase === 'results' ? props.match.result.note
    : 'Scores may be delayed or unavailable. Current leader is not an authoritative winner.';
});
</script>

<template>
  <section class="wardogs-score-section cmp-surface" aria-label="Observed score evidence">
    <div class="wardogs-score-heading"><div><p class="cmp-kicker">{{ match.source === 'cmp-backend' ? 'Server evidence' : 'Sample evidence' }}</p><h2>{{ match.source === 'cmp-backend' ? 'Observed scores' : match.label }}</h2></div><strong>{{ match.source === 'cmp-backend' ? 'Not an official result' : 'Mock scores · no lifecycle inference' }}</strong></div>
    <p class="wardogs-score-note">{{ scoreNote }}</p>
    <div class="wardogs-score-grid">
      <div v-for="faction in match.factions" :key="faction.id" class="wardogs-score-row" :class="`cmp-faction--${faction.id}`">
        <span class="cmp-faction-marker">{{ faction.name }}</span><strong>{{ match.scores[faction.id] ?? '—' }}</strong>
        <span v-if="rankedResults.length" class="wardogs-rank">{{ rankedResults.find((row) => row.faction.id === faction.id)?.tied ? 'Tied ' : '' }}{{ ordinal(rankedResults.find((row) => row.faction.id === faction.id)?.rank) }}</span>
      </div>
    </div>
    <details v-if="match.source === 'cmp-backend' && match.unexpectedPlayers?.length" class="cmp-disclosure wardogs-score-detail"><summary>Unexpected server players · {{ match.unexpectedPlayers.length }}</summary><ul><li v-for="(player, index) in match.unexpectedPlayers" :key="`${player.steamId || 'unknown'}-${index}`">{{ player.displayName }} · {{ player.observedFactionName || 'Faction unknown' }}</li></ul></details>
    <details v-if="match.phase === 'live' && match.source !== 'cmp-backend'" class="cmp-disclosure wardogs-score-detail"><summary>Recent demo observations</summary><ul><li v-for="observation in match.observations" :key="observation">{{ observation }}</li></ul></details>
    <details v-else-if="match.source !== 'cmp-backend'" class="cmp-disclosure wardogs-score-detail"><summary>Sample player statistics · presentation only</summary><p v-if="!rankedResults.length">Ranking withheld until a complete, confirmed result is available.</p><div v-for="faction in match.factions" :key="faction.id" class="wardogs-stat-row"><strong>{{ faction.name }}</strong><span v-for="player in faction.groups.flatMap((group) => group.players).slice(0, 2)" :key="player.id">{{ player.displayName }} · K {{ player.stats.kills }} / D {{ player.stats.deaths }} / A {{ player.stats.assists }}</span></div></details>
  </section>
</template>
