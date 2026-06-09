<script setup>
defineProps({
  maps: {
    type: Array,
    default: () => []
  },
  selectedMap: {
    type: String,
    default: ''
  },
  getVotesForMap: {
    type: Function,
    required: true
  }
})

defineEmits(['vote'])
</script>

<template>
  <div class="map-list window-panel">
    <div class="window-titlebar">
      <span class="window-titlebar-label">Vote</span>
      <span class="window-titlebar-meta">{{ maps.length }}</span>
    </div>
    <div class="map-list-body">
      <button
        v-for="map in maps"
        :key="map"
        @click="$emit('vote', map)"
        :class="['map-button', { voted: selectedMap === map }]"
        type="button"
      >
        <span>{{ map }}</span>
        <strong v-if="getVotesForMap(map) > 0" class="vote-count">
          {{ getVotesForMap(map) }}
        </strong>
      </button>
    </div>
  </div>
</template>

<style scoped>
.map-list {
  margin-top: 0;
  width: 100%;
  max-width: var(--middle-column-width, 280px);
  overflow: hidden;
}

.map-list-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: stretch;
  padding: 12px;
}

.map-button {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  background: var(--control-bg);
  color: inherit;
  border: 1px solid var(--control-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease, transform 0.08s ease;
  min-width: 120px;
  width: 100%;
  text-align: left;
  font-weight: 800;
  box-shadow: var(--surface-shadow);
}

.map-button:hover {
  background: var(--control-bg-hover);
  transform: translateY(-1px);
}

.map-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.map-button.voted {
  background: var(--accent-soft);
  border-color: var(--accent-border);
  color: var(--accent-strong);
}

.vote-count {
  flex: 0 0 auto;
  min-width: 24px;
  min-height: 24px;
  background: var(--panel-bg-strong);
  border: 1px solid var(--accent-border);
  color: var(--accent-strong);
  border-radius: var(--radius-sm);
  padding: 3px 7px;
  font-size: 0.78em;
  font-weight: 900;
  box-shadow: var(--surface-shadow);
}

@media (max-width: 900px) {
  .map-list {
    padding-top: 0;
    max-width: 100%;
    width: 100%;
  }
}
</style>
