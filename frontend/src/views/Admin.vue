<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../stores/authStore';
import { useRootStore } from '../stores/rootStore';
import { useSocketStore } from '../stores/socketStore';
import { API_BASE_URL } from '../config';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { formatQueueModeCapacity } from '../features/admin/diagnostics';
import {
  formatJoinStrategy,
  formatLookupStep,
  getServerDiscovery,
  getServerJoinStrategy
} from '../features/server/utils/serverDiscovery';

const authStore = useAuthStore();
const rootStore = useRootStore();
const socketStore = useSocketStore();

const diagnostics = ref(null);
const servers = ref([]);
const serversLoaded = ref(false);
const loading = ref(false);
const serverLoading = ref(false);
const error = ref('');
const serverError = ref('');
const automationLoading = ref(false);
const adminModeLoading = ref(false);
const wardogsDev = ref(null);
const wardogsDevError = ref('');
const wardogsDevBusy = ref(false);
const wardogsDevLoading = ref(false);
const wardogsDevAvailable = computed(() => import.meta.env.DEV && isAdmin.value && wardogsDev.value !== null);
const wardogsDevVisible = computed(() => import.meta.env.DEV && isAdmin.value);
const wardogsServers = computed(() => servers.value.filter((server) => server.game_type === 'wardogs'));
const otherServers = computed(() => servers.value.filter((server) => server.game_type !== 'wardogs'));
const wardogsQueueModes = computed(() => queueModeDiagnostics.value.filter((mode) => mode.gameType === 'wardogs'));
const wardogsRuntimeCapacity = computed(() => diagnostics.value?.serverAvailabilityByGame?.wardogs || null);

const loadWardogsDev = async () => {
  if (!import.meta.env.DEV || !isAdmin.value) return;
  wardogsDevLoading.value = true;
  try {
    wardogsDev.value = await apiFetch('/admin/dev/wardogs');
    wardogsDevError.value = '';
  } catch (err) {
    wardogsDevError.value = err.message || 'WARDOGS dev tools unavailable';
  } finally {
    wardogsDevLoading.value = false;
  }
};

const wardogsDevAction = async (path, body = {}) => {
  wardogsDevBusy.value = true;
  wardogsDevError.value = '';
  try {
    await apiFetch(`/admin/dev/wardogs/${path}`, { method: 'POST', body: JSON.stringify(body) });
    await loadWardogsDev();
  } catch (err) {
    wardogsDevError.value = err.message || 'WARDOGS dev action failed';
  } finally {
    wardogsDevBusy.value = false;
  }
};

const wardogsLobbyAction = async (action) => {
  const lobbyId = wardogsDev.value?.lobbyId;
  if (!lobbyId) return;
  if (action === 'cleanup' && !window.confirm('Delete this WARDOGS test lobby and release its server allocation?')) return;
  wardogsDevBusy.value = true;
  wardogsDevError.value = '';
  try {
    await apiFetch(`/admin/wardogs/lobbies/${encodeURIComponent(lobbyId)}${action === 'allocate' ? '/allocate' : ''}`,
      { method: action === 'allocate' ? 'POST' : 'DELETE' });
    await loadWardogsDev();
  } catch (err) {
    wardogsDevError.value = err.message || 'WARDOGS lobby action failed';
  } finally {
    wardogsDevBusy.value = false;
  }
};

const automationMode = computed(() => diagnostics.value?.automation?.mode || 'on');
const automationModes = [
  {
    id: 'on',
    label: 'On',
    description: 'Allow layer changes, broadcasts, team moves, kicks, and match end commands.'
  },
  {
    id: 'monitor',
    label: 'Monitor Only',
    description: 'Keep reading server state but block all RCON write commands.'
  },
  {
    id: 'off',
    label: 'Off',
    description: 'Pause live automation so admins can run the match manually.'
  }
];

const activeLobbies = computed(() => diagnostics.value?.activeLobbies || []);
const recentEvents = computed(() => diagnostics.value?.recentEvents || []);
const historyCounts = computed(() => diagnostics.value?.historyCounts || {});
const queueModeDiagnostics = computed(() => Object.values(diagnostics.value?.queueModes || {}));

