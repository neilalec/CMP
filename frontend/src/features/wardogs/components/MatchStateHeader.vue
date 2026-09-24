<script setup>
import { computed } from 'vue';
import { matchRoomState, participantObservation } from '../models/presentation';

const props = defineProps({
  match: { type: Object, required: true },
  participant: { type: Object, default: null }
});
const state = computed(() => matchRoomState(props.match, props.participant));
const observation = computed(() => participantObservation(props.match, props.participant));
const observationTone = computed(() => {
  if (!props.participant || props.match.observation?.state !== 'fresh') return 'cmp-status--stale';
  const player = props.participant.player;
  if (player.connected === true && player.observedFactionId &&
      player.observedFactionId !== props.participant.faction.id) return 'cmp-status--danger';
  if (player.connected === true && player.observedFactionId === props.participant.faction.id) return 'cmp-status--success';
  return 'cmp-status--warning';
});
</script>

<template>
  <header class="wardogs-state-header cmp-surface" aria-label="Match state and your next action">
    <div class="wardogs-state-main">
      <p class="cmp-kicker">Match room</p>
      <h1>{{ state.title }}</h1>
      <p class="wardogs-next-action" role="status">{{ state.action }}</p>
      <p v-if="match.devSimulation?.enabled" class="wardogs-state-note">{{ match.devSimulation.label }}</p>
    </div>
    <section v-if="participant" class="wardogs-personal-status" aria-label="Your match status">
      <p class="cmp-kicker">Your assignment</p>
      <h2 class="cmp-faction-marker" :class="`cmp-faction--${participant.faction.id}`">{{ participant.faction.name }} <small>· {{ participant.player.rosterStatus === 'reserve' ? 'Reserve' : 'Active' }}</small></h2>
      <p class="wardogs-personal-group">{{ participant.group.name }}<span v-if="!participant.player.registered"> · CMP registration pending</span></p>
      <p class="cmp-status wardogs-personal-observation" :class="observationTone"><span>Observed: {{ observation }}</span></p>
      <p class="wardogs-personal-ready">CMP readiness: <strong>{{ participant.player.ready ? 'Ready' : 'Not ready' }}</strong></p>
    </section>
  </header>
</template>
