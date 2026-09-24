<script setup>
import { computed } from 'vue';
import { matchRoomState, participantObservation } from '../models/presentation';

const props = defineProps({
  match: { type: Object, required: true },
  participant: { type: Object, default: null }
});
const state = computed(() => matchRoomState(props.match, props.participant));
const observation = computed(() => participantObservation(props.match, props.participant));
</script>

<template>
  <section class="wardogs-state-header" aria-label="Match state and your next action">
    <div class="wardogs-state-main">
      <p class="wardogs-kicker">WARDOGS match room</p>
      <h1>{{ state.title }}</h1>
      <strong class="wardogs-next-action">{{ state.action }}</strong>
      <p v-if="match.devSimulation?.enabled" class="wardogs-state-note">{{ match.devSimulation.label }}</p>
    </div>
    <div v-if="participant" class="wardogs-personal-status" aria-label="Your match status">
      <strong>Your position</strong>
      <p><span>Planned</span><b>{{ participant.faction.name }} · {{ participant.player.rosterStatus === 'reserve' ? 'Reserve' : 'Active' }}</b></p>
      <p><span>Group</span><b>{{ participant.group.name }}</b></p>
      <p><span>Registration</span><b>{{ participant.player.registered ? 'Registered' : 'Pending' }}</b></p>
      <p><span>Observed</span><b>{{ observation }}</b></p>
      <p><span>CMP ready</span><b>{{ participant.player.ready ? 'Ready' : 'Not ready' }}</b></p>
    </div>
  </section>
</template>
