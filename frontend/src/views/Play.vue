<script setup>
import { RouterLink } from 'vue-router';
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
  <div class="play-content content-panel page-shell">
    <header v-if="activeView === 'queue'" class="play-heading">
      <div>
        <h1>Play</h1>
      </div>
      <RouterLink class="play-group-link" to="/group">{{ groupStore.inGroup ? 'Your group' : 'Group' }}</RouterLink>
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
  width: min(100%, var(--page-width));
}

.play-heading {
  display: flex;
  align-items: end;
  justify-content: space-between;
  gap: 16px;
  padding: clamp(8px, 2vw, 26px) 0 24px;
}

.play-heading .eyebrow { margin-bottom: 8px; }
.play-heading h1 { margin: 0; font-size: clamp(2rem, 4vw, 3rem); letter-spacing: -.03em; }
.play-group-link { color: var(--text-secondary); font-size: .84rem; font-weight: 700; }
.play-group-link:hover { color: var(--text-primary); }

@media (max-width: 640px) {
  .play-content {
    margin-top: 0;
    padding: var(--page-gutter);
  }
}
</style>