const isAdmin = computed(() => !!authStore.token && !!authStore.isAdmin);
const canAccessAdminPage = computed(() => !!authStore.token && (authStore.isAdmin || authStore.canToggleAdmin));
const getEosDiscovery = (value) => value?.metadata?.eosDiscovery || value?.eosDiscovery || null;
const formatEosDiscovery = (value) => {
  if (!value) return 'Not attempted';
  if (!value.configured) return 'Not configured';
  if (!value.attempted) return 'Not attempted';
  if (value.error) return value.error;
  if (value.matched && value.targetServerId) return value.targetServerId;
  return 'No EOS session match';
};
const getLiveSession = (value) => value?.metadata?.liveSession || value?.liveSession || null;
const formatDateTime = (value) => {
  if (!value) return 'Unavailable';
  const numeric = Number(value);
  const date = Number.isFinite(numeric) ? new Date(numeric * 1000) : new Date(value);
  return Number.isNaN(date.getTime()) ? 'Unavailable' : date.toLocaleString();
};
const formatLobbyPhase = (step) => {
  const phases = {
    1: 'Acceptance',
    2: 'Map Vote',
    3: 'Join Server',
    4: 'Live',
    5: 'Score'
  };
  return phases[Number(step)] || `Step ${step || '-'}`;
};
const formatEventType = (value) => String(value || 'event').replaceAll('_', ' ');
const isWarningEvent = (value) => /failed|error|unauthorized|skipped|blocked|timeout|warning/i.test(String(value || ''));
const formatLiveSession = (value) => {
  if (!value || !value.matched || !value.targetServerId) return 'No verified live session';
  return value.targetServerId;
};
const runtimeCapacityLabel = (value) => {
  if (!value || typeof value.available !== 'boolean') return 'Unknown';
  if (Number(value.capacity) <= 0) return 'No registered capacity';
  return value.available ? 'Headroom reported' : 'At runtime capacity';
};
const runtimeCapacityTone = (value) => {
  if (!value || typeof value.available !== 'boolean') return 'is-neutral';
  return value.available ? 'is-good' : 'is-attention';
};

