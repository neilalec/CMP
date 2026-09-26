<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../stores/authStore';
import { useRootStore } from '../stores/rootStore';
import { useSocketStore } from '../stores/socketStore';
import { useQueueStore } from '../stores/queueStore';
import { useGroupStore } from '../stores/groupStore';
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
const queueStore = useQueueStore();
const participantGroupStore = useGroupStore();
const seedCount = ref(1);

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
const wardogsQueueBusy = ref(false);
const wardogsDevAvailable = computed(() => import.meta.env.DEV && isAdmin.value && wardogsDev.value !== null);
const wardogsDevVisible = computed(() => import.meta.env.DEV && isAdmin.value);
const wardogsServers = computed(() => servers.value.filter((server) => server.game_type === 'wardogs'));
const otherServers = computed(() => servers.value.filter((server) => server.game_type !== 'wardogs'));
const wardogsQueueModes = computed(() => queueModeDiagnostics.value.filter((mode) => mode.gameType === 'wardogs'));
const wardogsRuntimeCapacity = computed(() => diagnostics.value?.serverAvailabilityByGame?.wardogs || null);
const systemSummary = computed(() => {
  if (!diagnostics.value) return loading.value ? 'Loading' : 'Unknown';
  const database = diagnostics.value.database?.ok;
  const bridge = diagnostics.value.bridge;
  if (database === false || (bridge?.enabled !== false && bridge?.ok === false)) return 'Needs attention';
  if (database === true && (bridge?.enabled === false || bridge?.ok === true)) return 'Healthy';
  return 'Partial checks';
});
const queueSummary = computed(() => {
  if (!diagnostics.value) return loading.value ? 'Loading' : 'Unknown';
  const sizes = wardogsQueueModes.value.map((mode) => mode.size);
  if (!sizes.length || sizes.some((size) => typeof size !== 'number' || !Number.isFinite(size))) return 'Unknown';
  const total = sizes.reduce((sum, size) => sum + size, 0);
  return `${total} waiting`;
});
const serverSummary = computed(() => {
  if (!wardogsRuntimeCapacity.value || typeof wardogsRuntimeCapacity.value.available !== 'boolean') {
    return diagnostics.value ? 'Unknown' : (loading.value || serverLoading.value ? 'Loading' : 'Unknown');
  }
  const capacity = wardogsRuntimeCapacity.value.capacity;
  if (typeof capacity !== 'number' || !Number.isFinite(capacity)) return 'Unknown';
  if (capacity <= 0) return 'No registered capacity';
  return `${wardogsRuntimeCapacity.value.available ? 'Runtime headroom reported' : 'At runtime capacity'} · ${capacity} registered`;
});
const systemNeedsAttention = computed(() => systemSummary.value === 'Needs attention');
const activeLobbyCount = computed(() => Array.isArray(diagnostics.value?.activeLobbies)
  ? activeLobbies.value.length
  : 'Unknown');

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
const manageWardogsQueue = async (mode, action) => {
  if (!import.meta.env.DEV || !isAdmin.value) return;
  wardogsQueueBusy.value = true;
  wardogsDevError.value = '';
  try {
    if (action === 'clear') await queueStore.clearQueue(mode.id);
    else await queueStore.setQueueEnabled(mode.id, mode.enabled === false);
    await loadDiagnostics();
    await loadWardogsDev();
  } catch (err) {
    wardogsDevError.value = err.message || 'WARDOGS queue action failed';
  } finally {
    wardogsQueueBusy.value = false;
  }
};
const seedWardogsGroup = async () => {
  const count = Number(seedCount.value);
  if (!Number.isFinite(count) || count < 1) {
    rootStore.setError('Enter a valid bot count.');
    return;
  }
  try {
    await participantGroupStore.seedGroup(Math.floor(count));
  } catch (err) {
    rootStore.setError(err.message || 'Failed to seed group');
  }
};
const runtimeCapacityLabel = (value) => {
  if (!value || typeof value.available !== 'boolean'
    || typeof value.capacity !== 'number' || !Number.isFinite(value.capacity)) return 'Unknown';
  if (value.capacity <= 0) return 'No registered capacity';
  return value.available ? 'Headroom reported' : 'At runtime capacity';
};
const runtimeCapacityTone = (value) => {
  if (!value || typeof value.available !== 'boolean') return 'is-neutral';
  return value.available ? 'is-good' : 'is-attention';
};
const queueModeSize = (mode) => typeof mode?.size === 'number' && Number.isFinite(mode.size) ? mode.size : null;

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
  if (authStore.username) await participantGroupStore.syncStatus(authStore.username);
  await Promise.all([loadDiagnostics(), loadServers(), loadWardogsDev()]);
});
</script>

