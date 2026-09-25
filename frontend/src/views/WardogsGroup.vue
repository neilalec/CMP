<script setup>
import { ref } from 'vue';
import { useGroupView } from '../features/group/composables/useGroupView';
import { useQueueStore } from '../stores/queueStore';

const {
  authStore, groupStore, handleCreate, handleJoin, handleKickMember, handleLeave,
  handleTransferOwnership, getMemberDisplayName, isGroupLeader, joinCode
} = useGroupView();
const queueStore = useQueueStore();
const copyStatus = ref('');
const copyFailed = ref(false);
const copyCode = async () => {
  if (!groupStore.code || !navigator?.clipboard?.writeText) {
    copyStatus.value = 'Copy is unavailable in this browser.';
    copyFailed.value = true;
    return;
  }
  try {
    await navigator.clipboard.writeText(groupStore.code);
    copyStatus.value = 'Group code copied.';
    copyFailed.value = false;
  } catch {
    copyStatus.value = 'Could not copy the group code.';
    copyFailed.value = true;
  }
};
</script>

<template>
  <div class="wardogs-group-page cmp-page cmp-page-content">
    <header class="cmp-page-header"><h1>Group</h1></header>

    <template v-if="!groupStore.inGroup">
      <p v-if="queueStore.inQueue" class="group-queue-note" role="status">Leave the queue from Play before creating or joining a group.</p>
      <div class="group-start">
        <button class="cmp-button cmp-button--primary" type="button" :disabled="groupStore.loading || queueStore.inQueue" :aria-busy="groupStore.loading" @click="handleCreate">{{ groupStore.loading ? 'Working…' : 'Create group' }}</button>
        <span class="group-or" aria-hidden="true">or</span>
        <form class="group-join-control" @submit.prevent="handleJoin"><label for="wardogs-group-code" class="sr-only">Group code</label><input id="wardogs-group-code" v-model="joinCode" class="cmp-input" type="text" placeholder="Group code" maxlength="8" autocomplete="off" :disabled="groupStore.loading || queueStore.inQueue"><button class="cmp-button cmp-button--secondary" type="submit" :disabled="groupStore.loading || queueStore.inQueue">Join group</button></form>
      </div>
    </template>

    <template v-else>
      <p v-if="queueStore.inQueue" class="group-queue-note" role="status">Group is queued. Manage matchmaking from Play.</p>
      <section class="group-overview" aria-label="Your group summary">
        <div class="group-size"><h2>Group · {{ groupStore.members.length }} player{{ groupStore.members.length === 1 ? '' : 's' }}</h2><p>Leader: <strong>{{ getMemberDisplayName(groupStore.leader) }}</strong> · {{ isGroupLeader ? 'You control queueing.' : 'Leader controls queueing.' }}</p></div>
        <div class="group-code"><code :aria-label="`Group code ${groupStore.code}`">{{ groupStore.code }}</code><button class="cmp-button cmp-button--secondary" type="button" aria-label="Copy group code" @click="copyCode">Copy</button><span v-if="copyStatus" class="group-copy-feedback cmp-status" :class="copyFailed ? 'cmp-status--danger' : 'cmp-status--success'" :role="copyFailed ? 'alert' : 'status'">{{ copyStatus }}</span></div>
      </section>

      <section class="group-members" aria-label="Group members"><h2 class="sr-only">Members</h2><ul><li v-for="member in groupStore.members" :key="member" class="cmp-player-row group-member" :class="{ 'is-me': member === authStore.username }"><div class="group-member-name"><strong>{{ getMemberDisplayName(member) }}</strong><span v-if="member === authStore.username">You</span><span v-if="member === groupStore.leader">Leader</span><span v-else>Member</span></div><div v-if="member !== groupStore.leader && isGroupLeader" class="group-member-actions"><button class="cmp-button cmp-button--secondary" type="button" :disabled="groupStore.loading || queueStore.inQueue" @click="handleTransferOwnership(member)">Make leader</button><button class="cmp-button cmp-button--danger" type="button" :disabled="groupStore.loading || queueStore.inQueue" @click="handleKickMember(member)">Kick</button></div></li></ul></section>

      <div class="group-footer"><button class="cmp-button cmp-button--danger" type="button" :disabled="groupStore.loading" @click="handleLeave">Leave group</button></div>
    </template>
    <p v-if="groupStore.error" class="cmp-error-state" role="alert">{{ groupStore.error }}</p>
  </div>
</template>

<style scoped>
.wardogs-group-page { display: grid; gap: var(--cmp-section-gap); max-width: 840px; }
.wardogs-group-page .cmp-page-header { margin: 0; }
.group-queue-note { margin: 0; color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); }
.group-start { display: flex; align-items: center; flex-wrap: wrap; gap: var(--cmp-space-3); }
.group-or { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.group-join-control { display: flex; gap: var(--cmp-space-2); min-width: 0; }
.group-join-control input { flex: 1; min-width: 0; text-transform: uppercase; }
.group-overview { display: flex; align-items: center; justify-content: space-between; gap: var(--cmp-space-5); padding: var(--cmp-space-3) 0; border-bottom: 1px solid var(--cmp-border); }
.group-overview > div:first-child { display: grid; gap: var(--cmp-space-2); min-width: 0; }
.group-size { overflow-wrap: anywhere; }
.group-overview h2 { margin: 0; font-size: 1.5rem; }
.group-overview p:not(.cmp-kicker) { margin: 0; color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); overflow-wrap: anywhere; }
.group-overview p strong { color: var(--cmp-text); }
.group-code { display: flex; align-items: center; flex-wrap: wrap; gap: var(--cmp-space-2); min-width: 0; padding-left: var(--cmp-space-5); border-left: 1px solid var(--cmp-border); }
.group-code code { max-width: 100%; color: var(--cmp-text); font: 700 1.125rem var(--cmp-font-mono); letter-spacing: .04em; overflow-wrap: anywhere; }
.group-code button { justify-self: start; }
.group-copy-feedback { font-size: var(--cmp-type-meta); }
.group-members { display: grid; }
.group-members ul { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--cmp-border); }
.group-member { gap: var(--cmp-space-4); padding: var(--cmp-space-3) var(--cmp-space-2); }
.group-member.is-me { background: color-mix(in srgb, var(--cmp-primary) 8%, transparent); }
.group-member-name { display: flex; align-items: baseline; flex-wrap: wrap; gap: var(--cmp-space-2); min-width: 0; }
.group-member-name strong { overflow-wrap: anywhere; }
.group-member-name span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.group-member-name span:first-of-type { color: var(--cmp-primary-hover); }
.group-member-actions { display: flex; flex-wrap: wrap; gap: var(--cmp-space-2); }
.group-member-actions .cmp-button { min-height: 42px; }
.group-footer { padding-top: var(--cmp-space-3); border-top: 1px solid var(--cmp-border); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 720px) { .group-overview { align-items: flex-start; flex-direction: column; }.group-code { width: 100%; padding: var(--cmp-space-3) 0 0; border-left: 0; border-top: 1px solid var(--cmp-border); } }
@media (max-width: 480px) { .group-start { align-items: stretch; flex-direction: column; }.group-or { text-align: center; }.group-join-control, .group-member { align-items: stretch; flex-direction: column; }.group-join-control button, .group-member-actions .cmp-button { flex: 1; }.group-member-actions { width: 100%; } }
</style>
