<script setup>
import { onMounted } from 'vue';
import { storeToRefs } from 'pinia';
import { useWardogsMatchStore } from './stores/matchStore';
import MatchOverview from './components/MatchOverview.vue';
import FactionRoster from './components/FactionRoster.vue';
import ScoreAndResults from './components/ScoreAndResults.vue';
import './wardogs.css';

const store = useWardogsMatchStore();
const { match, scenarioKey, scenarioOptions, totals, factionSummaries, rankedResults, loading, error } = storeToRefs(store);
onMounted(() => store.selectScenario(scenarioKey.value));
const onScenarioChange = (event) => store.selectScenario(event.target.value);
</script>

<template>
  <main class="wardogs-demo">
    <header class="wardogs-header">
      <div>
        <p class="eyebrow">WARDOGS / CMP feature preview</p>
        <h1>Three-faction match room</h1>
        <p>Local mock scenarios. No WDRCON or CMP match lifecycle connection.</p>
      </div>
      <label class="wardogs-selector">
        <span>Scenario</span>
        <select :value="scenarioKey" @change="onScenarioChange">
          <option v-for="option in scenarioOptions" :key="option.key" :value="option.key">{{ option.label }}</option>
        </select>
      </label>
    </header>

    <p v-if="loading" role="status">Loading mock scenario…</p>
    <p v-if="error" role="alert">{{ error }}</p>
    <template v-if="match">
      <MatchOverview :match="match" :totals="totals" />
      <section v-if="match.phase === 'assembling'" aria-label="Faction rosters">
        <div class="wardogs-section-heading">
          <div><p class="section-kicker">Hybrid roster assembly</p><h2>{{ match.label }}</h2></div>
          <span>Groups stay together · solos fill gaps</span>
        </div>
        <div class="wardogs-faction-grid">
          <FactionRoster v-for="faction in match.factions" :key="faction.id" :faction="faction" :summary="factionSummaries[faction.id]" />
        </div>
      </section>
      <ScoreAndResults v-else :match="match" :summaries="factionSummaries" :ranked-results="rankedResults" />
    </template>
  </main>
</template>
