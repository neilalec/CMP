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
  queueStore,
} = useHomeView();
</script>

<template>
  <div class="play-content content-panel page-shell">
    <QueuePanel
      v-if="activeView === 'queue'"
      :in-queue="queueStore.inQueue"
      :current-queue-mode="currentQueueMode"
      :queue-modes="queueModes"
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
      @delete-lobby="deleteLobby"
    />
  </div>
</template>

<style scoped>
.play-content {
  width: min(100%, var(--page-width));
}

@media (max-width: 640px) {
  .play-content {
    margin-top: 0;
    padding: 18px 14px;
  }
}
</style>
