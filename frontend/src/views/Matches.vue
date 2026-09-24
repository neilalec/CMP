<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import { useQueueStore } from '../stores/queueStore';

const queueStore = useQueueStore();
const currentWardogsLobby = computed(() => queueStore.wardogsLobbyId || null);
</script>

<template>
  <div class="matches-page content-panel page-shell narrow">
    <header class="matches-heading">
      <p class="eyebrow">WARDOGS</p>
      <h1>Matches</h1>
    </header>
    <section class="matches-current" aria-label="Current match">
      <template v-if="currentWardogsLobby">
        <div>
          <p class="matches-label">Current match</p>
          <h2>Your WARDOGS match is ready</h2>
        </div>
        <RouterLink class="matches-link" :to="`/wardogs/lobby/${currentWardogsLobby}`">Open match</RouterLink>
      </template>
      <template v-else>
        <h2>No current match</h2>
        <p>Join the WARDOGS queue to find a match.</p>
        <RouterLink class="matches-link" to="/play">Go to Play</RouterLink>
      </template>
    </section>
  </div>
</template>

<style scoped>
.matches-page { display: grid; gap: 28px; padding-top: clamp(28px, 5vw, 60px); }
.matches-heading { display: grid; gap: 8px; }
.matches-heading h1 { margin: 0; font-size: clamp(2rem, 4vw, 3rem); letter-spacing: -.03em; }
.matches-current { min-height: 160px; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 14px; padding: 26px; border: 1px solid var(--border-muted); border-radius: var(--radius-lg); background: var(--surface); }
.matches-current h2 { margin: 0; font-size: 1.15rem; }
.matches-current p { margin: 0; color: var(--text-secondary); }
.matches-label { margin-bottom: 6px !important; color: var(--text-muted) !important; font-size: .7rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.matches-link { display: inline-flex; align-items: center; min-height: 40px; padding: 0 16px; border: 1px solid var(--primary); border-radius: var(--radius-sm); background: var(--primary); color: #061624; font-size: .84rem; font-weight: 800; text-decoration: none; }
.matches-link:hover { background: var(--primary-hover); color: #061624; text-decoration: none; }
</style>
