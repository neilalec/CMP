<script setup>
defineProps({ match: { type: Object, required: true }, totals: { type: Object, required: true } });
</script>

<template>
  <section class="window-panel" aria-label="Match overview">
    <div class="window-titlebar"><span>Match overview</span><span class="window-titlebar-meta">{{ match.source === 'cmp-backend' ? 'CMP LOBBY' : 'MOCK DATA' }}</span></div>
    <div class="wardogs-overview-grid">
      <div class="summary-tile"><span class="data-card-label">Server</span><strong>{{ match.server.name || match.join?.serverName || match.server.label }}</strong><small v-if="match.server.name || match.join?.serverName">{{ match.server.label }}</small></div>
      <div class="summary-tile"><span class="data-card-label">Map</span><strong>{{ match.configuration.map || 'Unknown' }}</strong></div>
      <div class="summary-tile"><span class="data-card-label">Experience / lighting / zone</span><strong>{{ [match.configuration.experience, match.configuration.lighting, match.configuration.zoneAlternator].filter(Boolean).join(' · ') || 'Unknown' }}</strong></div>
      <div class="summary-tile"><span class="data-card-label">Active roster</span><strong>{{ totals.connected }}/{{ totals.active }} connected · {{ totals.ready }}/{{ totals.active }} ready</strong><small>{{ totals.missing }} absent · {{ totals.unknown }} connection unknown · {{ totals.reserves }} reserves</small><small v-if="match.observation?.state === 'stale'">Presence is last known, not current.</small></div>
      <div v-if="match.source === 'cmp-backend'" class="summary-tile"><span class="data-card-label">Server population</span><strong>{{ match.serverStatus?.currentPlayers ?? '—' }}/{{ match.serverStatus?.maxPlayers ?? '—' }}</strong><small>Connected / capacity</small></div>
      <div v-if="match.source === 'cmp-backend'" class="summary-tile"><span class="data-card-label">Server observation</span><strong>{{ match.server.label }}</strong><small>{{ match.observation?.observedAt ? `Last observed ${match.observation.observedAt}` : 'No successful snapshot yet' }}</small><small v-if="match.observation?.pollState === 'error'">Latest read unavailable</small></div>
    </div>
  </section>
</template>
