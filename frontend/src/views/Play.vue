<script setup>
import QueuePanel from '../features/home/components/QueuePanel.vue';
import LobbiesPanel from '../features/home/components/LobbiesPanel.vue';
import { useHomeView } from '../features/home/composables/useHomeView';

const {
  activeView,
  authStore,
  canBypassSteamIdForLocalDev,
  canManageQueueTools,
  clearQueue,
  currentQueueMode,
  deleteLobby,
  groupStore,
  isGroupLeader,
  isInGroup,
  isInLobby,
  isModeQueueFull,
  joinOpenLobby,
  joinQueue,
  leaveQueue,
  loading,
  getLobbyLabel,
  getQueueProgressPercent,
  queueModes,
  serverAvailable,
  serverAvailabilityReason,
  seedQueue,
  setQueueEnabled,
  spectateLobby,
  queueStore,
} = useHomeView();
</script>

<template>
  <div class="play-content cmp-page cmp-page-content">
    <header v-if="activeView === 'queue'" class="play-heading cmp-page-header">
      <h1>Play</h1>
    </header>
    <p v-if="activeView === 'queue' && queueStore.error" class="play-feedback cmp-error-state" role="alert">{{ queueStore.error }}</p>
    <p v-if="activeView === 'queue' && !queueModes.length" class="play-feedback cmp-loading-state" role="status">Checking queue availability…</p>
    <QueuePanel
      v-if="activeView === 'queue' && queueModes.length"
      :in-queue="queueStore.inQueue"
      :current-queue-mode="currentQueueMode"
      :queue-modes="queueModes"
      :wardogs-lobby-id="queueStore.wardogsLobbyId"
      :match-accept-active="queueStore.matchAccept.active"
      :loading="loading"
      :is-in-lobby="isInLobby"
      :is-in-group="isInGroup"
      :is-group-leader="isGroupLeader"
      :has-steam-id="authStore.hasSteamId || canBypassSteamIdForLocalDev"
      :group-member-count="groupStore.members.length"
      :can-manage-queue-tools="canManageQueueTools"
      :server-available="serverAvailable"
      :server-availability-reason="serverAvailabilityReason"
      :get-queue-progress-percent="getQueueProgressPercent"
      :is-mode-queue-full="isModeQueueFull"
      @join-queue="joinQueue"
      @leave-queue="leaveQueue"
      @seed-queue="seedQueue"
      @clear-queue="clearQueue"
      @set-queue-enabled="setQueueEnabled"
    />

    <LobbiesPanel
      v-else-if="activeView === 'lobbies'"
      :open-lobbies="queueStore.openLobbies"
      :active-lobbies="queueStore.activeLobbies"
      :loading="loading"
      :is-in-lobby="isInLobby"
      :is-admin="authStore.isAdmin"
      :get-lobby-label="getLobbyLabel"
      @join-lobby="joinOpenLobby"
      @spectate-lobby="spectateLobby"
      @delete-lobby="deleteLobby"
    />
  </div>
</template>

<style scoped>
.play-content {
  display: block;
}

.play-heading {
  width: min(100%, 620px);
  margin: 0 auto var(--cmp-space-5);
}

.play-heading > p:last-child { font-size: .9rem; }
.play-feedback { width: min(100%, 620px); margin: 0 auto var(--cmp-space-4); }

@media (max-width: 640px) {
  .play-heading { margin-bottom: var(--cmp-space-4); }
}
</style>
