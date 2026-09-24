<script setup>
import { computed, ref } from 'vue'
import { useAuthStore } from '../../../stores/authStore'
import { useGroupStore } from '../../../stores/groupStore'
import { useRootStore } from '../../../stores/rootStore'

defineProps({
  actionsDisabled: { type: Boolean, default: false },
  isInGroup: { type: Boolean, default: false },
  isGroupLeader: { type: Boolean, default: false }
})

const authStore = useAuthStore()
const groupStore = useGroupStore()
const rootStore = useRootStore()
const joinCode = ref('')
const leaderName = computed(() => groupStore.getDisplayName(groupStore.leader) || groupStore.leader || 'Unknown')
const join = async () => {
  const code = joinCode.value.trim().toUpperCase()
  if (!code) {
    rootStore.setError('Enter a group code.')
    return
  }
  try {
    await groupStore.joinGroup(authStore.username, code)
    joinCode.value = ''
  } catch (error) {
    rootStore.setError(error.message || 'Failed to join group')
  }
}
const create = async () => {
  try {
    await groupStore.createGroup(authStore.username)
  } catch (error) {
    rootStore.setError(error.message || 'Failed to create group')
  }
}
</script>

<template>
  <section class="wardogs-play-group" aria-label="Your group">
    <div class="wardogs-play-group-summary" role="status">
      <p class="cmp-kicker">Your session</p>
      <template v-if="isInGroup">
        <strong>Group of {{ groupStore.members.length }}</strong>
        <span>Leader: {{ leaderName }}</span>
        <span>{{ isGroupLeader ? 'You control queueing for this group.' : 'Only the group leader controls queueing.' }}</span>
      </template>
      <template v-else>
        <strong>Solo</strong>
        <span>{{ actionsDisabled ? 'Group changes are unavailable while queued or in a match.' : 'Queue alone or bring a group.' }}</span>
      </template>
    </div>
    <template v-if="isInGroup">
      <RouterLink class="wardogs-play-manage cmp-button cmp-button--secondary" to="/group">Manage group</RouterLink>
    </template>
    <template v-else>
      <div class="wardogs-play-group-actions" aria-label="Group actions">
        <button class="cmp-button cmp-button--secondary" type="button" :disabled="actionsDisabled || groupStore.loading" @click="create">
          {{ groupStore.loading ? 'Working…' : 'Create group' }}
        </button>
        <form class="wardogs-play-join" @submit.prevent="join">
          <label class="sr-only" for="wardogs-play-group-code">Group code</label>
          <input id="wardogs-play-group-code" v-model="joinCode" class="cmp-input" type="text" placeholder="Group code" maxlength="8" autocomplete="off" :disabled="actionsDisabled || groupStore.loading">
          <button class="cmp-button cmp-button--secondary" type="submit" :disabled="actionsDisabled || groupStore.loading">
            Join group
          </button>
        </form>
      </div>
    </template>
  </section>
</template>

<style scoped>
.wardogs-play-group { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-4); padding: var(--cmp-space-4) 0; border-block: 1px solid var(--cmp-border); }
.wardogs-play-group-summary { display: grid; gap: var(--cmp-space-1); min-width: 0; color: var(--cmp-text-secondary); font-size: .8125rem; line-height: 1.35; }
.wardogs-play-group-summary strong { color: var(--cmp-text); font-size: 1rem; }
.wardogs-play-group-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: var(--cmp-space-2); }
.wardogs-play-join { display: flex; gap: var(--cmp-space-2); }
.wardogs-play-group button, .wardogs-play-manage { min-height: 42px; padding: 9px 12px; font-size: .8125rem; white-space: nowrap; }
.wardogs-play-join input { width: 112px; min-height: 42px; font-size: .8125rem; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 600px) {
  .wardogs-play-group { align-items: stretch; flex-direction: column; }
  .wardogs-play-group-actions { justify-content: stretch; }
  .wardogs-play-group-actions > button, .wardogs-play-join { flex: 1 1 100%; }
  .wardogs-play-join input { flex: 1; width: auto; min-width: 0; }
  .wardogs-play-manage { align-self: flex-start; }
}
</style>
