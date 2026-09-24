<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../stores/authStore';
import { useRootStore } from '../stores/rootStore';
import { useSocketStore } from '../stores/socketStore';
import { API_BASE_URL } from '../config';
import { SOCKET_EVENTS } from '../constants/socketEvents';
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
const availableServers = ref([]);
const loading = ref(false);
const serverLoading = ref(false);
const error = ref('');
const healthResults = ref({});
const automationLoading = ref(false);
const adminModeLoading = ref(false);

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

const formatJson = (value) => JSON.stringify(value ?? null, null, 2);
const isAdmin = computed(() => !!authStore.token && !!authStore.isAdmin);
const canAccessAdminPage = computed(() => !!authStore.token && (authStore.isAdmin || authStore.canToggleAdmin));
const getNetworkIdentity = (value) => value?.metadata?.networkIdentity || value?.networkIdentity || null;
const getSessionDiscovery = (value) => value?.metadata?.sessionDiscovery || value?.sessionDiscovery || null;
const getEosDiscovery = (value) => value?.metadata?.eosDiscovery || value?.eosDiscovery || null;
const getServerResultPayload = (server) => healthResults.value?.[server?.id] || server?.metadata || null;
const getExternalServerKey = (value) => {
  const identity = getNetworkIdentity(value);
  if (!identity) return '';
  return identity.externalKey || '';
};
const getIdentitySummary = (value) => {
  const identity = getNetworkIdentity(value);
  if (!identity) return '';
  if (identity.host && identity.queryPort) return `${identity.host}:${identity.queryPort}`;
  return identity.host || '';
};
const formatSessionDiscovery = (value) => {
  if (!value || !value.attempted) return 'Not attempted';
  if (value.matched && value.targetServerId) return value.targetServerId;
  return 'No session identifier found';
};
const formatEosDiscovery = (value) => {
  if (!value) return 'Not attempted';
  if (!value.configured) return 'Not configured';
  if (!value.attempted) return 'Not attempted';
  if (value.error) return value.error;
  if (value.matched && value.targetServerId) return value.targetServerId;
  return 'No EOS session match';
};
const formatClientLogDiscovery = (value) => {
  if (!value) return 'Not attempted';
  if (!value.configured) return 'No Squad log path';
  if (!value.attempted) return 'Not attempted';
  if (value.error) return value.error;
  if (value.matched && value.targetServerId) return value.targetServerId;
  return 'No local log match';
};
const getLiveSession = (value) => value?.metadata?.liveSession || value?.liveSession || null;
const formatDateTime = (value) => {
  const numeric = Number(value);
  if (!numeric) return '';
  return new Date(numeric * 1000).toLocaleString();
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
const formatBooleanStatus = (value) => (value ? 'Yes' : 'No');
const formatEventType = (value) => String(value || 'event').replaceAll('_', ' ');
const isWarningEvent = (value) => /failed|error|unauthorized|skipped|blocked|timeout|warning/i.test(String(value || ''));
const formatLiveSession = (value) => {
  if (!value || !value.matched || !value.targetServerId) return 'No verified live session';
  return value.targetServerId;
};
const formatLiveSessionMeta = (value) => {
  if (!value || !value.matched) return '';
  const parts = [];
  if (value.source) parts.push(value.source.replaceAll('_', ' '));
  if (value.fresh === false) parts.push('stale');
  return parts.join(' | ');
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
  try {
    const payload = await apiFetch('/admin/servers');
    servers.value = payload.servers || [];
    availableServers.value = payload.available || [];
  } catch (err) {
    rootStore.setError(err.message || 'Failed to load servers');
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
    } else {
      diagnostics.value = null;
      servers.value = [];
      availableServers.value = [];
    }
  } catch (err) {
    rootStore.setError(err.message || 'Failed to update admin test mode');
  } finally {
    adminModeLoading.value = false;
  }
};

