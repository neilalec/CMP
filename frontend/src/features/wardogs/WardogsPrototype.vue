<script setup>
import { watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { useAuthStore } from '../../stores/authStore';
import { createBackendWardogsDataSource } from './api/backendDataSource';
import { useWardogsMatchStore } from './stores/matchStore';
import MatchOverview from './components/MatchOverview.vue';
import FactionRoster from './components/FactionRoster.vue';
import ScoreAndResults from './components/ScoreAndResults.vue';
import './wardogs.css';

const store = useWardogsMatchStore();
const authStore = useAuthStore();
const route = useRoute();
const { match, mode, scenarioKey, scenarioOptions, totals, factionSummaries, rankedResults, loading, error } = storeToRefs(store);
watch(() => [route.query.source, route.query.lobby], () => {
  if (route.query.source === 'backend') {
    const lobbyId = typeof route.query.lobby === 'string' ? route.query.lobby : '';
    store.loadBackendLobby(lobbyId, createBackendWardogsDataSource({ getToken: () => authStore.token }));
  } else {
    store.selectScenario(scenarioKey.value);
  }
}, { immediate: true });
const onScenarioChange = (event) => store.selectScenario(event.target.value);
</script>

<template>
  <main class="wardogs-demo">
    <header class="wardogs-header">
      <div>
        <p class="eyebrow">WARDOGS / CMP feature preview</p>
        <h1>Three-faction match room</h1>
        <p v-if="mode === 'mock'">Local mock scenarios. No WDRCON or CMP match lifecycle connection.</p>
        <p v-else>Read-only CMP lobby snapshot. Connection and scores are observations; results remain unconfirmed.</p>
      </div>
      <label v-if="mode === 'mock'" class="wardogs-selector">
        <span>Scenario</span>
        <select :value="scenarioKey" @change="onScenarioChange">
          <option v-for="option in scenarioOptions" :key="option.key" :value="option.key">{{ option.label }}</option>
        </select>
      </label>
    </header>

    <p v-if="loading" role="status">Loading WARDOGS lobby…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="match">
      <MatchOverview :match="match" :totals="totals" />
      <section v-if="match.phase === 'assembling'" aria-label="Faction rosters">
        <div class="wardogs-section-heading">
          <div><p class="section-kicker">{{ mode === 'mock' ? 'Hybrid roster assembly' : 'Planned WARDOGS roster' }}</p><h2>{{ match.label }}</h2></div>
          <span v-if="mode === 'mock'">Groups stay together · solos fill gaps</span>
          <span v-else>Planned groups and observed server presence</span>
        </div>
        <div class="wardogs-faction-grid">
          <FactionRoster v-for="faction in match.factions" :key="faction.id" :faction="faction" :summary="factionSummaries[faction.id]" />
        </div>
      </section>
      <ScoreAndResults v-else :match="match" :summaries="factionSummaries" :ranked-results="rankedResults" />
    </template>
  </main>
</template>
