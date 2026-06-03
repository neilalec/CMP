<script setup>
defineProps({
  layoutClass: {
    type: String,
    default: ''
  }
})
</script>

<template>
  <div :class="['map-vote-layout', layoutClass]">
    <div class="phase-column phase-left">
      <slot name="left" />
    </div>
    <div class="phase-column phase-center">
      <slot name="center" />
    </div>
    <div class="phase-column phase-right">
      <slot name="right" />
    </div>
  </div>
</template>

<style scoped>
.map-vote-layout {
  display: grid;
  grid-template-columns: minmax(260px, 1fr) minmax(220px, var(--middle-column-width, 280px)) minmax(260px, 1fr);
  gap: var(--phase-column-gap, clamp(20px, 3vw, 56px));
  width: 100%;
  max-width: min(100%, 1120px);
  justify-content: center;
  align-items: start;
  min-height: 480px;
}

.phase-column {
  min-width: 0;
}

.phase-center {
  display: flex;
  justify-content: center;
}

.match-ready-layout {
  min-height: 480px;
}

.server-details-layout {
  min-height: 420px;
}

@media (max-width: 1200px) {
  .map-vote-layout {
    max-width: 100%;
  }
}

@media (max-width: 900px) {
  .map-vote-layout {
    display: flex;
    flex-direction: column;
    gap: 20px;
    align-items: stretch;
  }

  .phase-center {
    width: 100%;
  }
}
</style>