const apiFetch = async (path, options = {}) => {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authStore.token}`,
      ...(options.headers || {})
    }
  });
  const text = await response.text();
  let payload = null;
  try {
    payload = text ? JSON.parse(text) : null;
  } catch {
    throw new Error(`Expected JSON from ${path}, received ${response.headers.get('content-type') || 'unknown content'}`);
  }
  if (!response.ok || !payload?.success) {
    throw new Error(payload?.message || 'Request failed');
  }
  return payload;
};

const loadDiagnostics = async () => {
  if (!isAdmin.value) return;
  loading.value = true;
  error.value = '';
  try {
    const payload = await apiFetch('/admin/diagnostics');
    diagnostics.value = payload.diagnostics || null;
  } catch (err) {
    error.value = err.message || 'Failed to load diagnostics';
    rootStore.setError(error.value);
  } finally {
    loading.value = false;
  }
};

const loadServers = async () => {
  if (!isAdmin.value) return;
  serverLoading.value = true;
  serverError.value = '';
  try {
    const payload = await apiFetch('/admin/servers');
    servers.value = payload.servers || [];
    serversLoaded.value = true;
  } catch (err) {
    serverError.value = err.message || 'Failed to load servers';
    rootStore.setError(serverError.value);
  } finally {
    serverLoading.value = false;
  }
};

const setSelfAdminMode = async (enabled) => {
  adminModeLoading.value = true;
  try {
    const payload = await apiFetch('/admin/self-mode', {
      method: 'POST',
      body: JSON.stringify({ enabled })
    });
    if (payload.profile) {
      authStore.updateProfile(payload.profile);
    }
    if (enabled) {
      await loadDiagnostics();
      await loadServers();
      await loadWardogsDev();
    } else {
      diagnostics.value = null;
      servers.value = [];
      serversLoaded.value = false;
    }
  } catch (err) {
    rootStore.setError(err.message || 'Failed to update admin test mode');
  } finally {
    adminModeLoading.value = false;
  }
};

const setAutomationMode = async (mode) => {
  if (mode === automationMode.value) return;
  automationLoading.value = true;
  try {
    const payload = await apiFetch('/admin/automation', {
      method: 'POST',
      body: JSON.stringify({ mode })
    });
    diagnostics.value = {
      ...(diagnostics.value || {}),
      automation: payload.automation
    };
    await loadDiagnostics();
  } catch (err) {
    rootStore.setError(err.message || 'Failed to update automation mode');
  } finally {
    automationLoading.value = false;
  }
};

const deleteActiveLobby = async (lobbyId) => {
  if (!lobbyId) return;
  const confirmed = window.confirm(`Delete lobby ${lobbyId} and release its server allocation?`);
  if (!confirmed) return;

  loading.value = true;
  try {
    const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.DELETE, {
      lobby_id: lobbyId
    });
    if (!response?.success) {
      throw new Error(response?.message || 'Failed to delete lobby');
    }
    await loadDiagnostics();
    await loadServers();
  } catch (err) {
    rootStore.setError({
      message: 'Failed to delete lobby',
      details: err.message,
      context: 'admin-lobby-delete'
    });
  } finally {
    loading.value = false;
  }
};

onMounted(async () => {
  await authStore.syncProfile();
  await Promise.all([loadDiagnostics(), loadServers(), loadWardogsDev()]);
});
</script>

<template>
  <main class="admin-page cmp-page cmp-page-content">
    <header class="cmp-page-header admin-header">
      <div><p class="cmp-kicker">WARDOGS operations</p><h1>Admin</h1><p>System signals, server registry, and controlled local test tools.</p></div>
      <button v-if="isAdmin" class="cmp-button cmp-button--secondary" type="button" :disabled="loading || serverLoading" @click="loadDiagnostics(); loadServers()">
        {{ loading || serverLoading ? 'Refreshing…' : 'Refresh status' }}
      </button>
    </header>

    <details v-if="canAccessAdminPage && authStore.canToggleAdmin" class="admin-mode cmp-disclosure">
      <summary>Root admin test mode <span>{{ authStore.isAdmin ? 'Admin mode active' : 'Regular-user test' }}</span></summary>
      <p>{{ authStore.isAdmin ? 'CMP lobby and team enforcement bypasses apply.' : 'Lobby membership and assigned team are enforced.' }}</p>
      <div class="admin-actions">
        <button class="cmp-button cmp-button--secondary" type="button" :disabled="adminModeLoading || authStore.isAdmin" @click="setSelfAdminMode(true)">Admin On</button>
        <button class="cmp-button cmp-button--secondary" type="button" :disabled="adminModeLoading || !authStore.isAdmin" @click="setSelfAdminMode(false)">Test Regular</button>
      </div>
    </details>

    <p v-if="!isAdmin && !canAccessAdminPage" class="cmp-error-state" role="alert">Admin access is required.</p>

    <template v-if="isAdmin">
      <section class="admin-section" aria-label="System diagnostics">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Platform signals</p><h2>System health</h2></div><span v-if="diagnostics" class="admin-updated">Updated {{ formatDateTime(diagnostics.generatedAt) }}</span></div>
        <p v-if="loading && !diagnostics" role="status" class="cmp-loading-state">Loading system signals…</p>
        <p v-if="error" role="alert" class="cmp-error-state">{{ error }} <button type="button" class="text-action" @click="loadDiagnostics">Retry diagnostics</button><span v-if="diagnostics">Showing last successful diagnostics.</span></p>
        <template v-if="diagnostics">
          <dl class="signal-list">
            <div class="signal-row"><dt>Backend database</dt><dd class="signal-value" :class="diagnostics.database?.ok === true ? 'is-good' : diagnostics.database?.ok === false ? 'is-attention' : 'is-neutral'">{{ diagnostics.database?.ok === true ? 'Healthy' : diagnostics.database?.ok === false ? 'Needs attention' : 'Unknown' }}</dd></div>
            <div v-if="diagnostics.bridge?.enabled !== false" class="signal-row"><dt>CMP bridge</dt><dd class="signal-value" :class="diagnostics.bridge?.ok ? 'is-good' : 'is-attention'">{{ diagnostics.bridge?.ok ? 'Healthy' : 'Degraded' }}</dd></div>
            <div class="signal-row"><dt>WARDOGS queue capacity</dt><dd class="signal-value" :class="runtimeCapacityTone(wardogsRuntimeCapacity)">{{ runtimeCapacityLabel(wardogsRuntimeCapacity) }}</dd><small v-if="wardogsRuntimeCapacity">{{ wardogsRuntimeCapacity.activeLobbyCount || 0 }} active lobbies · {{ wardogsRuntimeCapacity.activePendingMatchCount || 0 }} pending acceptances · {{ wardogsRuntimeCapacity.capacity || 0 }} registered-server capacity</small></div>
            <div class="signal-row"><dt>EOS integration</dt><dd class="signal-value" :class="diagnostics.eos?.configured ? 'is-good' : 'is-attention'">{{ diagnostics.eos?.configured ? 'Configured' : 'Not configured' }}</dd></div>
            <div class="signal-row"><dt>RCON automation</dt><dd class="signal-value">{{ automationMode }} · {{ diagnostics.automation?.rconWritesEnabled ? 'writes enabled' : 'writes blocked' }}</dd></div>
          </dl>
          <p class="admin-note">Queue capacity describes runtime headroom from diagnostics. It does not guarantee a server will pass the allocator’s registry and fresh-health checks.</p>
          <div class="automation-control">
            <div><h3>Automation mode</h3><p>Control existing server write behavior.</p></div>
            <div class="admin-actions" role="group" aria-label="Automation mode">
              <button v-for="mode in automationModes" :key="mode.id" type="button" class="cmp-button cmp-button--secondary" :aria-pressed="automationMode === mode.id" :disabled="automationLoading || loading || !!error" :title="mode.description" @click="setAutomationMode(mode.id)">{{ mode.label }}</button>
            </div>
          </div>
          <details v-if="queueModeDiagnostics.length" class="admin-disclosure">
            <summary>Queue mode detail <span>{{ queueModeDiagnostics.length }}</span></summary>
            <div v-for="mode in queueModeDiagnostics" :key="mode.id" class="detail-row"><span>{{ mode.label }}</span><strong>{{ mode.size }} queued</strong><small>{{ formatQueueModeCapacity(mode) }}</small></div>
          </details>
          <details class="admin-disclosure">
            <summary>CMP audit events <span>{{ recentEvents.length }} recent</span></summary>
            <p v-if="!recentEvents.length" class="admin-note">No recent events.</p>
            <div v-for="event in recentEvents" :key="event.id" class="detail-row" :class="{ 'is-warning': isWarningEvent(event.event_type) }"><span>{{ formatEventType(event.event_type) }}</span><strong>{{ isWarningEvent(event.event_type) ? 'Review' : 'Recorded' }} · {{ formatDateTime(event.created_at) }}</strong><small>Lobby {{ event.lobby_id || 'unavailable' }}</small></div>
            <p class="admin-note">{{ historyCounts.lobbyEvents || 0 }} lobby events recorded.</p>
          </details>
        </template>
      </section>

      <section class="admin-section" aria-label="WARDOGS server registry">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Operations</p><h2>WARDOGS server registry</h2></div><span class="admin-updated">{{ serversLoaded ? `${wardogsServers.length} registered` : serverLoading ? 'Loading' : 'Unknown' }}</span></div>
        <p v-if="serverLoading && !serversLoaded" role="status" class="cmp-loading-state">Loading registered servers…</p>
        <p v-if="serverError" role="alert" class="cmp-error-state">{{ serverError }} <button type="button" class="text-action" @click="loadServers">Retry servers</button><span v-if="serversLoaded">Showing the last successful registry read; probe and assignment details may be stale.</span></p>
        <p v-if="serversLoaded && !wardogsServers.length" class="cmp-empty-state">No WARDOGS servers are registered.</p>
        <div v-for="server in wardogsServers" :key="server.id" class="server-row">
          <div class="server-identity"><strong>{{ server.display_name || server.slug || `Server ${server.id}` }}</strong><span>Registry ID {{ server.id }} · {{ server.approved_by ? 'Approved' : 'Awaiting approval' }}</span></div>
          <div class="server-state"><span>Registry state</span><strong>{{ server.enabled ? 'Enabled' : 'Disabled' }} · {{ server.status || 'Unknown' }}</strong></div>
          <div class="server-state"><span>Last probe</span><strong>{{ server.last_health_status || 'Not checked' }}</strong><small>{{ formatDateTime(server.last_health_check_at) }}</small></div>
          <div class="server-assignment"><span>Current match</span><RouterLink v-if="server.current_lobby_id" :to="`/wardogs/lobby/${server.current_lobby_id}`">{{ server.current_lobby_id }} · Open match</RouterLink><strong v-else>Unassigned</strong></div>
          <details class="server-details">
            <summary>Probe and registry detail</summary>
            <div class="detail-row"><span>Approval</span><strong>{{ server.approved_by ? `Approved by ${server.approved_by}` : 'Awaiting approval' }}</strong></div>
            <div class="detail-row"><span>Reservation</span><strong>{{ server.current_lobby_id ? `Assigned to ${server.current_lobby_id}` : 'No current match recorded' }}</strong></div>
            <div v-if="server.last_health_error" class="detail-row is-warning"><span>Probe issue</span><strong>{{ server.last_health_error }}</strong></div>
            <div v-if="getServerDiscovery(server)" class="detail-row"><span>Steam discovery</span><strong>{{ formatLookupStep(getServerDiscovery(server)?.a2s) }}</strong></div>
            <div v-if="getEosDiscovery(server)" class="detail-row"><span>EOS session lookup</span><strong>{{ formatEosDiscovery(getEosDiscovery(server)) }}</strong></div>
            <div v-if="getLiveSession(server)" class="detail-row"><span>Verified live session</span><strong>{{ formatLiveSession(getLiveSession(server)) }}</strong></div>
            <div v-if="getServerJoinStrategy(server)" class="detail-row"><span>Join method</span><strong>{{ formatJoinStrategy(getServerJoinStrategy(server)) }}</strong></div>
            <p class="admin-note">WARDOGS allocation checks approval, enabled state, a recent healthy probe, and reservation ownership when it runs. This registry view does not predict that decision.</p>
          </details>
        </div>
        <p v-if="serversLoaded && !serverError" class="admin-note">Registry writes remain disabled here. Allocation retry is limited to the local test workflow.</p>
        <details v-if="otherServers.length" class="admin-disclosure other-servers"><summary>Other registered game servers <span>{{ otherServers.length }}</span></summary>
          <div v-for="server in otherServers" :key="server.id" class="detail-row"><span>{{ server.display_name || server.slug || `Server ${server.id}` }} · {{ server.game_type }}</span><strong>{{ server.approved_by ? 'Approved' : 'Awaiting approval' }} · {{ server.enabled ? 'Enabled' : 'Disabled' }} · {{ server.status || 'Unknown' }}</strong><small>Last probe {{ server.last_health_status || 'Not checked' }} · {{ formatDateTime(server.last_health_check_at) }} · {{ server.current_lobby_id || 'Unassigned' }}</small></div>
        </details>
      </section>

      <section class="admin-section runtime-section" aria-label="Queue and runtime">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Live operations</p><h2>Queue &amp; runtime</h2></div><span class="admin-updated">{{ wardogsQueueModes.reduce((total, mode) => total + mode.size, 0) }} WARDOGS waiting</span></div>
        <p v-if="!wardogsQueueModes.length" class="admin-note">No WARDOGS queue modes are present in diagnostics.</p>
        <div v-else class="runtime-modes">
          <div v-for="mode in wardogsQueueModes" :key="mode.id" class="detail-row"><span>{{ mode.label }}</span><strong>{{ mode.size }} queued</strong><small>{{ formatQueueModeCapacity(mode) }} · {{ mode.pendingMatch ? `${mode.pendingMatch.acceptedCount}/${mode.pendingMatch.requiredCount} accepted` : 'No pending acceptance' }}</small></div>
        </div>
        <div class="runtime-summary">
          <div><span>Active CMP lobbies</span><strong>{{ activeLobbies.length }}</strong></div>
          <div><span>Pending acceptance</span><strong>{{ diagnostics?.pendingMatch ? `${diagnostics.pendingMatch.acceptedCount}/${diagnostics.pendingMatch.requiredCount} · ${diagnostics.pendingMatch.label}` : 'None reported' }}</strong></div>
        </div>
        <details v-if="activeLobbies.length" class="admin-disclosure">
          <summary>Active lobby detail <span>{{ activeLobbies.length }}</span></summary>
          <div v-for="lobby in activeLobbies" :key="lobby.lobby_id" class="detail-row"><span>{{ lobby.lobby_id }}</span><strong>{{ formatLobbyPhase(lobby.step) }} · {{ lobby.players }} players</strong><small>{{ lobby.selected_map || 'No layer selected' }}<template v-if="lobby.live_started_at"> · Live since {{ formatDateTime(lobby.live_started_at) }}</template></small></div>
        </details>
      </section>

      <section v-if="wardogsDevVisible" class="admin-section dev-section" aria-label="WARDOGS developer tools">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Local environment</p><h2>Test harness</h2></div><span class="environment-label">Development only</span></div>
        <p class="admin-note">These controls affect local WARDOGS test state. Join from Play first; synthetic players auto-accept. Simulated presence is separate from real WDRCON observation.</p>
        <p v-if="wardogsDevLoading && !wardogsDev" role="status" class="cmp-loading-state">Loading test state…</p>
        <p v-if="wardogsDevError" role="alert" class="cmp-error-state">{{ wardogsDevError }} <button class="text-action" type="button" @click="loadWardogsDev">Retry test tools</button><span v-if="wardogsDev">Showing the last successful test state; controls are disabled until it refreshes.</span></p>
        <template v-if="wardogsDevAvailable">
          <dl class="test-state-list">
            <div class="signal-row"><dt>Test queue</dt><dd>{{ wardogsDev.queue?.length || 0 }} queued · {{ wardogsDev.pendingMatch ? 'Acceptance active' : 'No pending acceptance' }}</dd></div>
            <div class="signal-row"><dt>Test match</dt><dd><RouterLink v-if="wardogsDev.lobbyId" :to="`/wardogs/lobby/${wardogsDev.lobbyId}`">{{ wardogsDev.lobbyId }} · Open match</RouterLink><span v-else>None</span></dd></div>
          </dl>
          <div class="admin-action-row"><div><h3>Fill queue</h3><p>Add synthetic players to the local test queue. Your acceptance remains manual.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsDevAction('fill')">Fill test queue</button></div>
          <div class="admin-action-row"><div><h3>Presence overlay</h3><p>Switch between simulated presence and real observations for this test match.</p></div><div class="admin-actions"><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsDevAction('simulate', { lobbyId: wardogsDev.lobbyId, enabled: true })">Simulate connected</button><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsDevAction('simulate', { lobbyId: wardogsDev.lobbyId, enabled: false })">Real observations only</button></div></div>
          <div class="admin-action-row"><div><h3>Allocation retry</h3><p>Retry allocation for the current local test lobby.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsLobbyAction('allocate')">Retry allocation</button></div>
          <div class="admin-action-row"><div><h3>Participant preview</h3><p>Change this view while keeping your admin permission.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="authStore.wardogsParticipantPreview = !authStore.wardogsParticipantPreview">{{ authStore.wardogsParticipantPreview ? 'View as admin' : 'View as participant' }}</button></div>
          <p class="admin-note">Result confirmation and correction stay with the match in Match Room.</p>
        </template>
      </section>

      <section v-if="diagnostics?.activeLobbies?.length || wardogsDevAvailable" class="admin-section danger-section" aria-label="Reset and cleanup">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Recovery</p><h2>Reset &amp; cleanup</h2></div><span class="danger-label">Destructive actions</span></div>
        <div v-if="wardogsDevAvailable" class="admin-action-row"><div><h3>Reset synthetic state</h3><p>Cancel test acceptance and remove synthetic queue players and presence overlay. Confirmed results remain.</p></div><button class="cmp-button cmp-button--danger" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsDevAction('reset')">Reset test queue / overlay</button></div>
        <div v-if="wardogsDevAvailable && wardogsDev.lobbyId" class="admin-action-row"><div><h3>Delete test lobby</h3><p>Delete this local WARDOGS lobby and release its server allocation. Confirmation is required.</p></div><button class="cmp-button cmp-button--danger" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsLobbyAction('cleanup')">Delete test lobby</button></div>
        <details v-if="activeLobbies.length" class="admin-disclosure"><summary>CMP lobby cleanup <span>{{ activeLobbies.length }}</span></summary>
          <div v-for="lobby in activeLobbies" :key="lobby.lobby_id" class="admin-action-row"><div><h3>{{ lobby.lobby_id }}</h3><p>{{ formatLobbyPhase(lobby.step) }} · {{ lobby.players }} players · {{ lobby.selected_map || 'No layer selected' }}</p><small v-if="lobby.announcement">{{ lobby.announcement }}</small><small v-if="lobby.live_roll_done"> · Live roll complete</small><small v-if="lobby.server_details_provided_at"> · Details sent {{ formatDateTime(lobby.server_details_provided_at) }}</small><small v-if="lobby.live_started_at"> · Live started {{ formatDateTime(lobby.live_started_at) }}</small></div><button class="cmp-button cmp-button--danger" type="button" :disabled="loading" @click="deleteActiveLobby(lobby.lobby_id)">Delete lobby</button></div>
        </details>
      </section>
    </template>
  </main>
</template>

<style scoped>
.admin-page { display: grid; gap: var(--cmp-section-gap); max-width: 1120px; }
.admin-header { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--cmp-space-5); margin: 0; }
.admin-header > div { display: grid; gap: var(--cmp-space-2); }
.admin-section { display: grid; gap: var(--cmp-space-3); min-width: 0; padding-top: var(--cmp-space-4); border-top: 1px solid var(--cmp-border); }
.admin-section-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: var(--cmp-space-4); }
.admin-section-heading > div { display: grid; gap: var(--cmp-space-1); }
.admin-section-heading h2 { margin: 0; font-size: var(--cmp-type-section); line-height: 1.3; }
.admin-updated { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); text-align: right; }
.signal-list, .test-state-list { display: grid; margin: 0; padding: 0; }
.signal-row { display: grid; grid-template-columns: minmax(180px, .8fr) minmax(0, 1.2fr); align-items: baseline; gap: var(--cmp-space-1) var(--cmp-space-5); padding: var(--cmp-space-3) var(--cmp-space-2); border-bottom: 1px solid var(--cmp-border); }
.signal-row:first-child { border-top: 1px solid var(--cmp-border); }
.signal-row dt, .signal-row > span { color: var(--cmp-text-secondary); font-size: .875rem; }
.signal-row dd, .signal-row > strong { margin: 0; font-size: .875rem; font-weight: 650; text-align: right; }
.signal-row small { grid-column: 2; color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); text-align: right; overflow-wrap: anywhere; }
.signal-value.is-good { color: var(--cmp-success); }
.signal-value.is-attention { color: var(--cmp-warning); }
.signal-value.is-neutral { color: var(--cmp-text-muted); }
.automation-control { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-4); padding: var(--cmp-space-3) var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.automation-control h3, .admin-action-row h3 { margin: 0; font-size: .9375rem; }
.automation-control p, .admin-action-row p, .admin-note { margin: var(--cmp-space-1) 0 0; color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); line-height: 1.5; }
.admin-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--cmp-space-2); }
.admin-page .cmp-button { min-height: 42px; }
.admin-page .cmp-button[aria-pressed="true"] { border-color: var(--cmp-primary); background: var(--cmp-surface-strong); }
.admin-disclosure { padding-top: var(--cmp-space-3); border-top: 1px solid var(--cmp-border); }
.admin-disclosure summary, .server-details summary { display: flex; align-items: baseline; justify-content: space-between; gap: var(--cmp-space-3); min-height: 42px; color: var(--cmp-text-secondary); font-size: .875rem; font-weight: 650; cursor: pointer; }
.admin-disclosure summary span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); font-weight: 500; text-align: right; }
.admin-disclosure summary:focus-visible, .server-details summary:focus-visible { outline: 2px solid var(--cmp-focus); outline-offset: 3px; }
.detail-row { display: grid; grid-template-columns: minmax(180px, .8fr) minmax(0, 1.2fr); align-items: baseline; gap: var(--cmp-space-1) var(--cmp-space-5); padding: var(--cmp-space-3) var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.detail-row > span { color: var(--cmp-text-secondary); font-size: .875rem; overflow-wrap: anywhere; }
.detail-row > strong { font-size: .875rem; font-weight: 650; text-align: right; overflow-wrap: anywhere; }
.detail-row small { grid-column: 1 / -1; color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); overflow-wrap: anywhere; }
.detail-row.is-warning > strong { color: var(--cmp-warning); }
.server-row { display: grid; grid-template-columns: minmax(200px, 1.4fr) minmax(135px, .8fr) minmax(135px, .8fr) minmax(150px, 1fr); gap: var(--cmp-space-3) var(--cmp-space-5); align-items: center; padding: var(--cmp-space-4) var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.server-identity, .server-state, .server-assignment { display: grid; gap: var(--cmp-space-1); min-width: 0; }
.server-identity strong { font-size: .9375rem; overflow-wrap: anywhere; }
.server-identity span, .server-state span, .server-state small, .server-assignment > span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); overflow-wrap: anywhere; }
.server-state strong, .server-assignment strong, .server-assignment a { color: var(--cmp-text); font-size: .875rem; font-weight: 650; overflow-wrap: anywhere; }
.server-assignment a { color: var(--cmp-primary-hover); }
.server-details { grid-column: 1 / -1; min-width: 0; padding-top: var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.server-details .detail-row:first-of-type { border-top: 0; }
.admin-note { margin: 0; }
.admin-section > .cmp-error-state, .admin-section > .cmp-loading-state, .admin-section > .cmp-empty-state { display: grid; gap: var(--cmp-space-2); }
.text-action { width: fit-content; padding: 0; border: 0; background: none; color: var(--cmp-primary-hover); font: 650 .875rem var(--cmp-font-body); cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.text-action:focus-visible { outline: 2px solid var(--cmp-focus); outline-offset: 3px; }
.runtime-modes { display: grid; }
.runtime-summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--cmp-space-5); padding: var(--cmp-space-4) var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.runtime-summary > div { display: grid; gap: var(--cmp-space-1); min-width: 0; }
.runtime-summary span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.runtime-summary strong { font-size: .9375rem; overflow-wrap: anywhere; }
.dev-section { border-top-color: var(--cmp-primary); }
.environment-label { padding: 4px 8px; border: 1px solid var(--cmp-border-strong); border-radius: var(--cmp-radius-sm); color: var(--cmp-primary-hover); font-size: var(--cmp-type-meta); font-weight: 650; }
.test-state-list { margin-top: var(--cmp-space-2); }
.admin-action-row { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-5); padding: var(--cmp-space-4) var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.admin-action-row > div:first-child { min-width: 0; }
.admin-action-row .cmp-button { flex: none; }
.danger-section { border-top-color: color-mix(in srgb, var(--cmp-danger) 60%, var(--cmp-border)); }
.danger-label { color: var(--cmp-danger); font-size: var(--cmp-type-meta); font-weight: 650; }
.danger-section .admin-action-row { border-top-color: color-mix(in srgb, var(--cmp-danger) 22%, var(--cmp-border)); }
.admin-mode { padding-top: 0; }
.admin-mode summary { color: var(--cmp-text-secondary); }
.admin-mode > p { margin: 0 0 var(--cmp-space-3); color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.admin-mode .admin-actions { justify-content: flex-start; padding-bottom: var(--cmp-space-3); }
@media (max-width: 900px) {
  .server-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .server-details { grid-column: 1 / -1; }
}
@media (max-width: 680px) {
  .admin-header, .automation-control, .admin-action-row { align-items: flex-start; flex-direction: column; }
  .admin-header > button, .admin-action-row > .cmp-button { width: 100%; }
  .admin-actions { justify-content: flex-start; }
  .signal-row, .detail-row { grid-template-columns: minmax(0, 1fr) auto; gap: var(--cmp-space-1) var(--cmp-space-3); }
  .signal-row small { grid-column: 1 / -1; text-align: left; }
  .runtime-summary { grid-template-columns: 1fr; gap: var(--cmp-space-3); }
  .other-servers .detail-row { grid-template-columns: 1fr; }
  .other-servers .detail-row > strong { text-align: left; }
}
@media (max-width: 480px) {
  .admin-section-heading { align-items: flex-start; flex-direction: column; gap: var(--cmp-space-2); }
  .admin-updated { text-align: left; }
  .server-row { grid-template-columns: minmax(0, 1fr); gap: var(--cmp-space-3); padding-inline: var(--cmp-space-2); }
  .server-details { grid-column: auto; }
  .signal-row, .detail-row { grid-template-columns: minmax(0, 1fr); }
  .signal-row dd, .signal-row > strong, .detail-row > strong { text-align: left; }
  .signal-row small, .detail-row small { grid-column: auto; }
  .automation-control .admin-actions, .admin-action-row .admin-actions { width: 100%; }
  .admin-action-row .admin-actions .cmp-button { flex: 1 1 100%; }
  .admin-disclosure summary span { text-align: left; }
}
</style>
