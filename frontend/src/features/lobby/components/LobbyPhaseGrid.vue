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
  grid-template-columns: minmax(0, 1fr) minmax(240px, var(--middle-column-width, 300px)) minmax(0, 1fr);
  gap: var(--phase-column-gap, clamp(16px, 2vw, 28px));
  width: 100%;
  max-width: 100%;
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
  align-items: flex-start;
}

.match-ready-layout {
  min-height: 480px;
}

.server-details-layout {
  min-height: 420px;
  align-items: center;
}

.match-ready-layout .phase-center,
.server-details-layout .phase-center {
  align-items: center;
}

@media (max-width: 1200px) {
  .map-vote-layout {
    max-width: 100%;
  }
}

@media (max-width: 980px) {
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
