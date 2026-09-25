<script setup>
import { computed } from 'vue';
import { matchRoomState, participantObservation } from '../models/presentation';
import JoinState from './JoinState.vue';

const props = defineProps({
  match: { type: Object, required: true },
  participant: { type: Object, default: null }
});
const state = computed(() => matchRoomState(props.match, props.participant));
const observation = computed(() => participantObservation(props.match, props.participant));
const observationUnknown = computed(() => props.match.source === 'cmp-backend' &&
  props.match.join?.state !== 'waiting_for_server' && props.match.observation?.state !== 'fresh');
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
  <header class="wardogs-state-header cmp-surface" :class="{ 'needs-action': state.title === 'Connected on wrong faction' }" aria-label="Match state and your next action">
    <div class="wardogs-state-main">
      <p class="cmp-kicker">Match room</p>
      <p v-if="participant" class="wardogs-state-assignment cmp-faction-marker" :class="`cmp-faction--${participant.faction.id}`">You are {{ participant.player.rosterStatus === 'reserve' ? 'reserve' : 'active' }} · {{ participant.faction.name }}</p>
      <h1>{{ state.title }}</h1>
      <p v-if="state.action !== state.title && match.join?.state !== 'waiting_for_server'" class="wardogs-next-action" role="status">{{ state.action }}</p>
      <p v-if="match.devSimulation?.enabled" class="wardogs-state-note">{{ match.devSimulation.label }}</p>
    </div>
    <JoinState v-if="state.joinProminent" :join="match.join" prominent />
    <div class="wardogs-state-context">
      <span v-if="participant">{{ participant.group.name }}<template v-if="!participant.player.registered"> · CMP registration pending</template></span>
      <span v-if="observationUnknown && state.title !== 'Server observation stale'">{{ match.observation?.state === 'stale' ? 'Server observation is stale; current presence is unknown' : 'Server presence has not been verified' }}</span>
      <span v-else-if="participant && match.observation?.state === 'fresh' && observationTone !== 'cmp-status--success'" class="cmp-status" :class="observationTone">{{ observation }}</span>
      <span v-if="participant && participant.player.ready && !observationUnknown">CMP ready</span>
    </div>
  </header>
</template>
