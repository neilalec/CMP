<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useGroupStore } from '../../../stores/groupStore'

defineProps({
  actionsDisabled: { type: Boolean, default: false },
  isInGroup: { type: Boolean, default: false },
  isGroupLeader: { type: Boolean, default: false }
})

const groupStore = useGroupStore()
const leaderName = computed(() => groupStore.getDisplayName(groupStore.leader) || groupStore.leader || 'Unknown')
</script>

<template>
  <div class="wardogs-play-group" aria-label="Your group">
    <div class="wardogs-play-group-summary">
      <strong v-if="isInGroup">Group of {{ groupStore.members.length }}</strong>
      <strong v-else>Solo</strong>
      <span v-if="isInGroup">Leader: {{ leaderName }} · {{ isGroupLeader ? 'You control queueing' : 'Leader controls queueing' }}</span>
    </div>
    <RouterLink v-if="isInGroup" to="/group">Manage group</RouterLink>
    <div v-else class="wardogs-play-group-actions">
      <RouterLink to="/group">Create group</RouterLink>
      <RouterLink to="/group">Join group</RouterLink>
    </div>
  </div>
</template>

<style scoped>
.wardogs-play-group { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--cmp-space-2) var(--cmp-space-4); padding: var(--cmp-space-3) 0; border-block: 1px solid var(--cmp-border); }
.wardogs-play-group-summary { display: flex; align-items: baseline; flex-wrap: wrap; gap: var(--cmp-space-1) var(--cmp-space-3); color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); }
.wardogs-play-group-summary strong { color: var(--cmp-text); font-size: 1rem; }
.wardogs-play-group-actions { display: flex; flex-wrap: wrap; gap: var(--cmp-space-3); }
.wardogs-play-group a { color: var(--cmp-primary-hover); font-size: var(--cmp-type-meta); font-weight: 700; }
@media (max-width: 480px) { .wardogs-play-group { align-items: start; flex-direction: column; } }
</style>
