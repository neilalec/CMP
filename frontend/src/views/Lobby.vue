<script setup>
import { useLobbyView } from '../features/lobby/composables/useLobbyView';
import LobbyTeamColumn from '../features/lobby/components/LobbyTeamColumn.vue';
import LobbyMatchInfo from '../features/lobby/components/LobbyMatchInfo.vue';
import LobbyMapVoteList from '../features/lobby/components/LobbyMapVoteList.vue';
import LobbyPhaseGrid from '../features/lobby/components/LobbyPhaseGrid.vue';
import LobbyPhaseHeader from '../features/lobby/components/LobbyPhaseHeader.vue';

const {
  activeCountdown,
  activeCountdownLabel,
  authStore,
  canAdminLobby,
  canAutoConnect,
  canDirectConnect,
  connectToServer,
  directConnectToServer,
  forceLiveReady,
  deleteLobby,
  getConnectionFlagClass,
  getConnectionLabel,
  getPlayerDisplayName,
  getTeamLabel,
  groupedTeam1,
  groupedTeam2,
  handleLeaveLobby,
  handleVoteMap,
  isCaptain,
  isCountdownPaused,
  isCurrentUser,
  isDev,
  liveRollGraceSeconds,
  liveRollRequiredCount,
  liveRollRequiredPercent,
  liveRollThresholdSeconds,
  lobbyStore,
  mapOptions,
  showConnectionStatus,
  showPauseButton,
  serverConnectedCount,
  skipPhase,
  toggleCountdownPause,
  prevPhase
} = useLobbyView();
</script>

<template>
  <div class="lobby-page">
    <div class="lobby-shell content-panel">
      <LobbyPhaseHeader
        :active-countdown-label="activeCountdownLabel"
        :active-countdown="activeCountdown"
        :connected-count="serverConnectedCount"
        :required-after-grace-count="liveRollRequiredCount"
        :ready-percent="liveRollRequiredPercent"
        :ready-threshold-seconds="liveRollThresholdSeconds"
        :ready-grace-seconds="liveRollGraceSeconds"
        :ready-grace-remaining-seconds="lobbyStore.liveRollCountdown"
        :total-players="lobbyStore.players.length"
        :announcement="lobbyStore.announcement"
        :server-details="lobbyStore.serverDetails"
        :step="lobbyStore.step"
        :show-pause-button="showPauseButton"
        :is-countdown-paused="isCountdownPaused"
        :can-admin="canAdminLobby"
        :is-dev="isDev"
        :is-spectator="lobbyStore.isSpectator"
        :admin-live-ready-override="lobbyStore.adminLiveReadyOverride"
        @pause="toggleCountdownPause"
        @skip="skipPhase"
        @prev="prevPhase"
        @delete="deleteLobby"
        @force-live-ready="forceLiveReady"
      />

      <div class="lobby-panel">
        <div v-if="lobbyStore.loading" class="loading surface-card">
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
                :get-display-name="getPlayerDisplayName"
                :show-connection-status="showConnectionStatus"
              />
            </template>
            <template #center>
              <LobbyMapVoteList
                :maps="mapOptions"
                :selected-map="lobbyStore.mapVotes[authStore.username]"
                :get-votes-for-map="lobbyStore.getVotesForMap"
                :voted-count="Object.keys(lobbyStore.mapVotes || {}).length"
                :disabled="lobbyStore.isSpectator"
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
                :get-display-name="getPlayerDisplayName"
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
                :get-display-name="getPlayerDisplayName"
                :show-connection-status="showConnectionStatus"
              />
            </template>
            <template #center>
              <LobbyMatchInfo
                :selected-map="lobbyStore.selectedMap"
                server-prefix="Connect Address"
                :server-details="lobbyStore.serverDetails"
                :can-admin="canAdminLobby"
                :auto-connect-available="lobbyStore.step === 3 || lobbyStore.step === 4"
                :auto-connect-enabled="canAutoConnect"
                :direct-connect-available="lobbyStore.step === 3 || lobbyStore.step === 4"
                :direct-connect-enabled="canDirectConnect"
                :is-spectator="lobbyStore.isSpectator"
                @auto-connect="connectToServer"
                @direct-connect="directConnectToServer"
                @leave-lobby="handleLeaveLobby"
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
                :get-display-name="getPlayerDisplayName"
                :show-connection-status="showConnectionStatus"
              />
            </template>
          </LobbyPhaseGrid>
        </div>

        <div v-if="!lobbyStore.loading && lobbyStore.step < 3" class="leave-lobby-card window-panel">
          <div class="leave-lobby-card-body panel-body">
            <button class="leave-lobby-button" type="button" @click="handleLeaveLobby">
              {{ lobbyStore.isSpectator ? 'Stop Spectating' : 'Leave Lobby' }}
            </button>
          </div>
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
  overflow: visible;
}

.lobby-panel {
  width: 100%;
  max-width: 100%;
  margin-inline: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  overflow: visible;
}

.lobby-section {
  padding: clamp(14px, 2.2vw, 24px);
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  --middle-column-width: 300px;
  --phase-column-gap: clamp(12px, 1.6vw, 18px);
  --teams-offset: 0px;
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

.leave-lobby-card {
  width: auto;
  margin: 4px auto 0;
  overflow: visible;
  border: 0;
  background: transparent;
  box-shadow: none;
}

.leave-lobby-card-body {
  display: flex;
  justify-content: center;
  padding: 0;
  background: transparent;
}

.leave-lobby-button {
  width: 200px;
  min-height: 34px;
  background: var(--button-flat-bg);
  border-color: var(--button-border);
  box-shadow: var(--button-shadow);
  color: var(--button-flat-text);
}

.leave-lobby-button:hover {
  background: var(--button-flat-bg-hover);
  border-color: var(--button-border-hover);
  box-shadow: var(--button-hover-shadow);
}

@media (max-width: 1200px) {
  .lobby-section {
    --middle-column-width: 280px;
    --phase-column-gap: 12px;
  }
}

@media (max-width: 768px) {
  .lobby-panel {
    width: 100%;
    margin-inline: 0;
  }

  .lobby-section {
    padding: 12px 8px 16px;
    --middle-column-width: 100%;
    --phase-column-gap: 12px;
  }

  .loading {
    min-height: 260px;
  }

  .leave-lobby-button {
    width: min(100%, 220px);
  }
}

@media (max-width: 420px) {
  .lobby-section {
    padding-inline: 6px;
  }
}
</style>
