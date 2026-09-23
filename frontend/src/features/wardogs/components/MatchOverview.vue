<script setup>
defineProps({ match: { type: Object, required: true }, totals: { type: Object, required: true } });
</script>

<template>
  <section class="window-panel" aria-label="Match overview">
    <div class="window-titlebar"><span>Match overview</span><span class="window-titlebar-meta">MOCK DATA</span></div>
    <div class="wardogs-overview-grid">
      <div class="summary-tile"><span class="data-card-label">Server</span><strong>{{ match.server.label }}</strong></div>
      <div class="summary-tile"><span class="data-card-label">Map</span><strong>{{ match.configuration.map || 'Unknown' }}</strong></div>
      <div class="summary-tile"><span class="data-card-label">Experience / lighting / zone</span><strong>{{ [match.configuration.experience, match.configuration.lighting, match.configuration.zoneAlternator].filter(Boolean).join(' · ') || 'Unknown' }}</strong></div>
      <div class="summary-tile"><span class="data-card-label">Active roster</span><strong>{{ totals.connected }}/{{ totals.active }} connected · {{ totals.ready }}/{{ totals.active }} ready</strong><small>{{ totals.missing }} missing · {{ totals.reserves }} reserves</small></div>
    </div>
  </section>
</template>
