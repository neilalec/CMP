<script setup>
import { computed, ref } from 'vue'
import { useAuthStore } from '../../../stores/authStore'
import { useGroupStore } from '../../../stores/groupStore'
import { useRootStore } from '../../../stores/rootStore'

const props = defineProps({
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
    <template v-if="isInGroup">
      <div class="wardogs-play-group-summary" role="status">
        <strong>{{ groupStore.members.length }} player{{ groupStore.members.length === 1 ? '' : 's' }}</strong>
        <span>Leader: {{ leaderName }}</span>
        <span>{{ isGroupLeader ? 'You control queueing for this group.' : 'Only the group leader controls queueing.' }}</span>
      </div>
      <RouterLink class="wardogs-play-manage cmp-button cmp-button--secondary" to="/group">Manage group</RouterLink>
    </template>
    <template v-else>
      <div class="wardogs-play-group-summary" role="status">
        <strong>Solo</strong>
        <span>{{ actionsDisabled ? 'Group changes are unavailable while queued or in a match.' : 'Queue on your own or bring a group.' }}</span>
      </div>
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
.wardogs-play-group { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 10px 0; border-block: 1px solid var(--cmp-border); }
.wardogs-play-group-summary { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 14px; min-width: 0; color: var(--cmp-text-secondary); font-size: .8rem; }
.wardogs-play-group-summary strong { color: var(--cmp-text); font-size: .9rem; }
.wardogs-play-group-actions { display: flex; flex-wrap: wrap; align-items: center; justify-content: flex-end; gap: 8px; }
.wardogs-play-join { display: flex; gap: 6px; }
.wardogs-play-group button, .wardogs-play-manage { min-height: 36px; padding: 7px 11px; font-size: .76rem; white-space: nowrap; }
.wardogs-play-join input { width: 118px; min-height: 36px; padding: 6px 8px; font-size: .78rem; }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 640px) {
  .wardogs-play-group { align-items: stretch; flex-direction: column; }
  .wardogs-play-group-actions { justify-content: stretch; }
  .wardogs-play-group-actions > button, .wardogs-play-join { flex: 1 1 100%; }
  .wardogs-play-join input { flex: 1; width: auto; min-width: 0; }
}
</style>
