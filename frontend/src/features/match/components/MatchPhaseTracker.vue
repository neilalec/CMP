<script setup>
const props = defineProps({
  currentPhase: {
    type: String,
    default: 'queue'
  },
  compact: {
    type: Boolean,
    default: false
  },
  phases: {
    type: Array,
    default: () => [
      { id: 'queue', label: 'Queue' },
      { id: 'accept', label: 'Accept' },
      { id: 'map', label: 'Map Vote' },
      { id: 'server', label: 'Join Server' },
      { id: 'live', label: 'Live' },
      { id: 'complete', label: 'Scoreboard' }
    ]
  }
});

const getPhaseState = (index) => {
  const currentIndex = Math.max(
    0,
    props.phases.findIndex((phase) => phase.id === props.currentPhase)
  );

  if (index < currentIndex) return 'is-complete';
  if (index === currentIndex) return 'is-current';
  return 'is-upcoming';
};
</script>

<template>
  <ol :class="['phase-tracker', { compact }]">
    <li
      v-for="(phase, index) in phases"
      :key="phase.id"
      :class="['phase-step', getPhaseState(index)]"
    >
      <span class="phase-dot" aria-hidden="true"></span>
      <span class="phase-label">{{ phase.label }}</span>
    </li>
  </ol>
</template>

<style scoped>
.phase-tracker {
  --tracker-accent: var(--accent);
  --tracker-muted: var(--surface-border);
  width: 100%;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 0;
  list-style: none;
  padding: 0;
  margin: 0;
  border: 1px solid var(--surface-border);
  background: var(--panel-bg);
  box-shadow: none;
}

.phase-step {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  min-width: 0;
  min-height: 38px;
  padding: 6px 8px;
  color: var(--text-muted);
  font-family: var(--font-mono);
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  background: transparent;
  border-right: 1px solid var(--surface-border);
  box-shadow: none;
}

.phase-step:last-child {
  border-right: 0;
}

.phase-dot {
  flex: 0 0 auto;
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: 1px solid var(--tracker-muted);
  background: var(--panel-bg-strong);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--text-main);
  font-size: 0.58rem;
  font-weight: 700;
  line-height: 1;
  box-shadow: none;
  z-index: 1;
}

.phase-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.phase-step.is-complete,
.phase-step.is-current {
  color: var(--text-main);
}

.phase-step.is-current {
  background: var(--accent-soft);
}

.phase-step.is-complete .phase-dot {
  background: var(--tracker-accent);
  border-color: var(--tracker-accent);
  color: #f7f8fa;
  box-shadow: none;
}

.phase-step.is-current .phase-dot {
  background: var(--panel-bg-strong);
  border-color: var(--tracker-accent);
  box-shadow: 0 0 0 1px var(--accent-border);
}

.phase-step.is-current .phase-dot::after {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--tracker-accent);
}

.phase-tracker.compact {
  gap: 0;
  padding: 0;
}

.phase-tracker.compact .phase-step {
  font-size: 0.62rem;
  min-height: 32px;
  padding: 5px 6px;
}

.phase-tracker.compact .phase-label {
  letter-spacing: 0.02em;
}

@media (max-width: 680px) {
  .phase-tracker {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .phase-step:nth-child(3n) {
    border-right: 0;
  }

  .phase-step:nth-child(n + 4) {
    border-top: 1px solid var(--surface-border);
  }

  .phase-label {
    font-size: 0.58rem;
  }

  .phase-dot {
    width: 13px;
    height: 13px;
  }
}
</style>
