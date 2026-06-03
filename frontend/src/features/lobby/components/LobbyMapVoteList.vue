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
  <div class="map-list">
    <button
      v-for="map in maps"
      :key="map"
      @click="$emit('vote', map)"
      :class="['map-button', { voted: selectedMap === map }]"
      type="button"
    >
      {{ map }}
      <span v-if="getVotesForMap(map) > 0" class="vote-count">
        ({{ getVotesForMap(map) }})
      </span>
    </button>
  </div>
</template>

<style scoped>
.map-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: stretch;
  margin-top: 0;
  padding-top: 34px;
  width: 100%;
  max-width: var(--middle-column-width, 280px);
}

.map-button {
  position: relative;
  padding: 15px 25px;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 120px;
  width: 100%;
  text-align: center;
}

.map-button:hover {
  background: #4a4f56;
}

.map-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.map-button.voted {
  background: #2E7D32;
  transform: scale(1.05);
}

.vote-count {
  position: absolute;
  top: -8px;
  right: -8px;
  background: #2d2d2d;
  color: #4CAF50;
  border-radius: 50%;
  padding: 2px 6px;
  font-size: 0.8em;
}

@media (max-width: 900px) {
  .map-list {
    padding-top: 0;
    max-width: 100%;
    width: 100%;
  }
}
</style>
