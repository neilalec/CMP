<script setup>
import { computed } from 'vue';

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
      { id: 'complete', label: 'Score' }
    ]
  }
});

const currentIndex = computed(() => Math.max(
  0,
  props.phases.findIndex((phase) => phase.id === props.currentPhase)
));

const trackerStyle = computed(() => ({
  '--phase-count': Math.max(1, props.phases.length)
}));

const getPhaseState = (index) => {
  if (index < currentIndex.value) return 'is-complete';
  if (index === currentIndex.value) return 'is-current';
  return 'is-upcoming';
};
</script>

<template>
  <ol :class="['phase-tracker', { compact }]" :style="trackerStyle">
    <li
      v-for="(phase, index) in phases"
      :key="phase.id"
      :class="['phase-step', getPhaseState(index)]"
    >
      <span class="phase-dot" aria-hidden="true"></span>
      <span class="phase-label">{{ phase.label }}</span>
      <span
        :class="[
          'phase-connector',
          {
            'is-terminal': index === phases.length - 1,
            'is-complete': index < currentIndex,
            'is-leading': index === currentIndex - 1
          }
        ]"
        aria-hidden="true"
      ></span>
    </li>
  </ol>
</template>

<style scoped>
.phase-tracker {
  --tracker-arrow: #6f9f75;
  --tracker-accent: var(--tracker-arrow);
  --tracker-muted: var(--surface-border);
  position: relative;
  width: 100%;
  display: grid;
  grid-template-columns: repeat(var(--phase-count), minmax(0, 1fr));
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
  display: grid;
  grid-template-columns: auto auto minmax(18px, 1fr);
  align-items: center;
  justify-content: stretch;
  column-gap: 7px;
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
  border-right: 0;
  box-shadow: none;
  z-index: 1;
}

.phase-step:last-child {
  border-right: 0;
}

.phase-dot {
  width: 15px;
  height: 15px;
  border-radius: 50%;
  border: 1px solid var(--tracker-muted);
  background: var(--panel-bg);
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

.phase-connector {
  position: relative;
  display: block;
  min-width: 18px;
  height: 3px;
  background: transparent;
  justify-self: stretch;
  margin-left: 1px;
  margin-right: 8px;
}

.phase-connector.is-complete {
  background: var(--tracker-arrow);
  box-shadow:
    0 0 5px rgba(111, 159, 117, 0.38),
    0 1px 0 rgba(0, 0, 0, 0.2);
}

.phase-connector.is-terminal {
  visibility: hidden;
}

.phase-connector.is-leading::after {
  content: "";
  position: absolute;
  right: -8px;
  top: 50%;
  width: 0;
  height: 0;
  border-top: 6px solid transparent;
  border-bottom: 6px solid transparent;
  border-left: 9px solid var(--tracker-arrow);
  transform: translateY(-50%);
  filter: drop-shadow(0 0 4px rgba(111, 159, 117, 0.48)) drop-shadow(0 1px 0 rgba(0, 0, 0, 0.26));
}

.phase-step.is-complete,
.phase-step.is-current {
  color: var(--text-main);
}

.phase-step.is-complete {
  background: transparent;
}

.phase-step.is-current {
  background: transparent;
}

.phase-step.is-complete .phase-dot {
  position: relative;
  background: var(--tracker-accent);
  border-color: var(--tracker-accent);
  color: var(--phase-check-text, #fff3d2);
  box-shadow: 0 0 0 1px var(--accent-border);
}

.phase-step.is-complete .phase-dot::before {
  content: "";
  width: 7px;
  height: 4px;
  border-left: 2px solid currentColor;
  border-bottom: 2px solid currentColor;
  transform: translateY(-1px) rotate(-45deg);
}

.phase-step.is-current .phase-dot {
  background: var(--panel-bg-strong);
  border-color: var(--tracker-accent);
  box-shadow:
    0 0 0 2px var(--tracker-arrow),
    0 0 7px color-mix(in srgb, var(--tracker-arrow) 48%, transparent);
  animation: phase-current-pulse 1.8s ease-in-out infinite;
}

.phase-step.is-current .phase-dot::after {
  content: "";
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--tracker-accent);
}

@keyframes phase-current-pulse {
  0%,
  100% {
    box-shadow:
      0 0 0 2px var(--tracker-arrow),
      0 0 5px color-mix(in srgb, var(--tracker-arrow) 42%, transparent),
      0 0 0 0 color-mix(in srgb, var(--tracker-arrow) 24%, transparent);
    transform: scale(1);
  }

  50% {
    box-shadow:
      0 0 0 2px var(--tracker-arrow),
      0 0 8px color-mix(in srgb, var(--tracker-arrow) 54%, transparent),
      0 0 0 4px color-mix(in srgb, var(--tracker-arrow) 0%, transparent);
    transform: scale(1.06);
  }
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

  .phase-step {
    grid-template-columns: auto auto;
    justify-content: center;
  }

  .phase-connector {
    display: none;
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