const runHealthCheck = async (serverId) => {
  serverLoading.value = true;
  try {
    const payload = await apiFetch(`/admin/servers/${serverId}/health-check`, { method: 'POST' });
    healthResults.value = {
      ...healthResults.value,
      [serverId]: payload.result || null
    };
    await loadServers();
    await loadDiagnostics();
  } catch (err) {
    rootStore.setError(err.message || 'Health check failed');
  } finally {
    serverLoading.value = false;
  }
};

const setServerEnabled = async (serverId, enabled) => {
  serverLoading.value = true;
  try {
    await apiFetch(`/admin/servers/${serverId}/${enabled ? 'enable' : 'disable'}`, { method: 'POST' });
    await loadServers();
    await loadDiagnostics();
  } catch (err) {
    rootStore.setError(err.message || 'Failed to update server');
  } finally {
    serverLoading.value = false;
  }
};

const approveServer = async (serverId) => {
  serverLoading.value = true;
  try {
    await apiFetch(`/admin/servers/${serverId}/approve`, { method: 'POST' });
    await loadServers();
    await loadDiagnostics();
  } catch (err) {
    rootStore.setError(err.message || 'Failed to approve server');
  } finally {
    serverLoading.value = false;
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
  await loadDiagnostics();
  await loadServers();
});
</script>

