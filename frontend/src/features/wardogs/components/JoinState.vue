<script setup>
import { computed, ref } from 'vue';

const props = defineProps({
  join: { type: Object, required: true },
  prominent: { type: Boolean, default: true }
});
const directUrl = computed(() => props.join.state === 'direct_join_available' &&
  typeof props.join.directJoinUrl === 'string' &&
  /^(steam|https):\/\//i.test(props.join.directJoinUrl)
  ? props.join.directJoinUrl : '');
const joinId = computed(() => props.join.state === 'manual_join_available' &&
  typeof props.join.joinId === 'string' && /^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$/.test(props.join.joinId)
  ? props.join.joinId : '');
const copyStatus = ref('');
const copyJoinId = async () => {
  if (!joinId.value || !navigator?.clipboard?.writeText) {
    copyStatus.value = 'Copy is unavailable in this browser.';
    return;
  }
  try {
    await navigator.clipboard.writeText(joinId.value);
    copyStatus.value = 'Join ID copied.';
  } catch {
    copyStatus.value = 'Could not copy the Join ID.';
  }
};
</script>

<template>
  <section class="wardogs-join-state" :class="{ 'is-compact': !prominent }" aria-label="Server and joining">
    <h2 v-if="join.state === 'waiting_for_server'">Waiting for a WARDOGS server</h2>
    <template v-else>
      <h2>{{ prominent ? 'Join server' : 'Server access' }}</h2>
      <p v-if="join.serverName" class="wardogs-server-name">{{ join.serverName }}</p>
      <p v-else>WARDOGS server allocated</p>
      <template v-if="join.state === 'manual_join_available' && joinId">
        <p v-if="prominent">Use Join By ID in WARDOGS</p>
        <div class="wardogs-join-id">
          <code>{{ joinId }}</code>
          <button class="cmp-button cmp-button--secondary" type="button" @click="copyJoinId">Copy Join ID</button>
        </div>
        <p v-if="copyStatus" aria-live="polite">{{ copyStatus }}</p>
        <details v-if="Array.isArray(join.instructions)" class="wardogs-join-instructions">
          <summary>Join By ID steps</summary>
          <ol><li v-for="(step, index) in join.instructions" :key="index">{{ step }}</li></ol>
        </details>
      </template>
      <a v-else-if="directUrl" class="cmp-button cmp-button--primary" :href="directUrl">Join server</a>
      <p v-else>Server allocated. Verified player join instructions are not available yet.</p>
    </template>
  </section>
</template>
