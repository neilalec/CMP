<script setup>
defineProps({ match: { type: Object, required: true }, totals: { type: Object, required: true } });
</script>

<template>
  <details class="wardogs-evidence" aria-label="Server and observation details">
    <summary>Server and observation details <span>{{ match.server.label }}</span></summary>
    <dl>
      <div><dt>Server</dt><dd>{{ match.server.name || match.join?.serverName || match.server.label }}</dd></div>
      <div><dt>Map</dt><dd>{{ match.configuration.map || 'Unknown' }}</dd></div>
      <div><dt>Experience / lighting / zone</dt><dd>{{ [match.configuration.experience, match.configuration.lighting, match.configuration.zoneAlternator].filter(Boolean).join(' · ') || 'Unknown' }}</dd></div>
      <div><dt>Active roster</dt><dd>{{ match.source === 'cmp-backend' && ['none', 'unavailable'].includes(match.observation?.state) ? 'Connection unknown' : `${totals.connected}/${totals.active} ${match.observation?.state === 'stale' ? 'last seen connected' : 'connected'}` }} · {{ totals.ready }}/{{ totals.active }} CMP ready · {{ totals.reserves }} reserves</dd></div>
      <div v-if="match.source === 'cmp-backend'"><dt>Server population</dt><dd>{{ match.serverStatus?.currentPlayers ?? '—' }}/{{ match.serverStatus?.maxPlayers ?? '—' }}</dd></div>
      <div v-if="match.source === 'cmp-backend'"><dt>Observation</dt><dd>{{ match.observation?.observedAt ? `Last observed ${match.observation.observedAt}` : 'No successful snapshot yet' }}<span v-if="match.observation?.pollState === 'error'"> · Latest read unavailable</span><span v-if="match.observation?.state === 'stale'"> · Presence is last known, not current</span></dd></div>
    </dl>
  </details>
</template>
