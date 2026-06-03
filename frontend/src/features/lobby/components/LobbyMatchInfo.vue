<script setup>
defineProps({
  matchSizeLabel: {
    type: String,
    default: ''
  },
  selectedMap: {
    type: String,
    default: ''
  },
  serverLabel: {
    type: String,
    default: ''
  },
  serverPrefix: {
    type: String,
    default: 'Server'
  }
})
</script>

<template>
  <div class="match-info match-info-center">
    <p v-if="matchSizeLabel">Format <span class="highlight">{{ matchSizeLabel }}</span></p>
    <p>Map <span class="highlight">{{ selectedMap }}</span></p>
    <p>{{ serverPrefix }} <span class="highlight">{{ serverLabel }}</span></p>
  </div>
</template>

<style scoped>
.match-info {
  background: #243447;
  padding: 20px;
  border-radius: 4px;
  width: 100%;
  max-width: var(--middle-column-width, 280px);
  text-align: center;
}

.match-info-center {
  align-self: center;
  justify-self: center;
}

.match-info p {
  margin: 10px 0;
  font-size: 1.1em;
  color: inherit;
  text-align: center;
}

.highlight {
  color: #4CAF50;
  font-weight: bold;
}

@media (max-width: 900px) {
  .match-info {
    width: 100%;
    max-width: 100%;
    margin-top: 0;
  }

  .match-info-center {
    align-self: stretch;
  }
}

@media (max-width: 640px) {
  .match-info p {
    font-size: 1rem;
  }
}
</style>
