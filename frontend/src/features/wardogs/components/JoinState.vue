<script setup>
import { computed } from 'vue';

const props = defineProps({
  join: { type: Object, required: true }
});
const directUrl = computed(() => props.join.state === 'direct_join_available' &&
  typeof props.join.directJoinUrl === 'string' &&
  /^(steam|https):\/\//i.test(props.join.directJoinUrl)
  ? props.join.directJoinUrl : '');
</script>

<template>
  <section class="wardogs-join-state" aria-label="Server and joining">
    <h2 v-if="join.state === 'waiting_for_server'">Waiting for a WARDOGS server</h2>
    <template v-else>
      <h2>{{ join.serverName || 'WARDOGS server allocated' }}</h2>
      <p v-if="join.state === 'manual_join_available' && join.instructions">{{ join.instructions }}</p>
      <a v-else-if="directUrl" :href="directUrl">Join server</a>
      <p v-else>Server allocated. Verified player join instructions are not available yet.</p>
    </template>
  </section>
</template>
