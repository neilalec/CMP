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
const wardogsAvailableServers = computed(() => wardogsServers.value.filter((server) =>
  server.enabled && ['healthy', 'degraded', 'approved'].includes(server.status) && !server.current_lobby_id));
const otherServers = computed(() => servers.value.filter((server) => server.game_type !== 'wardogs'));
const wardogsQueueModes = computed(() => queueModeDiagnostics.value.filter((mode) => mode.gameType === 'wardogs'));

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
  <main class="admin-page cmp-page">
    <header class="admin-topline">
      <div><h1>Admin</h1><p>System status and match operations</p></div>
      <button v-if="isAdmin" class="cmp-button cmp-button--secondary" type="button" :disabled="loading || serverLoading" @click="loadDiagnostics(); loadServers()">
        {{ loading || serverLoading ? 'Refreshing…' : 'Refresh status' }}
      </button>
    </header>

    <section v-if="canAccessAdminPage && authStore.canToggleAdmin" class="admin-section admin-mode" aria-label="Admin privileges">
      <div class="section-head"><h2>Admin privileges</h2><span>{{ authStore.isAdmin ? 'Admin mode' : 'Regular user test' }}</span></div>
      <div class="admin-inline">
        <p>{{ authStore.isAdmin ? 'CMP lobby and team enforcement bypasses apply.' : 'Lobby membership and assigned team are enforced.' }}</p>
        <div class="admin-actions">
          <button class="cmp-button cmp-button--secondary" type="button" :disabled="adminModeLoading || authStore.isAdmin" @click="setSelfAdminMode(true)">Admin On</button>
          <button class="cmp-button cmp-button--secondary" type="button" :disabled="adminModeLoading || !authStore.isAdmin" @click="setSelfAdminMode(false)">Test Regular</button>
        </div>
      </div>
    </section>

    <template v-if="isAdmin">
      <section class="admin-section" aria-label="System and integration">
        <div class="section-head"><h2>System &amp; integration</h2><span v-if="diagnostics">Updated {{ formatDateTime(diagnostics.generatedAt) }}</span></div>
        <p v-if="loading && !diagnostics" role="status" class="admin-note">Loading diagnostics…</p>
        <p v-if="error" role="alert" class="admin-error">{{ error }} <button type="button" class="text-action" @click="loadDiagnostics">Retry diagnostics</button></p>
        <template v-if="diagnostics">
          <div class="status-list">
            <div class="status-row"><span>Backend database</span><strong :class="diagnostics.database?.ok === false ? 'state-bad' : 'state-good'">{{ diagnostics.database?.ok === true ? 'Healthy' : diagnostics.database?.ok === false ? 'Needs attention' : 'Unknown' }}</strong></div>
            <div class="status-row"><span>WARDOGS servers</span><strong>{{ serversLoaded ? `${wardogsAvailableServers.length} available · ${wardogsServers.length} registered` : 'Unknown' }}</strong><small v-if="serversLoaded && !wardogsAvailableServers.length">No eligible server for allocation</small></div>
            <div class="status-row"><span>WARDOGS queue</span><strong>{{ wardogsQueueModes.reduce((total, mode) => total + mode.size, 0) }} waiting</strong></div>
            <div v-if="diagnostics.bridge?.enabled !== false" class="status-row"><span>CMP bridge</span><strong :class="diagnostics.bridge?.ok ? 'state-good' : 'state-bad'">{{ diagnostics.bridge?.ok ? 'Healthy' : 'Degraded' }}</strong></div>
            <div class="status-row"><span>EOS setup</span><strong>{{ diagnostics.eos?.configured ? 'Configured' : 'Not configured' }}</strong></div>
          </div>
          <p class="admin-note">WARDOGS observation freshness is shown in each match room. Server probe status is listed below.</p>
          <div class="admin-inline automation-row">
            <div><h3>Automation mode</h3><p>RCON writes {{ diagnostics.automation?.rconWritesEnabled ? 'enabled' : 'blocked' }}. Current mode: {{ automationMode }}.</p></div>
            <div class="admin-actions" role="group" aria-label="Automation mode">
              <button v-for="mode in automationModes" :key="mode.id" type="button" class="cmp-button cmp-button--secondary" :class="{ selected: automationMode === mode.id }" :disabled="automationLoading" :title="mode.description" @click="setAutomationMode(mode.id)">{{ mode.label }}</button>
            </div>
          </div>
          <details v-if="queueModeDiagnostics.length" class="admin-disclosure">
            <summary>Queue modes <span>{{ queueModeDiagnostics.length }}</span></summary>
            <div v-for="mode in queueModeDiagnostics" :key="mode.id" class="status-row"><span>{{ mode.label }}</span><strong>{{ mode.size }} queued</strong><small>{{ formatQueueModeCapacity(mode) }}</small></div>
          </details>
          <details class="admin-disclosure">
            <summary>Recent events <span>{{ recentEvents.length }} shown</span></summary>
            <p v-if="!recentEvents.length" class="admin-note">No recent events.</p>
            <div v-for="event in recentEvents" :key="event.id" class="status-row" :class="{ 'state-bad': isWarningEvent(event.event_type) }"><span>{{ formatEventType(event.event_type) }}</span><strong>{{ formatDateTime(event.created_at) }}</strong><small>Lobby {{ event.lobby_id || 'unavailable' }}</small></div>
            <p class="admin-note">{{ historyCounts.lobbyEvents || 0 }} lobby events recorded.</p>
          </details>
        </template>
      </section>

      <section class="admin-section" aria-label="WARDOGS servers">
        <div class="section-head"><h2>WARDOGS servers</h2><span>{{ wardogsServers.length }} registered</span></div>
        <p v-if="serverLoading && !servers.length" role="status" class="admin-note">Loading servers…</p>
        <p v-if="serverError" role="alert" class="admin-error">{{ serverError }} <button type="button" class="text-action" @click="loadServers">Retry servers</button></p>
        <p v-if="!serverLoading && !serverError && !wardogsServers.length" class="admin-note">No WARDOGS servers are registered.</p>
        <div v-for="server in wardogsServers" :key="server.id" class="server-row">
          <div class="server-name"><strong>{{ server.display_name || server.slug || `Server ${server.id}` }}</strong><small>{{ server.current_lobby_id ? `Assigned to ${server.current_lobby_id}` : 'No current match' }}</small></div>
          <div class="server-state"><span>{{ server.approved_by ? 'Approved' : 'Awaiting approval' }}</span><strong>{{ server.enabled ? 'Enabled' : 'Disabled' }} · {{ server.status || 'Unknown' }}</strong></div>
          <div class="server-state"><span>Last probe</span><strong>{{ server.last_health_status || 'Not checked' }}</strong><small>{{ formatDateTime(server.last_health_check_at) }}</small></div>
          <RouterLink v-if="server.current_lobby_id" class="text-action" :to="`/wardogs/lobby/${server.current_lobby_id}`">Open match</RouterLink>
          <details class="server-details"><summary>Server details</summary>
            <div class="status-row"><span>Allocation</span><strong>{{ server.current_lobby_id ? 'Reserved' : server.enabled && ['healthy', 'degraded', 'approved'].includes(server.status) ? 'Eligible' : 'Unavailable' }}</strong></div>
            <div v-if="server.last_health_error" class="status-row"><span>Probe issue</span><strong>{{ server.last_health_error }}</strong></div>
            <div v-if="getServerDiscovery(server)" class="status-row"><span>Discovery</span><strong>{{ formatLookupStep(getServerDiscovery(server)?.a2s) }}</strong></div>
            <div v-if="getEosDiscovery(server)" class="status-row"><span>EOS session</span><strong>{{ formatEosDiscovery(getEosDiscovery(server)) }}</strong></div>
            <div v-if="getLiveSession(server)" class="status-row"><span>Live session</span><strong>{{ formatLiveSession(getLiveSession(server)) }}</strong></div>
            <div v-if="getServerJoinStrategy(server)" class="status-row"><span>Join method</span><strong>{{ formatJoinStrategy(getServerJoinStrategy(server)) }}</strong></div>
          </details>
        </div>
        <p class="admin-note">Server pool writes remain disabled. Match allocation retry is available only in the local test workflow below.</p>
        <details v-if="otherServers.length" class="admin-disclosure"><summary>Other registered servers <span>{{ otherServers.length }}</span></summary>
          <details v-for="server in otherServers" :key="server.id" class="admin-disclosure"><summary>{{ server.display_name }} · {{ server.status }}</summary>
            <div class="status-row"><span>Registry</span><strong>{{ server.approved_by ? 'Approved' : 'Awaiting approval' }} · {{ server.enabled ? 'Enabled' : 'Disabled' }}</strong></div>
            <div class="status-row"><span>Last probe</span><strong>{{ server.last_health_status || 'Not checked' }}</strong><small>{{ formatDateTime(server.last_health_check_at) }}</small></div>
            <div class="status-row"><span>Allocation</span><strong>{{ server.current_lobby_id || 'No current match' }}</strong></div>
            <div v-if="server.last_health_error" class="status-row"><span>Probe issue</span><strong>{{ server.last_health_error }}</strong></div>
          </details>
        </details>
      </section>

      <section v-if="wardogsDevVisible" class="admin-section dev-section" aria-label="WARDOGS developer tools">
        <div class="section-head"><h2>Local test tools</h2><span>Development mode only</span></div>
        <p class="admin-note">Synthetic queue and presence controls for local WARDOGS testing. Join from Play first; synthetic players auto-accept.</p>
        <p v-if="wardogsDevLoading && !wardogsDev" role="status" class="admin-note">Loading test state…</p>
        <p v-if="wardogsDevError" role="alert" class="admin-error">{{ wardogsDevError }} <button class="text-action" type="button" @click="loadWardogsDev">Retry test tools</button></p>
        <template v-if="wardogsDevAvailable">
          <div class="status-list">
            <div class="status-row"><span>Test queue</span><strong>{{ wardogsDev.queue?.length || 0 }} queued</strong><small>{{ wardogsDev.pendingMatch ? 'Match acceptance active' : 'No pending acceptance' }}</small></div>
            <div class="status-row"><span>Your test match</span><strong>{{ wardogsDev.lobbyId || 'None' }}</strong><RouterLink v-if="wardogsDev.lobbyId" class="text-action" :to="`/wardogs/lobby/${wardogsDev.lobbyId}`">Open match</RouterLink></div>
          </div>
          <p v-if="wardogsDevError && wardogsDev" class="admin-note">Showing the last successful test state. Actions are disabled until refresh succeeds.</p>
          <div class="admin-action-row"><div><h3>Fill missing slots</h3><p>Add synthetic queue players. Your own acceptance remains manual.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsDevAction('fill')">Fill test queue</button></div>
          <div class="admin-action-row"><div><h3>Connected overlay</h3><p>Simulated presence is local test state; real WDRCON observation remains separate.</p></div><div class="admin-actions"><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsDevAction('simulate', { lobbyId: wardogsDev.lobbyId, enabled: true })">Simulate connected</button><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsDevAction('simulate', { lobbyId: wardogsDev.lobbyId, enabled: false })">Real observations only</button></div></div>
          <div class="admin-action-row"><div><h3>Test match allocation</h3><p>Retry allocation for your current test lobby.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError || !wardogsDev.lobbyId" @click="wardogsLobbyAction('allocate')">Retry allocation</button></div>
          <div class="admin-action-row"><div><h3>Participant preview</h3><p>Only changes this view; your admin permission remains active.</p></div><button class="cmp-button cmp-button--secondary" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="authStore.wardogsParticipantPreview = !authStore.wardogsParticipantPreview">{{ authStore.wardogsParticipantPreview ? 'View as admin' : 'View as participant' }}</button></div>
          <p class="admin-note">Referee confirmation and correction stay with the result in the match room.</p>
        </template>
      </section>

      <section v-if="diagnostics?.activeLobbies?.length || wardogsDevAvailable" class="admin-section danger-section" aria-label="Reset and cleanup">
        <div class="section-head"><h2>Reset &amp; cleanup</h2><span>Destructive actions</span></div>
        <div v-if="wardogsDevAvailable" class="admin-action-row"><div><h3>Reset synthetic state</h3><p>Cancel WARDOGS test acceptance and remove synthetic queued players and presence overlay. Confirmed results remain.</p></div><button class="cmp-button cmp-button--danger" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsDevAction('reset')">Reset test queue / overlay</button></div>
        <div v-if="wardogsDevAvailable && wardogsDev.lobbyId" class="admin-action-row"><div><h3>Delete test lobby</h3><p>Remove this WARDOGS lobby and release its server allocation.</p></div><button class="cmp-button cmp-button--danger" type="button" :disabled="wardogsDevBusy || !!wardogsDevError" @click="wardogsLobbyAction('cleanup')">Delete test lobby</button></div>
        <details v-if="activeLobbies.length" class="admin-disclosure"><summary>Legacy active lobby cleanup <span>{{ activeLobbies.length }}</span></summary>
          <div v-for="lobby in activeLobbies" :key="lobby.lobby_id" class="admin-action-row"><div><h3>{{ lobby.lobby_id }}</h3><p>{{ formatLobbyPhase(lobby.step) }} · {{ lobby.players }} players · {{ lobby.selected_map || 'No layer selected' }}</p><small v-if="lobby.announcement">{{ lobby.announcement }}</small><small v-if="lobby.live_roll_done"> · Live roll complete</small><small v-if="lobby.server_details_provided_at"> · Details sent {{ formatDateTime(lobby.server_details_provided_at) }}</small><small v-if="lobby.live_started_at"> · Live started {{ formatDateTime(lobby.live_started_at) }}</small></div><button class="cmp-button cmp-button--danger" type="button" :disabled="loading" @click="deleteActiveLobby(lobby.lobby_id)">Delete lobby</button></div>
        </details>
      </section>
    </template>
  </main>
