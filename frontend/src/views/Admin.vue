<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useAuthStore } from '../stores/authStore';
import { useRootStore } from '../stores/rootStore';
import { API_BASE_URL } from '../config';

const authStore = useAuthStore();
const rootStore = useRootStore();

const diagnostics = ref(null);
const servers = ref([]);
const availableServers = ref([]);
const loading = ref(false);
const serverLoading = ref(false);
const testing = ref(false);
const error = ref('');
const testResult = ref(null);

const serverForm = reactive({
  display_name: '',
  owner_label: '',
  steam_lobby_id: '',
  connect_address: '',
  join_password: '',
  bridge_url: '',
  bridge_token: ''
});

const formatJson = (value) => JSON.stringify(value ?? null, null, 2);
const isAdmin = computed(() => !!authStore.token && !!authStore.isAdmin);

const apiFetch = async (path, options = {}) => {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authStore.token}`,
      ...(options.headers || {})
    }
  });
  const payload = await response.json();
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

const runServerTest = async () => {
  testing.value = true;
  testResult.value = null;
  try {
    const payload = await apiFetch('/admin/servers/test', {
      method: 'POST',
      body: JSON.stringify(serverForm)
    });
    testResult.value = payload.result || null;
  } catch (err) {
    rootStore.setError(err.message || 'Server test failed');
  } finally {
    testing.value = false;
  }
};

const createServer = async () => {
  serverLoading.value = true;
  try {
    await apiFetch('/admin/servers', {
      method: 'POST',
      body: JSON.stringify(serverForm)
    });
    testResult.value = null;
    Object.assign(serverForm, {
      display_name: '',
      owner_label: '',
      steam_lobby_id: '',
      connect_address: '',
      join_password: '',
      bridge_url: '',
      bridge_token: ''
    });
    await loadServers();
    await loadDiagnostics();
  } catch (err) {
    rootStore.setError(err.message || 'Failed to create server');
  } finally {
    serverLoading.value = false;
  }
};

const runHealthCheck = async (serverId) => {
  serverLoading.value = true;
  try {
    await apiFetch(`/admin/servers/${serverId}/health-check`, { method: 'POST' });
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

onMounted(async () => {
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
          <span>System</span>
          <button type="button" @click="loadDiagnostics(); loadServers()" :disabled="loading || serverLoading">
            {{ loading || serverLoading ? 'Refreshing...' : 'Refresh' }}
          </button>
        </div>

        <p v-if="error" class="admin-error">{{ error }}</p>

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
            <span class="data-card-label">Servers</span>
            <strong>{{ servers.length }}</strong>
            <p>{{ availableServers.length }} available</p>
          </article>
        </div>

        <section class="admin-section">
          <div class="window-titlebar compact-titlebar">
            <span class="window-titlebar-label">Add Server</span>
          </div>
          <div class="section-body server-form">
            <input v-model="serverForm.display_name" type="text" placeholder="Display name" />
            <input v-model="serverForm.owner_label" type="text" placeholder="Owner label" />
            <input v-model="serverForm.steam_lobby_id" type="text" placeholder="Steam lobby ID (optional)" />
            <input v-model="serverForm.connect_address" type="text" placeholder="Connect address" />
            <input v-model="serverForm.join_password" type="text" placeholder="Join password" />
            <input v-model="serverForm.bridge_url" type="text" placeholder="Bridge URL" />
            <input v-model="serverForm.bridge_token" type="password" placeholder="Bridge token" />
            <div class="server-form-actions">
              <button type="button" @click="runServerTest" :disabled="testing || serverLoading">
                {{ testing ? 'Testing...' : 'Test Server' }}
              </button>
              <button type="button" @click="createServer" :disabled="serverLoading">
                Add Server
              </button>
            </div>
            <pre v-if="testResult" class="payload-panel">{{ formatJson(testResult) }}</pre>
          </div>
        </section>

        <section class="admin-section">
          <div class="window-titlebar compact-titlebar">
            <span class="window-titlebar-label">Server Pool</span>
            <span class="window-titlebar-meta">{{ servers.length }}</span>
          </div>
          <div class="admin-list section-body">
            <article v-for="server in servers" :key="server.id" class="admin-list-item data-card">
              <div class="admin-row">
                <span>{{ server.display_name }}</span>
                <strong>{{ server.status }}</strong>
              </div>
              <div class="admin-row">
                <span>{{ server.bridge_url }}</span>
                <strong>{{ server.enabled ? 'Enabled' : 'Disabled' }}</strong>
              </div>
              <div class="admin-row">
                <span>{{ server.steam_lobby_id || 'No Steam lobby ID' }}</span>
                <strong>{{ server.connect_address || 'No connect address' }}</strong>
              </div>
              <div class="admin-row">
                <span>{{ server.connect_address || 'No connect address' }}</span>
                <strong>{{ server.bridge_token_masked || 'No token' }}</strong>
              </div>
              <div class="admin-row">
                <span>Submitted by {{ server.submitted_by || 'unknown' }}</span>
                <strong>{{ server.approved_by ? `Approved by ${server.approved_by}` : 'Awaiting approval' }}</strong>
              </div>
              <p v-if="server.last_health_error">{{ server.last_health_error }}</p>
              <div class="server-actions">
                <button type="button" @click="runHealthCheck(server.id)" :disabled="serverLoading">Health Check</button>
                <button
                  v-if="server.status === 'pending'"
                  type="button"
                  @click="approveServer(server.id)"
                  :disabled="serverLoading"
                >
                  Approve
                </button>
                <button
                  type="button"
                  @click="setServerEnabled(server.id, !server.enabled)"
                  :disabled="serverLoading"
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

.admin-toolbar,
.admin-row,
.server-form-actions,
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

.admin-section {
  margin-top: 14px;
  border: 1px solid var(--surface-border);
  background: var(--panel-bg);
}

.compact-titlebar {
  min-height: 26px;
}

.section-body {
  padding: 10px;
}

.server-form,
.admin-list {
  display: grid;
  gap: 10px;
}

.payload-panel {
  margin: 0;
  padding: 12px;
  background: var(--input-bg);
  border: 1px solid var(--input-border);
  box-shadow: var(--inset-shadow);
  font-size: 0.8rem;
  line-height: 1.45;
  overflow-x: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.admin-error {
  margin: 0;
  color: var(--danger);
}

@media (max-width: 640px) {
  .admin-toolbar,
  .admin-row,
  .server-form-actions,
  .server-actions {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