<template>
  <div class="admin-page content-panel page-shell">
    <section class="admin-panel window-panel">
      <div class="window-titlebar">
        <span class="window-titlebar-label">Admin</span>
        <span class="window-titlebar-meta">{{ loading || serverLoading ? 'Syncing' : 'Diagnostics' }}</span>
      </div>
      <div class="panel-body">
        <div class="admin-toolbar">
          <div>
            <p class="eyebrow">Diagnostics</p>
            <strong class="admin-heading">System overview and server control.</strong>
          </div>
          <button type="button" @click="loadDiagnostics(); loadServers()" :disabled="loading || serverLoading">
            {{ loading || serverLoading ? 'Refreshing...' : 'Refresh' }}
          </button>
        </div>

        <p v-if="error" class="admin-error">{{ error }}</p>

        <section v-if="canAccessAdminPage" class="automation-section">
          <div>
            <p class="eyebrow">Testing</p>
            <strong class="admin-heading">Admin privileges</strong>
            <p class="automation-summary">
              {{
                authStore.isAdmin
                  ? 'Admin mode is on. CMP lobby and team enforcement bypasses apply.'
                  : 'Testing as a regular user. CMP will enforce lobby membership and assigned team.'
              }}
            </p>
          </div>
          <div class="automation-controls" role="group" aria-label="Admin privileges">
            <button
              type="button"
              class="automation-mode-button"
              :class="{ 'is-selected-control': authStore.isAdmin }"
              :disabled="adminModeLoading || authStore.isAdmin"
              @click="setSelfAdminMode(true)"
            >
              Admin On
            </button>
            <button
              type="button"
              class="automation-mode-button"
              :class="{ 'is-selected-control': !authStore.isAdmin }"
              :disabled="adminModeLoading || !authStore.isAdmin"
              @click="setSelfAdminMode(false)"
            >
              Test Regular
            </button>
          </div>
        </section>

        <section v-if="diagnostics" class="automation-section">
          <div>
            <p class="eyebrow">Live Safety</p>
            <strong class="admin-heading">Automation mode</strong>
            <p class="automation-summary">
              Admin mode bypasses CMP lobby and team enforcement. RCON writes are
              {{ diagnostics.automation?.rconWritesEnabled ? 'enabled' : 'blocked' }}.
            </p>
          </div>
          <div class="automation-controls" role="group" aria-label="Automation mode">
            <button
              v-for="mode in automationModes"
              :key="mode.id"
              type="button"
              class="automation-mode-button"
              :class="{ 'is-selected-control': automationMode === mode.id }"
              :disabled="automationLoading"
              :title="mode.description"
              @click="setAutomationMode(mode.id)"
            >
              {{ mode.label }}
            </button>
          </div>
        </section>

        <div v-if="diagnostics" class="diagnostics-grid">
          <article class="diagnostic-card data-card">
            <span class="data-card-label">Queue</span>
            <strong>{{ diagnostics.queueSize }}</strong>
            <p>{{ diagnostics.pendingMatch ? diagnostics.pendingMatch.label : 'Idle' }}</p>
          </article>

          <article class="diagnostic-card data-card">
            <span class="data-card-label">Bridge</span>
            <strong>{{ diagnostics.bridge?.ok ? 'Healthy' : 'Degraded' }}</strong>
            <p>{{ diagnostics.bridge?.url }}</p>
          </article>

          <article class="diagnostic-card data-card">
            <span class="data-card-label">Automation</span>
            <strong>{{ automationMode }}</strong>
            <p>{{ diagnostics.automation?.rconWritesEnabled ? 'RCON writes enabled' : 'RCON writes blocked' }}</p>
          </article>

          <article class="diagnostic-card data-card">
            <span class="data-card-label">EOS</span>
            <strong>{{ diagnostics.eos?.configured ? 'Configured' : 'Missing Token' }}</strong>
            <p>{{ diagnostics.eos?.deploymentId || 'No deployment' }}</p>
            <p>
              {{
                diagnostics.eos?.steamSessionTicketConfigured
                  ? 'Steam ticket present'
                  : diagnostics.eos?.clientIdConfigured || diagnostics.eos?.clientSecretConfigured
                    ? 'Exchange partially configured'
                    : 'No exchange inputs'
              }}
            </p>
          </article>

          <article class="diagnostic-card data-card">
            <span class="data-card-label">Verified Server</span>
            <strong>{{ getExternalServerKey(diagnostics.server) || 'Unavailable' }}</strong>
            <p>{{ diagnostics.server?.serverName || diagnostics.server?.bridge?.serverName || 'Run a health check' }}</p>
          </article>

          <article class="diagnostic-card data-card">
            <span class="data-card-label">Servers</span>
            <strong>{{ servers.length }}</strong>
            <p>{{ availableServers.length }} available</p>
          </article>
        </div>

        <section v-if="diagnostics" class="admin-section">
          <div class="window-titlebar compact-titlebar">
            <span class="window-titlebar-label">Active Lobbies</span>
            <span class="window-titlebar-meta">{{ activeLobbies.length }}</span>
          </div>
          <div class="admin-list section-body">
            <p v-if="!activeLobbies.length" class="empty-state">No active lobbies</p>
            <article v-for="lobby in activeLobbies" :key="lobby.lobby_id" class="admin-list-item data-card">
              <div class="data-row">
                <span>{{ lobby.lobby_id }}</span>
                <strong>{{ formatLobbyPhase(lobby.step) }}</strong>
              </div>
              <div class="data-row">
                <span>Players</span>
                <strong>{{ lobby.players }}</strong>
              </div>
              <div class="data-row">
                <span>Selected layer</span>
                <strong>{{ lobby.selected_map || 'None' }}</strong>
              </div>
              <div class="data-row">
                <span>Live roll complete</span>
                <strong>{{ formatBooleanStatus(lobby.live_roll_done) }}</strong>
              </div>
              <div class="data-row" v-if="lobby.announcement">
                <span>Announcement</span>
                <strong>{{ lobby.announcement }}</strong>
              </div>
              <div class="data-row" v-if="lobby.server_details_provided_at">
                <span>Server details sent</span>
                <strong>{{ formatDateTime(lobby.server_details_provided_at) }}</strong>
              </div>
              <div class="data-row" v-if="lobby.live_started_at">
                <span>Live started</span>
                <strong>{{ formatDateTime(lobby.live_started_at) }}</strong>
              </div>
              <div class="server-actions">
                <button
                  type="button"
                  class="delete-button"
                  :disabled="loading"
                  @click="deleteActiveLobby(lobby.lobby_id)"
                >
                  Delete Lobby
                </button>
              </div>
            </article>
          </div>
        </section>

        <section v-if="diagnostics" class="admin-section">
          <div class="window-titlebar compact-titlebar">
            <span class="window-titlebar-label">Recent Events</span>
            <span class="window-titlebar-meta">{{ historyCounts.lobbyEvents || 0 }} total</span>
          </div>
          <div class="admin-list section-body">
            <p v-if="!recentEvents.length" class="empty-state">No recent events</p>
            <article
              v-for="event in recentEvents"
              :key="event.id"
              class="admin-list-item data-card event-card"
              :class="{ 'is-warning-event': isWarningEvent(event.event_type) }"
            >
              <div class="data-row">
                <span class="event-type">{{ formatEventType(event.event_type) }}</span>
                <strong>{{ formatDateTime(event.created_at) }}</strong>
              </div>
              <div class="data-row">
                <span>Lobby</span>
                <strong>{{ event.lobby_id }}</strong>
              </div>
              <details v-if="event.payload" class="payload-details">
                <summary>Payload</summary>
                <pre class="payload-panel">{{ formatJson(event.payload) }}</pre>
              </details>
            </article>
          </div>
        </section>

        <section class="admin-section disabled-section" aria-disabled="true">
          <div class="window-titlebar compact-titlebar">
            <span class="window-titlebar-label">Server Pool</span>
            <span class="window-titlebar-meta">Disabled</span>
          </div>
          <div class="admin-list section-body">
            <p class="disabled-note">Pool management is disabled for now. The current production server remains configured.</p>
            <article v-for="server in servers" :key="server.id" class="admin-list-item data-card">
              <div class="data-row">
                <span>{{ server.display_name }}</span>
                <strong>{{ server.status }}</strong>
              </div>
              <div class="data-row">
                <span>{{ server.bridge_url }}</span>
                <strong>{{ server.enabled ? 'Enabled' : 'Disabled' }}</strong>
              </div>
              <div class="data-row">
                <span>{{ server.steam_lobby_id || 'No Steam lobby ID' }}</span>
                <strong>{{ server.connect_address || 'No connect address' }}</strong>
              </div>
              <div class="data-row">
                <span>{{ getExternalServerKey(server) || getIdentitySummary(server) || 'No verified external key' }}</span>
                <strong>{{ server.bridge_token_masked || 'No token' }}</strong>
              </div>
              <div class="data-row" v-if="getIdentitySummary(server)">
                <span>Bridge identity</span>
                <strong>{{ getIdentitySummary(server) }}</strong>
              </div>
              <div class="data-row">
                <span>Submitted by {{ server.submitted_by || 'unknown' }}</span>
                <strong>{{ server.approved_by ? `Approved by ${server.approved_by}` : 'Awaiting approval' }}</strong>
              </div>
              <div v-if="getServerDiscovery(server)" class="discovery-panel">
                <div class="data-row">
                  <span>Bridge lookup</span>
                  <strong>{{ formatLookupStep(getServerDiscovery(server)?.bridge) }}</strong>
                </div>
                <div class="data-row">
                  <span>A2S lookup</span>
                  <strong>{{ formatLookupStep(getServerDiscovery(server)?.a2s) }}</strong>
                </div>
                <div class="data-row">
                  <span>Steam web lookup</span>
                  <strong>{{ formatLookupStep(getServerDiscovery(server)?.steamWebApi, 'No Steam Web API match') }}</strong>
                </div>
                <div class="data-row" v-if="getSessionDiscovery(server)">
                  <span>Session lookup</span>
                  <strong>{{ formatSessionDiscovery(getSessionDiscovery(server)) }}</strong>
                </div>
                <div class="data-row" v-if="getEosDiscovery(server)">
                  <span>EOS matchmaking</span>
                  <strong>{{ formatEosDiscovery(getEosDiscovery(server)) }}</strong>
                </div>
                <div class="data-row" v-if="getEosDiscovery(server)?.clientLog">
                  <span>Client log session</span>
                  <strong>{{ formatClientLogDiscovery(getEosDiscovery(server)?.clientLog) }}</strong>
                </div>
                <div class="data-row" v-if="getLiveSession(server)">
                  <span>Live session</span>
                  <strong>{{ formatLiveSession(getLiveSession(server)) }}</strong>
                </div>
                <div class="data-row" v-if="getLiveSession(server)?.matched && getLiveSession(server)?.lastSeenAt">
                  <span>Last verified</span>
                  <strong>{{ formatDateTime(getLiveSession(server)?.lastSeenAt) }}</strong>
                </div>
                <div class="data-row" v-if="formatLiveSessionMeta(getLiveSession(server))">
                  <span>Verification</span>
                  <strong>{{ formatLiveSessionMeta(getLiveSession(server)) }}</strong>
                </div>
                <div class="data-row">
                  <span>Join method</span>
                  <strong>{{ formatJoinStrategy(getServerJoinStrategy(server)) }}</strong>
                </div>
                <div class="data-row" v-if="getServerJoinStrategy(server)?.target">
                  <span>Join target</span>
                  <strong>{{ getServerJoinStrategy(server)?.target }}</strong>
                </div>
                <div class="data-row" v-if="getServerResultPayload(server)?.serverInfo?.rawServerInfoKeyCount">
                  <span>Raw info keys</span>
                  <strong>{{ getServerResultPayload(server)?.serverInfo?.rawServerInfoKeyCount }}</strong>
                </div>
              </div>
              <pre v-if="getServerResultPayload(server)" class="payload-panel">{{ formatJson(getServerResultPayload(server)) }}</pre>
              <p v-if="server.last_health_error">{{ server.last_health_error }}</p>
              <div class="server-actions">
                <button type="button" @click="runHealthCheck(server.id)" disabled>Health Check / Re-test</button>
                <button
                  v-if="server.status === 'pending'"
                  type="button"
                  @click="approveServer(server.id)"
                  disabled
                >
                  Approve
                </button>
                <button
                  type="button"
                  @click="setServerEnabled(server.id, !server.enabled)"
                  disabled
                >
                  {{ server.enabled ? 'Disable' : 'Enable' }}
                </button>
              </div>
            </article>
          </div>
        </section>
      </div>
    </section>
  </div>
