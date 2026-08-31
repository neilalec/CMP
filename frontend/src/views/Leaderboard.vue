<script setup>
import { computed, onMounted, ref } from 'vue';
import { API_BASE_URL } from '../config';
import { useAuthStore } from '../stores/authStore';
import { useRootStore } from '../stores/rootStore';

const authStore = useAuthStore();
const rootStore = useRootStore();
const loading = ref(false);
const error = ref('');
const players = ref([]);

const rankedPlayers = computed(() => players.value.map((player) => ({
  rank: Number(player.rank || 0),
  username: player.username || '',
  displayName: player.display_name || player.username || '',
  eloRating: Number(player.elo_rating ?? 1000),
  eloMatches: Number(player.elo_matches ?? 0),
})));

const loadLeaderboard = async () => {
  if (!authStore.token) return;
  loading.value = true;
  error.value = '';
  try {
    const response = await fetch(`${API_BASE_URL}/leaderboard`, {
      headers: {
        Authorization: `Bearer ${authStore.token}`
      }
    });
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      throw new Error(`Expected JSON from leaderboard API, received ${response.headers.get('content-type') || 'unknown content'}`);
    }
    if (!response.ok || !payload?.success) {
      throw new Error(payload?.message || 'Failed to load leaderboard');
    }
    players.value = payload.players || [];
  } catch (err) {
    error.value = err.message || 'Failed to load leaderboard';
    rootStore.setError(error.value);
  } finally {
    loading.value = false;
  }
};

onMounted(loadLeaderboard);
</script>

<template>
  <div class="leaderboard-page content-panel page-shell">
    <section class="leaderboard-panel window-panel">
      <div class="window-titlebar">
        <span class="window-titlebar-label">Leaderboard</span>
        <span class="window-titlebar-meta">{{ rankedPlayers.length }}</span>
      </div>
      <div class="panel-body">
        <div class="leaderboard-toolbar">
          <span class="meta-label">{{ loading ? 'Loading' : 'Elo Standings' }}</span>
          <button type="button" @click="loadLeaderboard" :disabled="loading">
            {{ loading ? 'Refreshing...' : 'Refresh' }}
          </button>
        </div>

        <p v-if="error" class="leaderboard-error">{{ error }}</p>
        <p v-else-if="!rankedPlayers.length && !loading" class="empty-state">No players</p>

        <div v-else class="leaderboard-table-wrap">
          <table class="leaderboard-table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Player</th>
                <th>Elo</th>
                <th>Rated</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="player in rankedPlayers"
                :key="player.username"
                :class="{ 'is-current-player': player.username === authStore.username }"
              >
                <td class="rank-cell">#{{ player.rank }}</td>
                <td>
                  <strong>{{ player.displayName }}</strong>
                  <span v-if="player.username !== player.displayName" class="username-note">{{ player.username }}</span>
                </td>
                <td class="elo-cell">{{ player.eloRating }}</td>
                <td>{{ player.eloMatches }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.leaderboard-page {
  width: min(100%, var(--page-width));
}

.leaderboard-panel {
  overflow: hidden;
}

.leaderboard-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.leaderboard-toolbar button {
  width: auto;
  margin: 0;
}

.leaderboard-table-wrap {
  overflow-x: auto;
}

.leaderboard-table {
  width: 100%;
  min-width: 520px;
  border-collapse: collapse;
  font-size: 0.9rem;
}

.leaderboard-table th,
.leaderboard-table td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--surface-border);
  text-align: left;
  vertical-align: middle;
}

.leaderboard-table th {
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 800;
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.leaderboard-table th:nth-child(3),
.leaderboard-table th:nth-child(4),
.leaderboard-table td:nth-child(3),
.leaderboard-table td:nth-child(4) {
  text-align: right;
}

.leaderboard-table tbody tr:last-child td {
  border-bottom: 0;
}

.leaderboard-table tbody tr.is-current-player {
  background: color-mix(in srgb, var(--accent-soft) 36%, transparent);
}

.rank-cell {
  width: 72px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-weight: 800;
}

.elo-cell {
  color: var(--accent-strong);
  font-family: var(--font-display);
  font-size: 1.15rem;
  font-weight: 900;
}

.username-note {
  display: block;
  margin-top: 2px;
  color: var(--text-muted);
  font-size: 0.76rem;
}

.leaderboard-error {
  margin: 0;
  color: var(--danger);
}

@media (max-width: 560px) {
  .leaderboard-toolbar {
    align-items: stretch;
    flex-direction: column;
  }

  .leaderboard-toolbar button {
    width: 100%;
  }
}
</style>
