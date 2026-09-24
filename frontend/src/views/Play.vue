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
  <div class="play-content cmp-page">
    <header v-if="activeView === 'queue'" class="play-heading">
      <div>
        <p class="play-eyebrow">WARDOGS</p>
        <h1>Matchmaking</h1>
      </div>
      <RouterLink v-if="groupStore.inGroup" class="play-group-link cmp-button cmp-button--secondary" to="/group">
        Your group
      </RouterLink>
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
  min-height: max(560px, calc(100dvh - 154px));
  margin: 0 auto;
  padding: clamp(24px, 4vw, 48px) var(--cmp-page-gutter);
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.play-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  width: min(100%, 580px);
  margin: 0 auto 18px;
}

.play-eyebrow { margin: 0 0 5px; color: var(--cmp-text-muted); font-size: .68rem; font-weight: 800; letter-spacing: .16em; }
.play-heading h1 { margin: 0; font-size: clamp(1.7rem, 3vw, 2.2rem); letter-spacing: -.035em; }
.play-group-link { min-height: 40px; padding: 8px 14px; color: var(--cmp-text-secondary); font-size: .8rem; }
.play-group-link:hover { color: var(--cmp-text); }

@media (max-width: 640px) {
  .play-content {
    min-height: max(500px, calc(100dvh - 132px));
    padding-block: 28px;
  }

  .play-heading {
    margin-bottom: 14px;
  }
}
</style>
