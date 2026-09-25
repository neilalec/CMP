<script setup>
import { ref } from 'vue';
import { useGroupView } from '../features/group/composables/useGroupView';
import { useQueueStore } from '../stores/queueStore';

const {
  authStore, groupStore, handleCreate, handleJoin, handleKickMember, handleLeave,
  handleSeedGroup, handleTransferOwnership, getMemberDisplayName, isGroupLeader,
  joinCode, seedCount
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
    <header class="cmp-page-header"><p class="cmp-kicker">Premade</p><h1>Group</h1><p>{{ groupStore.inGroup ? 'Manage your group before joining matchmaking.' : 'Queue alone, or bring players together.' }}</p></header>

    <template v-if="!groupStore.inGroup">
      <p v-if="queueStore.inQueue" class="cmp-status cmp-status--warning group-queue-note" role="status">Leave the queue before creating or joining a group.</p>
      <div class="group-start cmp-surface">
        <section aria-labelledby="group-create-title"><p class="cmp-kicker">Start a premade</p><h2 id="group-create-title">Create a group</h2><p>Get a code to share with your players.</p><button class="cmp-button cmp-button--primary" type="button" :disabled="groupStore.loading || queueStore.inQueue" :aria-busy="groupStore.loading" @click="handleCreate">{{ groupStore.loading ? 'Working…' : 'Create group' }}</button></section>
        <section aria-labelledby="group-join-title"><p class="cmp-kicker">Have a code?</p><h2 id="group-join-title">Join a group</h2><form class="group-join-control" @submit.prevent="handleJoin"><label for="wardogs-group-code" class="sr-only">Group code</label><input id="wardogs-group-code" v-model="joinCode" class="cmp-input" type="text" placeholder="Group code" maxlength="8" autocomplete="off" :disabled="groupStore.loading || queueStore.inQueue"><button class="cmp-button cmp-button--secondary" type="submit" :disabled="groupStore.loading || queueStore.inQueue">Join group</button></form></section>
      </div>
    </template>

    <template v-else>
      <section class="group-overview cmp-surface" aria-label="Your group summary">
        <div><p class="cmp-kicker">Your premade</p><h2>{{ groupStore.members.length }} player{{ groupStore.members.length === 1 ? '' : 's' }}</h2><p>Leader: <strong>{{ getMemberDisplayName(groupStore.leader) }}</strong> · {{ isGroupLeader ? 'You control queueing for this group.' : 'Only the group leader controls queueing.' }}</p><p v-if="queueStore.inQueue" class="cmp-status cmp-status--success">You are in queue.</p></div>
        <div class="group-code"><span class="cmp-kicker">Group code</span><code>{{ groupStore.code }}</code><button class="cmp-button cmp-button--secondary" type="button" @click="copyCode">Copy code</button><span v-if="copyStatus" class="group-copy-feedback cmp-status" :class="copyFailed ? 'cmp-status--danger' : 'cmp-status--success'" :role="copyFailed ? 'alert' : 'status'">{{ copyStatus }}</span></div>
      </section>

      <section class="group-members" aria-label="Group members"><div class="cmp-section-header"><h2>Members</h2><p>{{ groupStore.members.length }} in group</p></div><ul><li v-for="member in groupStore.members" :key="member" class="cmp-player-row group-member" :class="{ 'is-me': member === authStore.username }"><div class="group-member-name"><strong>{{ getMemberDisplayName(member) }}</strong><span v-if="member === authStore.username">You</span><span v-if="member === groupStore.leader">Leader</span></div><div v-if="member !== groupStore.leader && isGroupLeader" class="group-member-actions"><button class="cmp-button cmp-button--secondary" type="button" :disabled="groupStore.loading" @click="handleTransferOwnership(member)">Make leader</button><button class="cmp-button cmp-button--danger" type="button" :disabled="groupStore.loading" @click="handleKickMember(member)">Kick</button></div></li></ul></section>

      <details v-if="authStore.isAdmin" class="group-admin cmp-disclosure"><summary>Admin seeding</summary><div><label for="wardogs-seed-count">Bots to add</label><input id="wardogs-seed-count" v-model.number="seedCount" class="cmp-input" type="number" min="1" step="1" inputmode="numeric"><button class="cmp-button cmp-button--secondary" type="button" :disabled="groupStore.loading" @click="handleSeedGroup">Add to group</button></div></details>
      <div class="group-footer"><button class="cmp-button cmp-button--danger" type="button" :disabled="groupStore.loading" @click="handleLeave">Leave group</button></div>
    </template>
    <p v-if="groupStore.error" class="cmp-error-state" role="alert">{{ groupStore.error }}</p>
  </div>
</template>

<style scoped>
.wardogs-group-page { display: grid; gap: var(--cmp-section-gap); max-width: 1000px; }
.wardogs-group-page .cmp-page-header { margin: 0; }
.group-queue-note { margin: 0; }
.group-start { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); border-top: 3px solid var(--cmp-primary); }
.group-start section { display: grid; align-content: start; gap: var(--cmp-space-3); min-width: 0; padding: var(--cmp-space-5); }
.group-start section + section { border-left: 1px solid var(--cmp-border); }
.group-start h2 { margin: 0; font-size: var(--cmp-type-section); }
.group-start section > p:not(.cmp-kicker) { margin: 0; color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); }
.group-start section > button { justify-self: start; }
.group-join-control { display: flex; gap: var(--cmp-space-2); min-width: 0; }
.group-join-control input { flex: 1; min-width: 0; text-transform: uppercase; }
.group-overview { display: flex; align-items: start; justify-content: space-between; gap: var(--cmp-space-5); padding: var(--cmp-space-5); border-top: 3px solid var(--cmp-primary); }
.group-overview > div:first-child { display: grid; gap: var(--cmp-space-2); min-width: 0; }
.group-overview h2 { margin: 0; font-size: 1.5rem; }
.group-overview p:not(.cmp-kicker) { margin: 0; color: var(--cmp-text-secondary); font-size: var(--cmp-type-meta); overflow-wrap: anywhere; }
.group-overview p strong { color: var(--cmp-text); }
.group-code { display: grid; gap: var(--cmp-space-2); min-width: 200px; padding-left: var(--cmp-space-5); border-left: 1px solid var(--cmp-border); }
.group-code code { color: var(--cmp-text); font: 700 1.125rem var(--cmp-font-mono); letter-spacing: .04em; overflow-wrap: anywhere; }
.group-code button { justify-self: start; }
.group-copy-feedback { font-size: var(--cmp-type-meta); }
.group-members { display: grid; gap: var(--cmp-space-3); }
.group-members .cmp-section-header { margin: 0; }
.group-members ul { margin: 0; padding: 0; list-style: none; border-top: 1px solid var(--cmp-border); }
.group-member { gap: var(--cmp-space-4); padding: var(--cmp-space-3) var(--cmp-space-2); }
.group-member.is-me { background: color-mix(in srgb, var(--cmp-primary) 8%, transparent); }
.group-member-name { display: flex; align-items: baseline; flex-wrap: wrap; gap: var(--cmp-space-2); min-width: 0; }
.group-member-name strong { overflow-wrap: anywhere; }
.group-member-name span { color: var(--cmp-text-muted); font-size: var(--cmp-type-meta); }
.group-member-name span:first-of-type { color: var(--cmp-primary-hover); }
.group-member-actions { display: flex; flex-wrap: wrap; gap: var(--cmp-space-2); }
.group-member-actions .cmp-button { min-height: 42px; }
.group-admin { font-size: var(--cmp-type-meta); }
.group-admin > div { display: flex; align-items: center; flex-wrap: wrap; gap: var(--cmp-space-2); padding: var(--cmp-space-3) 0; }
.group-admin input { width: 92px; }
.group-footer { padding-top: var(--cmp-space-3); border-top: 1px solid var(--cmp-border); }
.sr-only { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
@media (max-width: 720px) { .group-start { grid-template-columns: 1fr; }.group-start section + section { border-left: 0; border-top: 1px solid var(--cmp-border); }.group-overview { flex-direction: column; }.group-code { width: 100%; min-width: 0; padding: var(--cmp-space-4) 0 0; border-left: 0; border-top: 1px solid var(--cmp-border); } }
@media (max-width: 480px) { .group-start section, .group-overview { padding: var(--cmp-space-4); }.group-join-control, .group-member { align-items: stretch; flex-direction: column; }.group-join-control button, .group-member-actions .cmp-button { flex: 1; }.group-member-actions { width: 100%; } }
</style>