<template>
  <div class="admin-page cmp-page cmp-page-content">
    <header class="cmp-page-header admin-header">
      <div><p class="cmp-kicker">WARDOGS operations</p><h1>Admin</h1></div>
      <button v-if="isAdmin" class="cmp-button cmp-button--secondary" type="button" :disabled="loading || serverLoading" @click="loadDiagnostics(); loadServers()">
        {{ loading || serverLoading ? 'Refreshing…' : 'Refresh' }}
      </button>
    </header>

    <dl v-if="isAdmin" class="operator-summary" aria-label="WARDOGS operational summary">
      <div><dt>System</dt><dd :class="systemNeedsAttention ? 'is-attention' : ''">{{ systemSummary }}</dd></div>
      <div><dt>Queue</dt><dd>{{ queueSummary }}</dd></div>
      <div><dt>Servers</dt><dd>{{ serverSummary }}</dd></div>
    </dl>

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
      <div v-if="error || serverError" class="operator-alerts" aria-label="Operational problems">
        <p v-if="error" class="cmp-error-state" role="alert">Diagnostics: {{ error }} <button type="button" class="text-action" @click="loadDiagnostics">Retry diagnostics</button><span v-if="diagnostics">Showing last successful read.</span></p>
        <p v-if="serverError" class="cmp-error-state" role="alert">Server registry: {{ serverError }} <button type="button" class="text-action" @click="loadServers">Retry servers</button><span v-if="serversLoaded">Showing last successful registry read; probe details may be stale.</span></p>
        <p v-if="systemNeedsAttention" class="cmp-error-state" role="status">A system health check needs attention. Review the system detail below.</p>
        <p v-if="wardogsRuntimeCapacity?.available === false" class="cmp-error-state" role="status">WARDOGS runtime reports no headroom{{ wardogsRuntimeCapacity.reason ? `: ${String(wardogsRuntimeCapacity.reason).replaceAll('_', ' ')}` : '' }}.</p>
      </div>

      <section class="admin-section runtime-section" aria-label="Queue and runtime">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Live operations</p><h2>Queue &amp; runtime</h2></div><span class="admin-updated">{{ diagnostics ? queueSummary : loading ? 'Loading' : 'Unknown' }}</span></div>
        <p v-if="!diagnostics" class="admin-note" role="status">{{ loading ? 'Loading runtime diagnostics…' : 'Runtime diagnostics are unavailable. Retry diagnostics to restore live counts.' }}</p>
        <template v-else>
          <p v-if="error" class="admin-note" role="status">Showing the last successful runtime read; counts may be stale.</p>
          <p v-if="!wardogsQueueModes.length" class="admin-note">No WARDOGS queue modes are present in diagnostics.</p>
          <div v-for="mode in wardogsQueueModes" :key="mode.id" class="runtime-mode">
            <div><strong>{{ mode.label }}</strong><small>{{ formatQueueModeCapacity(mode) }}</small></div>
            <strong>{{ queueModeSize(mode) === null ? 'Unknown' : `${queueModeSize(mode)} waiting` }}</strong>
            <span>{{ mode.pendingMatch === null ? 'No pending acceptance' : mode.pendingMatch ? `${mode.pendingMatch.acceptedCount}/${mode.pendingMatch.requiredCount} accepted` : 'Unknown acceptance state' }}</span>
          </div>
          <div class="runtime-summary">
            <div><span>Active matches</span><strong>{{ activeLobbyCount }}</strong></div>
            <div><span>Pending acceptance</span><strong>{{ diagnostics?.pendingMatch === null ? 'None reported' : diagnostics?.pendingMatch ? `${diagnostics.pendingMatch.acceptedCount}/${diagnostics.pendingMatch.requiredCount}` : 'Unknown' }}</strong></div>
          </div>
          <div v-if="activeLobbies.length" class="active-lobby-list" aria-label="Active matches">
            <RouterLink v-for="lobby in activeLobbies" :key="lobby.lobby_id" class="active-lobby-row" :to="`/wardogs/lobby/${lobby.lobby_id}`">
              <span>{{ lobby.lobby_id }}</span><strong>{{ formatLobbyPhase(lobby.step) }} · {{ lobby.players }} players</strong><span>Open match</span>
            </RouterLink>
          </div>
        </template>
      </section>

      <section class="admin-section" aria-label="WARDOGS server registry">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Infrastructure</p><h2>WARDOGS servers</h2></div><span class="admin-updated">{{ serversLoaded ? `${wardogsServers.length} registered` : serverLoading ? 'Loading' : 'Unknown' }}</span></div>
        <p v-if="serverLoading && !serversLoaded" role="status" class="cmp-loading-state">Loading registered servers…</p>
        <p v-if="serversLoaded && !wardogsServers.length" class="cmp-empty-state">No WARDOGS servers are registered.</p>
        <div v-for="server in wardogsServers" :key="server.id" class="server-row">
          <div class="server-identity"><strong>{{ server.display_name || server.slug || `Server ${server.id}` }}</strong><span>ID {{ server.id }} · {{ server.approved_by ? 'Approved' : 'Awaiting approval' }} · {{ server.enabled ? 'Enabled' : 'Disabled' }}</span></div>
          <div class="server-state"><span>Last probe</span><strong>{{ server.last_health_status || 'Not checked' }}</strong><small>{{ formatDateTime(server.last_health_check_at) }}</small></div>
          <div class="server-assignment"><span>Assignment</span><RouterLink v-if="server.current_lobby_id" :to="`/wardogs/lobby/${server.current_lobby_id}`">{{ server.current_lobby_id }} · Open match</RouterLink><strong v-else>Unassigned</strong></div>
          <details class="server-details cmp-disclosure">
            <summary>Technical detail</summary>
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
        <details v-if="otherServers.length" class="cmp-disclosure admin-disclosure other-servers"><summary>Other registered game servers <span>{{ otherServers.length }}</span></summary>
          <div v-for="server in otherServers" :key="server.id" class="detail-row"><span>{{ server.display_name || server.slug || `Server ${server.id}` }} · {{ server.game_type }}</span><strong>{{ server.approved_by ? 'Approved' : 'Awaiting approval' }} · {{ server.enabled ? 'Enabled' : 'Disabled' }} · {{ server.status || 'Unknown' }}</strong><small>Last probe {{ server.last_health_status || 'Not checked' }} · {{ formatDateTime(server.last_health_check_at) }} · {{ server.current_lobby_id || 'Unassigned' }}</small></div>
        </details>
      </section>

      <details v-if="diagnostics" class="admin-section system-detail cmp-disclosure" aria-label="System diagnostics">
        <summary><span><span class="cmp-kicker">Platform signals</span><strong>System detail</strong></span><span>Updated {{ formatDateTime(diagnostics.generatedAt) }}</span></summary>
        <dl class="signal-list">
          <div class="signal-row"><dt>Backend database</dt><dd class="signal-value" :class="diagnostics.database?.ok === true ? 'is-good' : diagnostics.database?.ok === false ? 'is-attention' : 'is-neutral'">{{ diagnostics.database?.ok === true ? 'Healthy' : diagnostics.database?.ok === false ? 'Needs attention' : 'Unknown' }}</dd></div>
          <div v-if="diagnostics.bridge?.enabled !== false" class="signal-row"><dt>CMP bridge</dt><dd class="signal-value" :class="diagnostics.bridge?.ok ? 'is-good' : 'is-attention'">{{ diagnostics.bridge?.ok ? 'Healthy' : 'Degraded' }}</dd></div>
          <div class="signal-row"><dt>EOS integration</dt><dd class="signal-value">{{ diagnostics.eos?.configured ? 'Configured' : 'Not configured' }}</dd></div>
          <div class="signal-row"><dt>RCON automation</dt><dd class="signal-value">{{ automationMode }} · {{ diagnostics.automation?.rconWritesEnabled ? 'writes enabled' : 'writes blocked' }}</dd></div>
          <div class="signal-row"><dt>Runtime headroom</dt><dd class="signal-value" :class="runtimeCapacityTone(wardogsRuntimeCapacity)">{{ runtimeCapacityLabel(wardogsRuntimeCapacity) }}</dd><small v-if="wardogsRuntimeCapacity">{{ wardogsRuntimeCapacity.activeLobbyCount ?? 'Unknown' }} active lobbies · {{ wardogsRuntimeCapacity.activePendingMatchCount ?? 'Unknown' }} pending acceptances · {{ wardogsRuntimeCapacity.capacity ?? 'Unknown' }} reported capacity</small></div>
        </dl>
        <p class="admin-note">Runtime capacity does not guarantee that a specific registry server will pass allocation checks.</p>
        <div class="automation-control">
          <div><h3>Automation mode</h3><p>Control existing server write behavior.</p></div>
          <div class="admin-actions" role="group" aria-label="Automation mode">
            <button v-for="mode in automationModes" :key="mode.id" type="button" class="cmp-button cmp-button--secondary" :aria-pressed="automationMode === mode.id" :disabled="automationLoading || loading || !!error" :title="mode.description" @click="setAutomationMode(mode.id)">{{ mode.label }}</button>
          </div>
        </div>
        <details v-if="queueModeDiagnostics.length" class="cmp-disclosure admin-disclosure"><summary>Queue mode detail <span>{{ queueModeDiagnostics.length }}</span></summary>
          <div v-for="mode in queueModeDiagnostics" :key="mode.id" class="detail-row"><span>{{ mode.label }}</span><strong>{{ queueModeSize(mode) ?? 'Unknown' }} queued</strong><small>{{ formatQueueModeCapacity(mode) }}</small></div>
        </details>
        <details class="cmp-disclosure admin-disclosure"><summary>CMP audit events <span>{{ recentEvents.length }} recent</span></summary>
          <p v-if="!recentEvents.length" class="admin-note">No recent events.</p>
          <div v-for="event in recentEvents" :key="event.id" class="detail-row" :class="{ 'is-warning': isWarningEvent(event.event_type) }"><span>{{ formatEventType(event.event_type) }}</span><strong>{{ isWarningEvent(event.event_type) ? 'Review' : 'Recorded' }} · {{ formatDateTime(event.created_at) }}</strong><small>Lobby {{ event.lobby_id || 'unavailable' }}</small></div>
          <p class="admin-note">{{ historyCounts.lobbyEvents || 0 }} lobby events recorded.</p>
        </details>
      </details>

      <section v-if="wardogsDevVisible" class="admin-section dev-section" aria-label="WARDOGS developer tools">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Local environment</p><h2>Development tools</h2></div><span class="environment-label">Development only</span></div>
        <p class="admin-note">Controls affect local WARDOGS test state. Synthetic players auto-accept; simulated presence is separate from real WDRCON observation.</p>
        <p v-if="wardogsDevLoading && !wardogsDev" role="status" class="cmp-loading-state">Loading test state…</p>
        <p v-if="wardogsDevError" role="alert" class="cmp-error-state">{{ wardogsDevError }} <button class="text-action" type="button" @click="loadWardogsDev">Retry test tools</button><span v-if="wardogsDev">Showing the last successful test state; controls are disabled until it refreshes.</span></p>
        <template v-if="wardogsDevAvailable">
          <dl class="test-state-list">
            <div class="signal-row"><dt>Test queue</dt><dd>{{ wardogsDev.queue?.length || 0 }} queued · {{ wardogsDev.pendingMatch ? 'Acceptance active' : 'No pending acceptance' }}</dd></div>
            <div class="signal-row"><dt>Test match</dt><dd><RouterLink v-if="wardogsDev.lobbyId" :to="`/wardogs/lobby/${wardogsDev.lobbyId}`">{{ wardogsDev.lobbyId }} · Open match</RouterLink><span v-else>None</span></dd></div>
          </dl>
          <div class="admin-action-row"><div><h3>Fill queue</h3><p>Add synthetic players to the local test queue. Your acceptance remains manual.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsDevAction('fill')">Fill test queue</button></div>
          <div v-if="participantGroupStore.inGroup" class="admin-action-row"><div><h3>Seed premade</h3><p>Add synthetic members to your current development group.</p></div><div class="admin-actions"><label for="admin-wardogs-seed-count">Bots</label><input id="admin-wardogs-seed-count" v-model.number="seedCount" class="cmp-input admin-seed-count" type="number" min="1" step="1" inputmode="numeric"><button class="cmp-button cmp-button--secondary" type="button" :disabled="participantGroupStore.loading" @click="seedWardogsGroup">Add members</button></div></div>
          <details v-if="wardogsQueueModes.length" class="cmp-disclosure admin-disclosure"><summary>Queue maintenance</summary><div v-for="mode in wardogsQueueModes" :key="mode.id" class="admin-action-row"><div><h3>{{ mode.label }}</h3><p>{{ mode.size }} waiting · {{ mode.enabled === false ? 'Paused' : 'Enabled' }}</p></div><div class="admin-actions"><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsQueueBusy" @click="manageWardogsQueue(mode, 'clear')">Clear queue</button><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsQueueBusy" @click="manageWardogsQueue(mode, 'toggle')">{{ mode.enabled === false ? 'Enable queue' : 'Disable queue' }}</button></div></div></details>
          <div class="admin-action-row"><div><h3>Presence overlay</h3><p>Switch between simulated presence and real observations for this test match.</p></div><div class="admin-actions"><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsDevAction('simulate', { lobbyId: wardogsDev.lobbyId, enabled: true })">Simulate connected</button><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsDevAction('simulate', { lobbyId: wardogsDev.lobbyId, enabled: false })">Real observations only</button></div></div>
          <div class="admin-action-row"><div><h3>Allocation retry</h3><p>Retry allocation for the current local test lobby.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsLobbyAction('allocate')">Retry allocation</button></div>
          <div class="admin-action-row"><div><h3>Participant preview</h3><p>Change this view while keeping your admin permission.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="authStore.wardogsParticipantPreview = !authStore.wardogsParticipantPreview">{{ authStore.wardogsParticipantPreview ? 'View as admin' : 'View as participant' }}</button></div>
        </template>
      </section>

      <section v-if="diagnostics?.activeLobbies?.length || wardogsDevAvailable" class="admin-section danger-section" aria-label="Reset and cleanup">
        <div class="admin-section-heading"><div><p class="cmp-kicker">Recovery</p><h2>Reset &amp; cleanup</h2></div><span class="danger-label">Destructive actions</span></div>
        <div v-if="wardogsDevAvailable" class="admin-action-row"><div><h3>Reset synthetic state</h3><p>Cancel test acceptance and remove synthetic queue players and presence overlay. Confirmed results remain.</p></div><button class="cmp-button cmp-button--danger" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsDevAction('reset')">Reset test queue / overlay</button></div>
        <div v-if="wardogsDevAvailable && wardogsDev.lobbyId" class="admin-action-row"><div><h3>Delete test lobby</h3><p>Delete this local WARDOGS lobby and release its server allocation. Confirmation is required.</p></div><button class="cmp-button cmp-button--danger" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsLobbyAction('cleanup')">Delete test lobby</button></div>
        <details v-if="activeLobbies.length" class="cmp-disclosure admin-disclosure"><summary>CMP lobby cleanup <span>{{ activeLobbies.length }}</span></summary>
          <div v-for="lobby in activeLobbies" :key="lobby.lobby_id" class="admin-action-row"><div><h3>{{ lobby.lobby_id }}</h3><p>{{ formatLobbyPhase(lobby.step) }} · {{ lobby.players }} players · {{ lobby.selected_map || 'No layer selected' }}</p><small v-if="lobby.announcement">{{ lobby.announcement }}</small><small v-if="lobby.live_roll_done"> · Live roll complete</small><small v-if="lobby.server_details_provided_at"> · Details sent {{ formatDateTime(lobby.server_details_provided_at) }}</small><small v-if="lobby.live_started_at"> · Live started {{ formatDateTime(lobby.live_started_at) }}</small></div><button class="cmp-button cmp-button--danger" type="button" :disabled="loading" @click="deleteActiveLobby(lobby.lobby_id)">Delete lobby</button></div>
        </details>
      </section>
    </template>
  </div>
