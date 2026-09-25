<script setup>
import { computed, onUnmounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useRoute } from 'vue-router';
import { useAuthStore } from '../../stores/authStore';
import { useSocketStore } from '../../stores/socketStore';
import { socketService } from '../../services/socketService';
import { createBackendWardogsDataSource } from './api/backendDataSource';
import { useWardogsMatchStore } from './stores/matchStore';
import MatchOverview from './components/MatchOverview.vue';
import MatchStateHeader from './components/MatchStateHeader.vue';
import FactionRoster from './components/FactionRoster.vue';
import ScoreAndResults from './components/ScoreAndResults.vue';
import JoinState from './components/JoinState.vue';
import WardogsResultConfirmation from './components/WardogsResultConfirmation.vue';
import './wardogs.css';
import { findParticipant, matchRoomState } from './models/presentation';

const store = useWardogsMatchStore();
const authStore = useAuthStore();
const participantPreview = computed(() => import.meta.env.DEV && authStore.wardogsParticipantPreview);
const socketStore = useSocketStore();
const route = useRoute();
const { match, mode, scenarioKey, scenarioOptions, factionSummaries, rankedResults, loading, error } = storeToRefs(store);
const participant = computed(() => findParticipant(match.value, authStore.username));
const roomState = computed(() => match.value ? matchRoomState(match.value, participant.value) : null);
const backendLobbyId = computed(() => route.name === 'wardogs-lobby' || route.query.source === 'backend'
  ? (typeof route.params.lobbyId === 'string' ? route.params.lobbyId
    : (typeof route.query.lobby === 'string' ? route.query.lobby : '')) : '');
