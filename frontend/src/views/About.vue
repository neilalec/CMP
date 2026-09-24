<script setup>
import { RouterLink } from 'vue-router';
import { DISCORD_INVITE_URL } from '../constants/links';
</script>

<template>
  <div class="static-page content-panel page-shell narrow">
    <section class="static-card surface-card">
      <div class="window-titlebar"><span class="window-titlebar-label">About CMP</span></div>
      <div class="static-body">
        <section class="static-section">
          <h1 class="static-section-title is-large">WARDOGS matchmaking</h1>
          <p>CMP brings players together for three-faction WARDOGS matches. Join the beta queue alone or with a small group, then accept when the match is ready.</p>
          <p>After acceptance, your match room shows the planned factions and server join instructions when a server is available. Live server information is separate from the final result, which an administrator confirms.</p>
        </section>
        <section class="static-section">
          <h2 class="static-section-title">Need help?</h2>
          <p>Visit the <a class="static-link" :href="DISCORD_INVITE_URL" target="_blank" rel="noopener noreferrer">community Discord</a> or return to <RouterLink to="/play">Play</RouterLink>.</p>
        </section>
      </div>
    </section>
  </div>
</template>
