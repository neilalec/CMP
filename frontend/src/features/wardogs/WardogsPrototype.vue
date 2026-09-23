<script setup>
import { computed, onUnmounted, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { useAuthStore } from '../../stores/authStore';
import { useSocketStore } from '../../stores/socketStore';
import { socketService } from '../../services/socketService';
import { createBackendWardogsDataSource } from './api/backendDataSource';
import { useWardogsMatchStore } from './stores/matchStore';
import MatchOverview from './components/MatchOverview.vue';
import FactionRoster from './components/FactionRoster.vue';
import ScoreAndResults from './components/ScoreAndResults.vue';
import JoinState from './components/JoinState.vue';
import './wardogs.css';

const store = useWardogsMatchStore();
const authStore = useAuthStore();
const socketStore = useSocketStore();
const route = useRoute();
const { match, mode, scenarioKey, scenarioOptions, totals, factionSummaries, rankedResults, loading, error } = storeToRefs(store);
const backendLobbyId = computed(() => route.name === 'wardogs-lobby' || route.query.source === 'backend'
  ? (typeof route.params.lobbyId === 'string' ? route.params.lobbyId
    : (typeof route.query.lobby === 'string' ? route.query.lobby : '')) : '');
const backendSource = createBackendWardogsDataSource({ getToken: () => authStore.token });
let liveSocket = null;
let subscribedLobbyId = null;
const onLiveUpdate = (data) => {
  if (data?.lobbyId === backendLobbyId.value) store.refreshBackendLobby(data.lobbyId, backendSource);
};
const subscribe = () => {
  const lobbyId = backendLobbyId.value;
  if (!liveSocket?.connected || !lobbyId || !authStore.token) return;
  const socket = liveSocket;
  socket.emit('wardogs_lobby_subscribe', { lobbyId, token: authStore.token }, (reply) => {
    if (!reply?.success) return;
    if (liveSocket !== socket || backendLobbyId.value !== lobbyId) {
      socket.emit('wardogs_lobby_unsubscribe', { lobbyId });
      return;
    }
    subscribedLobbyId = lobbyId;
    store.refreshBackendLobby(lobbyId, backendSource);
  });
};
const detach = () => {
  if (liveSocket) {
    if (subscribedLobbyId && liveSocket.connected) {
      liveSocket.emit('wardogs_lobby_unsubscribe', { lobbyId: subscribedLobbyId });
    }
    liveSocket.off('wardogs_lobby_update', onLiveUpdate);
    liveSocket.off('connect', subscribe);
  }
  liveSocket = null;
  subscribedLobbyId = null;
};
watch(() => [backendLobbyId.value, socketStore.isConnected, authStore.token], () => {
  const socket = socketService.socket;
  if (!backendLobbyId.value || !socketStore.isConnected || !authStore.token || !socket) {
    detach();
    return;
  }
  if (liveSocket !== socket || (subscribedLobbyId && subscribedLobbyId !== backendLobbyId.value)) {
    detach();
    liveSocket = socket;
    liveSocket.on('wardogs_lobby_update', onLiveUpdate);
    liveSocket.on('connect', subscribe);
  }
  subscribe();
}, { immediate: true });
watch(backendLobbyId, (lobbyId) => {
  if (lobbyId) {
    store.loadBackendLobby(lobbyId, backendSource);
  } else {
    store.selectScenario(scenarioKey.value);
  }
}, { immediate: true });
onUnmounted(detach);
const onScenarioChange = (event) => store.selectScenario(event.target.value);
</script>

<template>
  <main class="wardogs-demo">
    <header class="wardogs-header">
      <div>
        <p class="eyebrow">WARDOGS / CMP feature preview</p>
        <h1>Three-faction match room</h1>
        <p v-if="mode === 'mock'">Local mock scenarios. No WDRCON or CMP match lifecycle connection.</p>
        <p v-else>Live server observations update this lobby. Scores are not official results.</p>
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
      <JoinState v-if="mode === 'backend'" :join="match.join" />
      <MatchOverview :match="match" :totals="totals" />
      <section v-if="mode === 'backend' || match.phase === 'assembling'" aria-label="Faction rosters">
        <div class="wardogs-section-heading">
          <div><p class="section-kicker">{{ mode === 'mock' ? 'Hybrid roster assembly' : 'Planned WARDOGS roster' }}</p><h2>{{ match.label }}</h2></div>
          <span v-if="mode === 'mock'">Groups stay together · solos fill gaps</span>
          <span v-else>Planned groups and observed server presence</span>
        </div>
        <div class="wardogs-faction-grid">
          <FactionRoster v-for="faction in match.factions" :key="faction.id" :faction="faction" :summary="factionSummaries[faction.id]" :observation-state="match.observation?.state" />
        </div>
      </section>
      <ScoreAndResults v-if="mode === 'backend' || match.phase !== 'assembling'" :match="match" :summaries="factionSummaries" :ranked-results="rankedResults" />
    </template>
  </main>
</template>