const backendSource = createBackendWardogsDataSource({ getToken: () => authStore.token });
let liveSocket = null;
let subscribedLobbyId = null;
const confirmingResult = ref(false);
const correctingResult = ref(false);
const resultHistory = ref([]);
const resultHistoryError = ref('');
const loadResultHistory = async (lobbyId) => {
  if (!lobbyId || !authStore.isAdmin || participantPreview.value) {
    resultHistory.value = [];
    resultHistoryError.value = '';
    return;
  }
  try {
    const revisions = await backendSource.loadResultHistory(lobbyId);
    if (backendLobbyId.value !== lobbyId || !authStore.isAdmin || participantPreview.value) return;
    resultHistory.value = revisions;
    resultHistoryError.value = '';
  } catch {
    resultHistory.value = [];
    resultHistoryError.value = 'Administrator result history is unavailable. Refresh to try again.';
  }
};
const confirmResult = async (submission) => {
  if (!backendLobbyId.value) return;
  confirmingResult.value = true;
  try {
    const confirmed = await store.confirmBackendResult(backendLobbyId.value, submission, backendSource);
    if (confirmed) await loadResultHistory(backendLobbyId.value);
  } finally {
    confirmingResult.value = false;
  }
};
const correctResult = async (correction) => {
  const lobbyId = backendLobbyId.value;
  if (!lobbyId) return;
  correctingResult.value = true;
  resultHistoryError.value = '';
  try {
    await backendSource.correctResult(lobbyId, correction);
    await store.refreshBackendLobby(lobbyId, backendSource);
    await loadResultHistory(lobbyId);
  } catch (correctionError) {
    if (correctionError.code === 'stale_revision') {
      await Promise.all([store.refreshBackendLobby(lobbyId, backendSource), loadResultHistory(lobbyId)]);
      resultHistoryError.value = 'The result changed while this form was open. History was refreshed; review the current revision and start again.';
    } else {
      store.error = correctionError.message || 'Result correction failed';
    }
  } finally {
    correctingResult.value = false;
  }
};
const onLiveUpdate = (data) => {
  if (data?.lobbyId === backendLobbyId.value) store.refreshBackendLobby(data.lobbyId, backendSource);
};
const subscribe = () => {
  const lobbyId = backendLobbyId.value;
  if (!liveSocket?.connected || !lobbyId || !authStore.token) return;
  const socket = liveSocket;
  socket.emit('wardogs_lobby_subscribe', { lobbyId }, (reply) => {
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
watch(() => [backendLobbyId.value, authStore.isAdmin, participantPreview.value, match.value?.result?.revisionNumber],
  ([lobbyId, isAdmin, preview]) => { if (lobbyId && isAdmin && !preview) loadResultHistory(lobbyId); }, { immediate: true });
onUnmounted(detach);
const onScenarioChange = (event) => store.selectScenario(event.target.value);
</script>

<template>
  <component :is="authStore.isLoggedIn ? 'div' : 'main'" class="wardogs-demo cmp-page">
    <header v-if="mode === 'mock' || participantPreview" class="wardogs-header">
      <p v-if="mode === 'mock'">Local mock scenarios · no CMP match lifecycle connection</p>
      <p v-if="participantPreview">Developer participant preview — your admin role is unchanged.</p>
      <label v-if="mode === 'mock'" class="wardogs-selector">
        <span>Scenario</span>
        <select class="cmp-input" :value="scenarioKey" @change="onScenarioChange">
          <option v-for="option in scenarioOptions" :key="option.key" :value="option.key">{{ option.label }}</option>
        </select>
      </label>
    </header>

    <p v-if="loading" class="cmp-loading-state" role="status">Loading WARDOGS lobby…</p>
    <p v-if="error" class="cmp-error-state" role="alert">{{ error }}</p>
    <template v-if="match">
      <MatchStateHeader :match="match" :participant="participant" />
      <p v-if="mode === 'backend'" class="wardogs-observation-banner cmp-status" :class="match.observation?.state === 'fresh' ? 'cmp-status--success' : 'cmp-status--stale'" role="status">
        <span v-if="match.observation?.state === 'fresh'">Server observation current<span v-if="match.observation.observedAt"> · {{ match.observation.observedAt }}</span></span>
        <span v-else-if="match.observation?.state === 'stale'">Server observation stale · roster presence is last known, not current<span v-if="match.observation.observedAt"> · {{ match.observation.observedAt }}</span></span>
        <span v-else>Server presence unknown<span v-if="match.observation?.pollState === 'error'"> · latest read unavailable</span></span>
      </p>
      <JoinState v-if="mode === 'backend' && match.join.state !== 'waiting_for_server'" :join="match.join" :prominent="roomState.joinProminent" />
      <WardogsResultConfirmation v-if="mode === 'backend' && roomState.resultProminent" :match="match" :can-confirm="authStore.isAdmin && !participantPreview" :confirming="confirmingResult" :correcting="correctingResult" :result-history="resultHistory" :history-error="resultHistoryError" @confirm="confirmResult" @correct="correctResult" />
      <section class="wardogs-roster-area" aria-label="Faction rosters">
        <div class="wardogs-section-heading cmp-section-header">
          <div><p class="cmp-kicker">Planned assignment</p><h2>Faction rosters</h2></div>
          <p>Server observations appear in each roster</p>
        </div>
        <div class="wardogs-faction-grid">
          <FactionRoster v-for="faction in match.factions" :key="faction.id" :faction="faction" :summary="factionSummaries[faction.id]" :observation-state="match.observation?.state || (mode === 'mock' ? 'demo' : 'none')" :my-group-id="participant?.group.id" :my-player-id="participant?.player.id" />
        </div>
      </section>
      <ScoreAndResults v-if="mode === 'backend' || match.phase !== 'assembling'" :match="match" :summaries="factionSummaries" :ranked-results="rankedResults" />
      <WardogsResultConfirmation v-if="mode === 'backend' && !roomState.resultProminent" :match="match" :can-confirm="authStore.isAdmin && !participantPreview" :confirming="confirmingResult" :correcting="correctingResult" :result-history="resultHistory" :history-error="resultHistoryError" @confirm="confirmResult" @correct="correctResult" />
      <MatchOverview :match="match" />
    </template>
  </component>
</template>
