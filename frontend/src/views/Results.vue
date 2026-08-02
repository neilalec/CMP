<script setup>
import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../stores/authStore';
import { useRootStore } from '../stores/rootStore';
import { API_BASE_URL } from '../config';
import { mapMatchToHistoryRow } from '../features/match/utils/matchHistory';

const authStore = useAuthStore();
const rootStore = useRootStore();
const loading = ref(false);
const error = ref('');
const matches = ref([]);
const viewMode = ref('list');

const matchRows = computed(() => matches.value.map(mapMatchToHistoryRow));

const loadResults = async () => {
  if (!authStore.token) return;
  loading.value = true;
  error.value = '';
  try {
    const response = await fetch(`${API_BASE_URL}/matches/history?limit=30`, {
      headers: {
        Authorization: `Bearer ${authStore.token}`
      }
    });
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      throw new Error(`Expected JSON from results API, received ${response.headers.get('content-type') || 'unknown content'}`);
    }
    if (!response.ok || !payload?.success) {
      throw new Error(payload?.message || 'Failed to load results');
    }
    matches.value = payload.matches || [];
  } catch (err) {
    error.value = err.message || 'Failed to load results';
    rootStore.setError(error.value);
  } finally {
    loading.value = false;
  }
};

onMounted(loadResults);
</script>

<template>
  <div class="results-page content-panel page-shell">
    <section class="results-panel window-panel">
      <div class="window-titlebar">
        <span class="window-titlebar-label">Results</span>
        <span class="window-titlebar-meta">{{ matchRows.length }}</span>
      </div>
      <div class="panel-body">
        <div class="results-toolbar">
          <span class="meta-label">{{ loading ? 'Loading' : 'Archive' }}</span>
          <div class="results-toolbar-actions">
            <div class="view-toggle" role="group" aria-label="Result layout">
              <button type="button" :class="{ 'is-selected-control': viewMode === 'list' }" @click="viewMode = 'list'">
                List
              </button>
              <button type="button" :class="{ 'is-selected-control': viewMode === 'grid' }" @click="viewMode = 'grid'">
                Grid
              </button>
            </div>
            <button type="button" @click="loadResults" :disabled="loading">
              {{ loading ? 'Refreshing...' : 'Refresh' }}
            </button>
          </div>
        </div>

        <p v-if="error" class="results-error">{{ error }}</p>
        <p v-else-if="!matchRows.length && !loading" class="empty-state">No results</p>

        <div v-else class="results-list" :class="{ 'is-grid': viewMode === 'grid' }">
          <article v-for="match in matchRows" :key="match.id" class="result-card data-card">
            <div class="result-main">
              <strong>{{ match.map }}</strong>
              <span class="info-row-meta">{{ match.completedAt }}</span>
            </div>
            <div class="result-grid">
              <div>
                <span class="data-card-label">Result</span>
                <strong>{{ match.result }}</strong>
              </div>
              <div>
                <span class="data-card-label">Score</span>
                <strong>{{ match.score || '-' }}</strong>
              </div>
              <div>
                <span class="data-card-label">Winner</span>
                <strong>{{ match.winner || '-' }}</strong>
              </div>
              <div>
                <span class="data-card-label">Server</span>
                <strong>{{ match.server }}</strong>
              </div>
            </div>
            <p v-if="match.note" class="result-note">{{ match.note }}</p>
          </article>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.results-page {
  width: min(100%, var(--page-width));
}

.results-panel {
  overflow: hidden;
}

.results-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.results-toolbar button {
  width: auto;
  margin: 0;
}

.results-toolbar-actions,
.view-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

.view-toggle button {
  min-width: 74px;
}

.results-list {
  display: grid;
  gap: 10px;
}

.results-list.is-grid {
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
}

.result-card {
  display: grid;
  gap: 12px;
}

.result-main {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.result-main strong {
  font-size: 1rem;
}

.result-note {
  color: var(--text-muted);
  font-size: 0.82rem;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.result-grid div {
  display: grid;
  gap: 3px;
  min-width: 0;
}

.result-grid strong {
  overflow-wrap: anywhere;
}

.result-note {
  margin: 0;
}

.results-error {
  margin: 0;
  color: var(--danger);
}

@media (max-width: 760px) {
  .result-main,
  .results-toolbar,
  .results-toolbar-actions,
  .view-toggle {
    align-items: stretch;
    flex-direction: column;
  }

  .result-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 460px) {
  .result-grid {
    grid-template-columns: 1fr;
  }
}
</style>
