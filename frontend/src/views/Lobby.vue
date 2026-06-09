<script setup>
import { useLobbyView } from '../features/lobby/composables/useLobbyView';
import LobbyTeamColumn from '../features/lobby/components/LobbyTeamColumn.vue';
import LobbyMatchInfo from '../features/lobby/components/LobbyMatchInfo.vue';
import LobbyMapVoteList from '../features/lobby/components/LobbyMapVoteList.vue';
import LobbyPhaseGrid from '../features/lobby/components/LobbyPhaseGrid.vue';
import LobbyPhaseHeader from '../features/lobby/components/LobbyPhaseHeader.vue';
import MatchPhaseTracker from '../features/match/components/MatchPhaseTracker.vue';

const {
  activeCountdown,
  activeCountdownLabel,
  authStore,
  canAdminLobby,
  canAutoConnect,
  connectToServer,
  deleteLobby,
  getConnectionFlagClass,
  getConnectionLabel,
  getTeamLabel,
  groupedTeam1,
  groupedTeam2,
  handleLeaveLobby,
  handleVoteMap,
  isCaptain,
  isCountdownPaused,
  isCurrentUser,
  isDev,
  lobbyStore,
  lobbyPhase,
  mapOptions,
  matchSizeLabel,
  phaseTitle,
  showConnectionStatus,
  showPauseButton,
  skipPhase,
  toggleCountdownPause,
  prevPhase
} = useLobbyView();
</script>

<template>
  <div class="lobby-page">
    <div class="lobby-shell content-panel">
      <LobbyPhaseHeader
        :phase-title="phaseTitle"
        :active-countdown-label="activeCountdownLabel"
        :active-countdown="activeCountdown"
        :announcement="lobbyStore.announcement"
        :show-pause-button="showPauseButton"
        :is-countdown-paused="isCountdownPaused"
        :can-admin="canAdminLobby"
        :is-dev="isDev"
        @pause="toggleCountdownPause"
        @skip="skipPhase"
        @prev="prevPhase"
        @leave="handleLeaveLobby"
        @delete="deleteLobby"
      />

      <div class="lobby-tracker window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Match Progress</span>
          <span class="window-titlebar-meta">{{ matchSizeLabel || 'Lobby' }}</span>
        </div>
        <div class="lobby-tracker-body">
          <MatchPhaseTracker :current-phase="lobbyPhase" />
        </div>
      </div>

      <div class="lobby-panel window-panel">
        <div class="window-titlebar">
          <span class="window-titlebar-label">Teams</span>
          <span class="window-titlebar-meta">{{ lobbyStore.selectedMap || phaseTitle }}</span>
        </div>
        <div v-if="lobbyStore.loading" class="loading">
          Loading lobby...
        </div>

        <div v-else-if="lobbyStore.step === 2" class="lobby-section">
          <LobbyPhaseGrid>
            <template #left>
              <LobbyTeamColumn
                team-key="team1"
                :team-label="getTeamLabel('team1')"
                :groups="groupedTeam1"
                :is-current-user="isCurrentUser"
                :is-captain="isCaptain"
                :get-connection-flag-class="getConnectionFlagClass"
                :get-connection-label="getConnectionLabel"
                :show-connection-status="showConnectionStatus"
              />
            </template>
            <template #center>
              <LobbyMapVoteList
                :maps="mapOptions"
                :selected-map="lobbyStore.mapVotes[authStore.username]"
                :get-votes-for-map="lobbyStore.getVotesForMap"
                @vote="handleVoteMap"
              />
            </template>
            <template #right>
              <LobbyTeamColumn
                team-key="team2"
                :team-label="getTeamLabel('team2')"
                :groups="groupedTeam2"
                :is-current-user="isCurrentUser"
                :is-captain="isCaptain"
                :get-connection-flag-class="getConnectionFlagClass"
                :get-connection-label="getConnectionLabel"
                :show-connection-status="showConnectionStatus"
              />
            </template>
          </LobbyPhaseGrid>
        </div>

        <div v-else-if="lobbyStore.step >= 3" class="lobby-section">
          <LobbyPhaseGrid layout-class="match-ready-layout">
            <template #left>
              <LobbyTeamColumn
                team-key="team1"
                :team-label="getTeamLabel('team1')"
                :groups="groupedTeam1"
                :is-current-user="isCurrentUser"
                :is-captain="isCaptain"
                :get-connection-flag-class="getConnectionFlagClass"
                :get-connection-label="getConnectionLabel"
                :show-connection-status="showConnectionStatus"
              />
            </template>
            <template #center>
              <LobbyMatchInfo
                :match-size-label="matchSizeLabel"
                :selected-map="lobbyStore.selectedMap"
                server-prefix="Connect Address"
                :server-details="lobbyStore.serverDetails"
                :auto-connect-available="lobbyStore.step === 3 || lobbyStore.step === 4"
                :auto-connect-enabled="canAutoConnect"
                @auto-connect="connectToServer"
              />
            </template>
            <template #right>
              <LobbyTeamColumn
                team-key="team2"
                :team-label="getTeamLabel('team2')"
                :groups="groupedTeam2"
                :is-current-user="isCurrentUser"
                :is-captain="isCaptain"
                :get-connection-flag-class="getConnectionFlagClass"
                :get-connection-label="getConnectionLabel"
                :show-connection-status="showConnectionStatus"
              />
            </template>
          </LobbyPhaseGrid>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lobby-page {
  width: 100%;
  min-height: 100%;
  padding: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
}

.lobby-shell {
  width: 100%;
  max-width: 100%;
  min-height: 100%;
  height: auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  position: relative;
  padding: 0px 0px 20px;
  align-self: stretch;
}

.lobby-panel {
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  overflow: hidden;
}

.lobby-section {
  padding: clamp(16px, 3vw, 30px);
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  --middle-column-width: 280px;
  --phase-column-gap: clamp(20px, 3vw, 56px);
  --teams-offset: 0px;
}

.lobby-tracker {
  width: min(100%, 920px);
  margin: 4px auto 0;
}

.lobby-tracker-body {
  padding: 12px clamp(14px, 3vw, 24px);
}

.loading {
  text-align: center;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
  width: 100%;
  color: inherit;
}

@media (max-width: 1200px) {
  .lobby-section {
    --middle-column-width: 240px;
    --phase-column-gap: 24px;
  }
}
</style>
