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
const copyFailed = ref(false);
const copyJoinId = async () => {
  if (!joinId.value || !navigator?.clipboard?.writeText) {
    copyStatus.value = 'Copy is unavailable in this browser.';
    copyFailed.value = true;
    return;
  }
  try {
    await navigator.clipboard.writeText(joinId.value);
    copyStatus.value = 'Join ID copied.';
    copyFailed.value = false;
  } catch {
    copyStatus.value = 'Could not copy the Join ID.';
    copyFailed.value = true;
  }
};
</script>

<template>
  <component :is="prominent ? 'section' : 'details'" class="wardogs-join-state cmp-surface" :class="{ 'is-compact': !prominent, 'cmp-disclosure': !prominent }" aria-label="Server and joining">
    <summary v-if="!prominent" class="wardogs-join-compact-summary">Server access <span>{{ join.serverName || 'WARDOGS server allocated' }}</span></summary>
    <h2 v-if="join.state === 'waiting_for_server'">Waiting for a WARDOGS server</h2>
    <template v-else>
      <div class="wardogs-join-heading"><div><p class="cmp-kicker">Server access</p><h2>{{ prominent && joinId ? 'Join by ID' : 'Server access' }}</h2></div><p>{{ join.serverName || 'WARDOGS server allocated' }}</p></div>
      <template v-if="join.state === 'manual_join_available' && joinId">
        <p v-if="prominent">Use Join By ID in WARDOGS to find this match.</p>
        <div class="wardogs-join-id">
          <code aria-label="Join ID">{{ joinId }}</code>
          <button class="cmp-button cmp-button--secondary" type="button" @click="copyJoinId">Copy Join ID</button>
        </div>
        <p v-if="copyStatus" class="wardogs-copy-feedback cmp-status" :class="copyFailed ? 'cmp-status--danger' : 'cmp-status--success'" :role="copyFailed ? 'alert' : 'status'">{{ copyStatus }}</p>
        <details v-if="Array.isArray(join.instructions) && join.instructions.length" class="wardogs-join-instructions cmp-disclosure">
          <summary>Join By ID steps</summary>
          <ol><li v-for="(step, index) in join.instructions" :key="index">{{ step }}</li></ol>
        </details>
      </template>
      <a v-else-if="directUrl" class="cmp-button" :class="prominent ? 'cmp-button--primary' : 'cmp-button--secondary'" :href="directUrl">Join server</a>
      <p v-else>Server allocated. Verified player join instructions are not available yet.</p>
    </template>
  </component>
</template>
