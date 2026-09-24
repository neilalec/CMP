<script setup>
import { computed } from 'vue';
import { RouterLink } from 'vue-router';
import { useQueueStore } from '../stores/queueStore';

const queueStore = useQueueStore();
const currentWardogsLobby = computed(() => queueStore.wardogsLobbyId || null);
</script>

<template>
  <div class="matches-page cmp-page">
    <header class="matches-heading">
      <p class="matches-kicker">WARDOGS</p>
      <h1>Matches</h1>
    </header>
    <section class="matches-current cmp-surface" aria-label="Current match">
      <template v-if="currentWardogsLobby">
        <div>
          <p class="matches-label">Current match</p>
          <h2>Your WARDOGS match is ready</h2>
        </div>
        <RouterLink class="matches-link cmp-button cmp-button--primary" :to="`/wardogs/lobby/${currentWardogsLobby}`">Open match</RouterLink>
      </template>
      <template v-else>
        <h2>No current match</h2>
        <p>Join the WARDOGS queue to find a match.</p>
        <RouterLink class="matches-link cmp-button cmp-button--primary" to="/play">Go to Play</RouterLink>
      </template>
    </section>
  </div>
</template>

<style scoped>
.matches-page { display: grid; gap: 28px; width: min(100%, 760px); margin: clamp(6px, 1.6vw, 16px) auto 0; padding: clamp(28px, 5vw, 60px) var(--cmp-page-gutter) var(--cmp-page-gutter); }
.matches-heading { display: grid; gap: 8px; }
.matches-kicker { margin: 0; color: var(--cmp-primary-hover); font: 800 .78rem var(--cmp-font-mono); letter-spacing: .08em; text-transform: uppercase; }
.matches-heading h1 { margin: 0; font-size: clamp(2rem, 4vw, 3rem); letter-spacing: -.03em; }
.matches-current { min-height: 160px; display: flex; flex-direction: column; align-items: flex-start; justify-content: center; gap: 14px; padding: 26px; }
.matches-current h2 { margin: 0; font-size: 1.15rem; }
.matches-current p { margin: 0; color: var(--cmp-text-secondary); }
.matches-label { margin-bottom: 6px !important; color: var(--cmp-text-muted) !important; font-size: .7rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase; }
.matches-link { min-height: 40px; padding: 0 16px; font-size: .84rem; }
</style>