</template>

<style scoped>
.admin-page { display: grid; gap: var(--cmp-section-gap); max-width: 1180px; }
.admin-header { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-5); margin: 0; }
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
.admin-disclosure summary, .server-details summary { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-3); min-height: 42px; color: var(--cmp-text-secondary); font-size: .875rem; font-weight: 650; cursor: pointer; }
.admin-disclosure summary span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); font-weight: 500; text-align: right; }
.admin-disclosure summary:focus-visible, .server-details summary:focus-visible { outline: 2px solid var(--cmp-focus); outline-offset: 3px; }
.detail-row { display: grid; grid-template-columns: minmax(180px, .8fr) minmax(0, 1.2fr); align-items: baseline; gap: var(--cmp-space-1) var(--cmp-space-5); padding: var(--cmp-space-3) var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.detail-row > span { color: var(--cmp-text-secondary); font-size: .875rem; overflow-wrap: anywhere; }
.detail-row > strong { font-size: .875rem; font-weight: 650; text-align: right; overflow-wrap: anywhere; }
.detail-row small { grid-column: 1 / -1; color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); overflow-wrap: anywhere; }
.detail-row.is-warning > strong { color: var(--cmp-warning); }
.server-row { display: grid; grid-template-columns: minmax(220px, 1.3fr) minmax(145px, .7fr) minmax(170px, 1fr); gap: var(--cmp-space-3) var(--cmp-space-5); align-items: center; padding: var(--cmp-space-3) var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.server-identity, .server-state, .server-assignment { display: grid; gap: var(--cmp-space-1); min-width: 0; }
.server-identity strong { font-size: .9375rem; overflow-wrap: anywhere; }
.server-identity span, .server-state span, .server-state small, .server-assignment > span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); overflow-wrap: anywhere; }
.server-state strong, .server-assignment strong, .server-assignment a { color: var(--cmp-text); font-size: .875rem; font-weight: 650; overflow-wrap: anywhere; }
.server-assignment a { color: var(--cmp-primary-hover); }
.server-details { grid-column: 1 / -1; min-width: 0; padding-top: var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.server-details .detail-row:first-of-type { border-top: 0; }
.admin-note { margin: 0; }
.admin-section > .cmp-error-state, .admin-section > .cmp-loading-state, .admin-section > .cmp-empty-state { display: grid; gap: var(--cmp-space-2); }
.text-action { width: fit-content; min-height: 42px; padding: 0; border: 0; background: none; color: var(--cmp-primary-hover); font: 650 .875rem var(--cmp-font-body); cursor: pointer; text-decoration: underline; text-underline-offset: 2px; }
.text-action:focus-visible { outline: 2px solid var(--cmp-focus); outline-offset: 3px; }
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
.admin-seed-count { width: 82px; }
.danger-section { border-top-color: color-mix(in srgb, var(--cmp-danger) 60%, var(--cmp-border)); }
.danger-label { color: var(--cmp-danger); font-size: var(--cmp-type-meta); font-weight: 650; }
.danger-section .admin-action-row { border-top-color: color-mix(in srgb, var(--cmp-danger) 22%, var(--cmp-border)); }
.admin-mode { padding-top: 0; }
.admin-mode summary { color: var(--cmp-text-secondary); }
.admin-mode summary span { margin-left: var(--cmp-space-3); }
.admin-mode > p { margin: 0 0 var(--cmp-space-3); color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.admin-mode .admin-actions { justify-content: flex-start; padding-bottom: var(--cmp-space-3); }
.operator-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; border-block: 1px solid var(--cmp-border); }
.operator-summary > div { display: grid; gap: var(--cmp-space-1); min-width: 0; padding: var(--cmp-space-3) var(--cmp-space-4); border-right: 1px solid var(--cmp-border); }
.operator-summary > div:last-child { border-right: 0; }
.operator-summary dt, .runtime-summary span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.operator-summary dd { margin: 0; color: var(--cmp-text); font-size: 1rem; font-weight: 700; overflow-wrap: anywhere; }
.operator-summary dd.is-attention { color: var(--cmp-warning); }
.operator-alerts { display: grid; gap: var(--cmp-space-2); }
.operator-alerts > * { margin: 0; }
.runtime-mode { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(110px, .7fr) minmax(140px, .8fr); align-items: center; gap: var(--cmp-space-3); padding: var(--cmp-space-3) var(--cmp-space-2); border-top: 1px solid var(--cmp-border); }
.runtime-mode > div { display: grid; gap: var(--cmp-space-1); min-width: 0; }
.runtime-mode strong { font-size: .9rem; overflow-wrap: anywhere; }
.runtime-mode small, .runtime-mode > span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); overflow-wrap: anywhere; }
.runtime-mode > strong { text-align: right; }
.active-lobby-list { display: grid; }
.active-lobby-row { display: grid; grid-template-columns: minmax(100px, .8fr) minmax(0, 1.4fr) auto; align-items: center; gap: var(--cmp-space-3); min-height: 48px; padding: var(--cmp-space-2); border-top: 1px solid var(--cmp-border); color: var(--cmp-text-secondary); font-size: .875rem; text-decoration: none; }
.active-lobby-row strong { color: var(--cmp-text); }
.active-lobby-row > span:last-child { color: var(--cmp-primary-hover); font-weight: 650; }
.active-lobby-row:hover { background: var(--cmp-surface); }
.active-lobby-row:focus-visible { outline: 2px solid var(--cmp-focus); outline-offset: 3px; }
.system-detail { padding-top: var(--cmp-space-3); border-top: 1px solid var(--cmp-border); }
.system-detail > summary { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-4); min-height: 48px; cursor: pointer; }
.system-detail > summary > span:first-child { display: inline-grid; gap: 2px; }
.system-detail > summary .cmp-kicker { margin: 0; }
.system-detail > summary strong { color: var(--cmp-text); font-size: 1rem; }
.system-detail > summary > span:last-child { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); text-align: right; }
.system-detail > summary:focus-visible { outline: 2px solid var(--cmp-focus); outline-offset: 3px; }
@media (max-width: 900px) {
  .server-row { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .server-details { grid-column: 1 / -1; }
}
@media (max-width: 680px) {
  .admin-header, .automation-control, .admin-action-row { align-items: flex-start; flex-direction: column; }
  .admin-header > button, .admin-action-row > .cmp-button { width: 100%; }
  .admin-actions { justify-content: flex-start; }
  .operator-summary > div { padding-inline: var(--cmp-space-2); }
  .runtime-mode { grid-template-columns: minmax(0, 1fr) auto; }
  .runtime-mode > span { grid-column: 1 / -1; }
  .active-lobby-row { grid-template-columns: minmax(0, 1fr) auto; }
  .active-lobby-row strong { grid-column: 1; }
  .active-lobby-row > span:last-child { grid-column: 2; grid-row: 1 / span 2; }
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
  .operator-summary { grid-template-columns: 1fr; }
  .operator-summary > div { grid-template-columns: minmax(100px, .7fr) minmax(0, 1fr); align-items: baseline; gap: var(--cmp-space-3); border-right: 0; border-bottom: 1px solid var(--cmp-border); }
  .operator-summary > div:last-child { border-bottom: 0; }
  .operator-summary dd { text-align: right; font-size: .9375rem; }
  .runtime-mode { grid-template-columns: minmax(0, 1fr); }
  .runtime-mode > strong { text-align: left; }
  .active-lobby-row { grid-template-columns: minmax(0, 1fr); gap: var(--cmp-space-1); }
  .active-lobby-row strong, .active-lobby-row > span:last-child { grid-column: auto; grid-row: auto; }
  .system-detail > summary { align-items: flex-start; flex-direction: column; gap: var(--cmp-space-2); }
  .system-detail > summary > span:last-child { text-align: left; }
}
</style>