</template>

<style scoped>
.admin-page {
  width: min(100%, var(--page-width));
}

.admin-panel {
  overflow: hidden;
}

.admin-heading {
  display: block;
  font-family: var(--font-display);
  font-size: 1rem;
  line-height: 1.2;
}

.admin-toolbar,
.server-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.admin-toolbar {
  margin-bottom: 12px;
}

.diagnostics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 10px;
}

.automation-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--surface-border);
  background: color-mix(in srgb, var(--panel-bg) 92%, var(--accent) 8%);
}

.automation-summary,
.disabled-note {
  margin: 4px 0 0;
  color: var(--text-muted);
}

.automation-controls {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 6px;
  min-width: min(100%, 360px);
}

.automation-mode-button {
  min-height: 36px;
  padding: 0 10px;
}

.admin-section {
  margin-top: 14px;
  border: 1px solid var(--surface-border);
  background: var(--panel-bg);
}

.disabled-section {
  opacity: 0.55;
}

.disabled-content {
  pointer-events: none;
  user-select: none;
  filter: grayscale(0.35);
}

.compact-titlebar {
  min-height: 26px;
}

.section-body {
  padding: 10px;
}

.admin-list {
  display: grid;
  gap: 10px;
}

.event-card.is-warning-event {
  border-color: var(--warning);
  background: color-mix(in srgb, var(--card-inner-bg) 88%, var(--warning-soft) 12%);
}

.event-type {
  font-weight: 800;
  text-transform: capitalize;
}

.payload-details {
  display: grid;
  gap: 8px;
}

.payload-details summary {
  cursor: pointer;
  color: var(--text-muted);
  font-size: 0.82rem;
  font-weight: 800;
}

.admin-error {
  margin: 0;
  color: var(--danger);
}

@media (max-width: 640px) {
  .admin-toolbar,
  .automation-section,
  .data-row,
  .server-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .automation-controls {
    grid-template-columns: 1fr;
  }
}
</style>
