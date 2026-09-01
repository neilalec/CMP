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
  },
  votedCount: {
    type: Number,
    default: 0
  },
  disabled: {
    type: Boolean,
    default: false
  }
})

defineEmits(['vote'])
</script>

<template>
  <div class="map-list window-panel">
    <div class="window-titlebar">
      <span class="window-titlebar-label">Vote</span>
      <span class="window-titlebar-meta">{{ votedCount }}</span>
    </div>
    <div class="map-list-body">
      <button
        v-for="map in maps"
        :key="map"
        @click="$emit('vote', map)"
        :class="['map-button', { 'is-selected-control': selectedMap === map }]"
        :disabled="disabled"
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
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: var(--button-flat-bg);
  color: var(--button-flat-text);
  border: 1px solid var(--button-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background-color 0.12s ease, border-color 0.12s ease, box-shadow 0.12s ease, transform 0.08s ease;
  min-width: 120px;
  width: 100%;
  text-align: left;
  font-weight: 800;
  box-shadow: var(--button-shadow);
}

.map-button span {
  min-width: 0;
}

.map-button:hover {
  background: var(--button-flat-bg-hover);
  border-color: var(--button-border-hover);
  box-shadow: var(--button-hover-shadow);
  transform: translateY(-1px);
}

.map-button:disabled {
  background: var(--button-disabled-bg);
  color: var(--button-disabled-text);
  border-color: var(--button-border);
  cursor: not-allowed;
}

.vote-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 28px;
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: 0.86em;
  font-weight: 900;
  text-align: center;
}

@media (max-width: 900px) {
  .map-list {
    padding-top: 0;
    max-width: 100%;
    width: 100%;
  }
}
</style>
