<script setup>
import QueuePanel from '../features/home/components/QueuePanel.vue';
import LobbiesPanel from '../features/home/components/LobbiesPanel.vue';
import { useHomeView } from '../features/home/composables/useHomeView';

const {
  MAX_PLAYERS,
  activeView,
  authStore,
  clearQueue,
  getLobbyLabel,
  groupStore,
  isDev,
  isGroupLeader,
  isInGroup,
  isInLobby,
  isQueueFull,
  joinOpenLobby,
  joinQueue,
  leaveQueue,
  loading,
  queueStore,
} = useHomeView();

</script>

<template>
  <div class="home-content content-panel">
      <QueuePanel
        v-if="activeView === 'queue'"
        :players-in-queue="queueStore.playersInQueue"
        :max-players="MAX_PLAYERS"
        :in-queue="queueStore.inQueue"
        :match-accept-active="queueStore.matchAccept.active"
        :loading="loading"
        :is-in-lobby="isInLobby"
        :is-queue-full="isQueueFull"
        :is-in-group="isInGroup"
        :is-group-leader="isGroupLeader"
        :has-steam-id="authStore.hasSteamId"
        :group-member-count="groupStore.members.length"
        :is-dev="isDev"
        @join-queue="joinQueue"
        @leave-queue="leaveQueue"
        @seed-queue="seedQueue(MAX_PLAYERS - 2)"
        @clear-queue="clearQueue"
      />

      <LobbiesPanel
        v-else-if="activeView === 'lobbies'"
        :open-lobbies="queueStore.openLobbies"
        :active-lobbies="queueStore.activeLobbies"
        :loading="loading"
        :is-in-lobby="isInLobby"
        :max-players="MAX_PLAYERS"
        :get-lobby-label="getLobbyLabel"
        @join-lobby="joinOpenLobby"
      />

      <section v-else class="home-about">
        <h1>Competitive Matchmaking Platform</h1>
        <p>
          The purpose of this web app is to allow players to queue for a competitive Squad match.
        </p><p>
          Once a queue is filled, all players must accept the match before setup continues.
        </p><p>
          Once a match is ready, you will be given the server info.
        </p>
      </section>
  </div>
</template>

<style scoped>
.home-content {
  width: min(100%, 1180px);
  max-width: 1180px;
  margin: clamp(20px, 5vw, 56px) auto 0;
}

.home-about {
  width: 100%;
  max-width: 100%;
  text-align: center;
  margin: 1rem 0;
}

.queue-column {
  width: 100%;
  text-align: center;
}

.queue-column h1 {
  text-align: center;
  margin-bottom: 1.5rem;
  color: inherit;
  font-weight: 500;
}

.home-about h1 {
  color: inherit;
  font-weight: 500;
}

.countdown {
  display: block;
  font-size: 1.2em;
  color: #4CAF50;
  font-weight: bold;
  margin: 1rem auto 0;
  line-height: 1.2em;
  width: 100%;
  max-width: 250px;
  text-align: center;
}

.countdown-slot {
  min-height: 1.2em;
  margin-top: 0.5rem;
}

.countdown-slot.is-hidden {
  visibility: hidden;
}

.none-text {
  color: #888;
  margin-top: 1rem;
}
</style>
