<script setup>
import { DISCORD_INVITE_URL } from '../constants/links';
</script>

<template>
  <div class="static-page is-centered content-panel page-shell narrow">
    <section class="static-card is-compact surface-card">
      <div class="window-titlebar">
        <span class="window-titlebar-label">Link</span>
      </div>
      <div class="static-body is-compact">
        <p class="static-copy">
        </p>
        <a class="static-link" :href="DISCORD_INVITE_URL" target="_blank" rel="noopener noreferrer">
          {{ DISCORD_INVITE_URL }}
        </a>
      </div>
    </section>
  </div>
</template>