</template>

<style scoped>
.admin-page { width: min(100%, 1040px); margin: 0 auto; padding: clamp(20px, 3vw, 32px) var(--cmp-page-gutter) 48px; display: grid; gap: 22px; }
.admin-topline, .section-head, .admin-inline, .admin-action-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; }
.admin-topline h1 { margin: 0; font: 800 clamp(1.55rem, 3vw, 2rem) var(--cmp-font-display); }
.admin-topline p, .admin-inline p, .admin-action-row p, .admin-note { margin: 3px 0 0; color: var(--cmp-text-muted); font-size: .82rem; }
.admin-section { min-width: 0; border-top: 1px solid var(--cmp-border); padding-top: 13px; }
.section-head { margin-bottom: 11px; align-items: baseline; }
.section-head h2 { margin: 0; font: 800 1rem var(--cmp-font-display); }
.section-head span { color: var(--cmp-text-muted); font: 700 .7rem var(--cmp-font-mono); }
.admin-section h3 { margin: 0; font-size: .85rem; }
.status-list { border: 1px solid var(--cmp-border); background: var(--cmp-surface); }
.status-row { display: grid; grid-template-columns: minmax(160px, 1fr) auto; align-items: baseline; gap: 5px 18px; padding: 9px 12px; border-bottom: 1px solid var(--cmp-border); font-size: .82rem; }
.status-row:last-child { border-bottom: 0; }.status-row strong { font-weight: 700; text-align: right; }.status-row small { grid-column: 1 / -1; color: var(--cmp-text-muted); }
.state-good { color: var(--cmp-success); }.state-bad { color: var(--cmp-danger); }
.automation-row { margin-top: 12px; padding: 11px 0; border-top: 1px solid var(--cmp-border); }
.admin-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: 6px; }
.admin-page .cmp-button { min-height: 34px; padding: 6px 10px; font-size: .76rem; white-space: nowrap; }
.admin-page .selected { border-color: var(--cmp-primary-hover); color: var(--cmp-text); }
.admin-disclosure { border-top: 1px solid var(--cmp-border); padding: 9px 0; }.admin-disclosure summary, .server-details summary { cursor: pointer; color: var(--cmp-text-secondary); font-size: .8rem; font-weight: 700; }.admin-disclosure summary span { float: right; color: var(--cmp-text-muted); }
.admin-disclosure .status-row { margin-top: 6px; border: 1px solid var(--cmp-border); background: var(--cmp-surface); }
.server-row { display: grid; grid-template-columns: minmax(180px, 1.4fr) minmax(120px, .9fr) minmax(120px, .9fr) auto; align-items: center; gap: 10px 16px; padding: 11px 13px; margin-bottom: 6px; border: 1px solid var(--cmp-border); background: var(--cmp-surface); font-size: .8rem; }
.server-name, .server-state { display: grid; gap: 3px; min-width: 0; }.server-name strong { font-size: .86rem; }.server-name small, .server-state span, .server-state small { color: var(--cmp-text-muted); font-size: .7rem; overflow-wrap: anywhere; }.server-details { grid-column: 1 / -1; }.server-details .status-row { padding: 7px 0; }
.admin-action-row { padding: 11px 0; border-top: 1px solid var(--cmp-border); }.admin-action-row:first-of-type { border-top: 0; }.admin-action-row > div:first-child { min-width: 0; }
.dev-section { border-top-color: var(--cmp-primary); }.danger-section { border-top-color: var(--cmp-danger); }.danger-section .section-head span { color: var(--cmp-danger); }
.admin-error { margin: 8px 0; color: var(--cmp-danger); font-size: .82rem; }.text-action { padding: 0; border: 0; background: none; color: var(--cmp-primary-hover); font: 700 .8rem var(--cmp-font-body); cursor: pointer; text-decoration: underline; }.admin-note { margin: 9px 0; }
@media (max-width: 680px) { .admin-topline, .admin-inline, .admin-action-row { align-items: flex-start; flex-direction: column; }.admin-actions { justify-content: flex-start; }.server-row { grid-template-columns: 1fr 1fr; }.server-name, .server-details { grid-column: 1 / -1; }.status-row { grid-template-columns: minmax(100px, 1fr) auto; } }
@media (max-width: 420px) { .server-row { grid-template-columns: 1fr; }.server-name, .server-details { grid-column: auto; }.status-row strong { overflow-wrap: anywhere; } }
</style>
