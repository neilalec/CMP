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
  <div class="play-content cmp-page">
    <header v-if="activeView === 'queue'" class="play-heading">
      <h1>Play WARDOGS</h1>
    </header>
    <QueuePanel
      v-if="activeView === 'queue'"
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
  width: min(100%, var(--cmp-page-width));
  min-height: 0;
  margin: 0 auto;
  padding: clamp(20px, 3vw, 32px) var(--cmp-page-gutter);
  display: flex;
  flex-direction: column;
}

.play-heading {
  display: flex;
  align-items: baseline;
  width: min(100%, 760px);
  margin: 0 auto 12px;
}

.play-heading h1 { margin: 0; font-size: clamp(1.45rem, 2.5vw, 1.8rem); letter-spacing: -.035em; }

@media (max-width: 640px) {
  .play-content {
    padding-block: 20px;
  }

  .play-heading {
    margin-bottom: 14px;
  }
}
</style>
