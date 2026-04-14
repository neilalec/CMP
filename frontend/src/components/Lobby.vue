<script setup>
import { onMounted, onBeforeUnmount, ref, computed } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { useLobbyStore } from '../stores/lobbyStore';
import { useSocketStore } from '../stores/socketStore';
import { useRootStore } from '../stores/rootStore';
import { useAuthStore } from '../stores/authStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';

const router = useRouter();
const route = useRoute();
const lobbyStore = useLobbyStore();
const socketStore = useSocketStore();
const rootStore = useRootStore();
const authStore = useAuthStore();
const isCountdownPaused = ref(false);

// Fallback only; real map pool comes from server per lobby
const AVAILABLE_MAPS = [
  'Al Basrah Skirmish v1',
  'Belaya Skirmish v1',
  'Chora Skirmish v1',
  "Fool's Road Skirmish v1",
  'Narva Skirmish v1'
];

const listeners = ref([]);
const activeCountdown = computed(() => {
  if (lobbyStore.step === 2) {
    return lobbyStore.votingCountdown;
  }
  return null;
});
const activeCountdownLabel = computed(() => {
  if (lobbyStore.step === 2) {
    return 'Map selected in';
  }
  return 'Match starting in';
});
const phaseTitle = computed(() => {
  if (lobbyStore.loading) return 'Loading Lobby...';
  if (lobbyStore.step === 2) return 'Map Voting';
  if (lobbyStore.step === 3) return 'Match Ready';
  if (lobbyStore.step === 4) return 'Server Details';
  return 'Lobby';
});
const showPauseButton = computed(() => activeCountdown.value !== null);
const mapOptions = computed(() => {
  return lobbyStore.mapPool?.length ? lobbyStore.mapPool : AVAILABLE_MAPS;
});
const isDev = import.meta.env.DEV;

// LIFECYCLE HOOKS
onMounted(async () => {
  const lobbyId = route.params.lobbyId;
  console.log('Lobby component mounted. ID:', lobbyId);
  if (lobbyStore.lobbyId && lobbyStore.lobbyId !== lobbyId) {
    lobbyStore.reset();
  }
  const hasCachedLobby = lobbyStore.lobbyId === lobbyId && lobbyStore.players?.length;
  lobbyStore.loading = !hasCachedLobby;
  
  try {
    // Wait for socket connection
    let attempts = 0;
    while (!socketStore.isConnected) {
      await new Promise(resolve => setTimeout(resolve, 100));
      if (attempts++ > 50) {
        throw new Error('Socket connection timeout');
      }
    }

    // Setup all listeners at once
    const setupListeners = () => {
      const events = [
        {
          event: SOCKET_EVENTS.LOBBY.UPDATE,
          handler: (data) => {
            console.log('Lobby update received:', data);
            if (data.teams && (data.teams.team1?.length || data.teams.team2?.length)) {
              lobbyStore.updateTeams(data.teams);
            }
            lobbyStore.updateLobbyState(data);
          }
        },
        {
          event: SOCKET_EVENTS.LOBBY.COUNTDOWN.VOTING,
          handler: (data) => {
            console.log('Received voting countdown update:', data);
            if (data.countdown !== undefined) {
              lobbyStore.updateVotingCountdown(data.countdown);
            }
            if (data.map_pool) {
              lobbyStore.updateMapPool(data.map_pool);
            }
            if (data.map_votes) {
              lobbyStore.updateMapVotes(data.map_votes);
            }
            if (data.vote_counts) {
              lobbyStore.updateVoteCounts(data.vote_counts);
            }
          }
        },
        {
          event: SOCKET_EVENTS.LOBBY.MAP_SELECTED,
          handler: async (data) => {
            console.log('Map selected:', data);
            await socketStore.emit(SOCKET_EVENTS.LOBBY.GET_DATA, { lobby_id: lobbyId });
            lobbyStore.updateLobbyState({
              selectedMap: data.map,
              step: 3,
              votingCountdown: null  // Reset countdown when map is selected
            });
          }
        },
        {
          event: SOCKET_EVENTS.LOBBY.READY,
          handler: (data) => {
            lobbyStore.updateLobbyState({
              ...data,
              step: 4
            });
          }
        },
        {
          event: 'player_disconnected',
          handler: (data) => {
            console.log('Player disconnected:', data);
            if (data.username === authStore.username) {
              // If we're the one who disconnected, handle accordingly
              lobbyStore.handleDisconnect();
            } else {
              // Otherwise just update the lobby state
              lobbyStore.updatePlayerStatus(data.username, 'disconnected');
            }
          }
        },
        {
          event: 'player_reconnected',
          handler: (data) => {
            console.log('Player reconnected:', data);
            lobbyStore.updatePlayerStatus(data.username, 'connected');
          }
        },
        {
          event: 'player_left',
          handler: (data) => {
            console.log('Player left:', data);
            lobbyStore.removePlayer(data.username);
          }
        }
      ];

      // Register all listeners
      events.forEach(({ event, handler }) => {
        socketStore.on(event, handler);
        listeners.value.push({ event, handler });
      });
    };

    setupListeners();

    socketStore.on(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE, (data) => {
      if (data && typeof data.paused === 'boolean') {
        isCountdownPaused.value = data.paused;
      }
    });
    try {
      const response = await socketStore.emit(SOCKET_EVENTS.COUNTDOWN.STATUS);
      if (response && typeof response.paused === 'boolean') {
        isCountdownPaused.value = response.paused;
      }
    } catch (error) {
      // ignore
    }
    
    // Try to join/rejoin lobby
    const joinResponse = await socketStore.emit(SOCKET_EVENTS.LOBBY.JOIN, { 
      lobby_id: lobbyId,
      username: authStore.username,
      rejoin: true  // flag to indicate possible reconnection
    });
    
    console.log('Join lobby response:', joinResponse);
    
    if (joinResponse?.success) {  // Check for success flag
      lobbyStore.updateLobbyState(joinResponse.data);
    } else {
      throw new Error(joinResponse?.message || 'Failed to join lobby');
    }

  } catch (error) {
    console.error('Error joining lobby:', error);
    rootStore.setError({
      message: 'Failed to join lobby',
      details: error.message,
      context: 'lobby-join'
    });
    router.push('/');
  } finally {
    lobbyStore.loading = false;
  }
});

onBeforeUnmount(() => {
  // Remove all listeners
  listeners.value.forEach(({ event, handler }) => {
    socketStore.off(event, handler);
  });
  listeners.value = [];
  lobbyStore.reset();
  socketStore.off(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE);
});

// METHODS
const handleVoteMap = async (map) => {
  try {
    console.log('Voting for map:', map);
    const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.VOTE_MAP, {
      lobby_id: lobbyStore.lobbyId,
      map
    });
    console.log('Vote response:', response);
    // Update local state immediately for better UX
    lobbyStore.mapVotes[authStore.username] = map;
  } catch (error) {
    console.error('Error voting for map:', error);
    rootStore.setError({
      message: 'Failed to vote for map',
      details: error.message,
      context: 'lobby-vote'
    });
  }
};

const handleLeaveLobby = async () => {
  try {
    const lobbyId = lobbyStore.lobbyId || route.params.lobbyId;
    if (!lobbyId) return;
    const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.LEAVE, {
      lobby_id: lobbyId,
      username: authStore.username
    });
    if (response?.success) {
      lobbyStore.leaveLobby();
      localStorage.removeItem('currentLobby');
      localStorage.removeItem('currentLobbyCaptains');
      router.push('/');
    } else {
      throw new Error(response?.message || 'Failed to leave lobby');
    }
  } catch (error) {
    rootStore.setError({
      message: 'Failed to leave lobby',
      details: error.message,
      context: 'lobby-leave'
    });
  }
};

const toggleCountdownPause = async () => {
  const nextPaused = !isCountdownPaused.value;
  isCountdownPaused.value = nextPaused;
  try {
    const response = await socketStore.emit(SOCKET_EVENTS.COUNTDOWN.TOGGLE_PAUSE, {
      paused: nextPaused
    });
    if (response && typeof response.paused === 'boolean') {
      isCountdownPaused.value = response.paused;
    }
  } catch (error) {
    isCountdownPaused.value = !nextPaused;
    rootStore.setError({
      message: 'Failed to toggle countdown pause',
      details: error.message,
      context: 'countdown-pause'
    });
  }
};

const skipPhase = async () => {
  try {
    await socketStore.emit(SOCKET_EVENTS.LOBBY.SKIP_PHASE, {
      lobby_id: lobbyStore.lobbyId
    });
  } catch (error) {
    rootStore.setError({
      message: 'Failed to skip phase',
      details: error.message,
      context: 'lobby-skip'
    });
  }
};

const prevPhase = async () => {
  try {
    await socketStore.emit(SOCKET_EVENTS.LOBBY.PREV_PHASE, {
      lobby_id: lobbyStore.lobbyId
    });
  } catch (error) {
    rootStore.setError({
      message: 'Failed to go back a phase',
      details: error.message,
      context: 'lobby-prev'
    });
  }
};

const isCaptain = (player, teamKey) => {
  return lobbyStore.captains?.[teamKey] === player;
};

const isCurrentUser = (player) => {
  return player === authStore.username;
};

const groupPlayers = (players) => {
  const groups = {};
  const segments = [];
  const mapping = lobbyStore.playerGroups || {};
  (players || []).forEach((player) => {
    const code = mapping[player];
    if (code) {
      if (!groups[code]) {
        groups[code] = { id: code, members: [] };
        segments.push(groups[code]);
      }
      groups[code].members.push(player);
    } else {
      segments.push({ id: null, members: [player] });
    }
  });
  return segments;
};

const getTeamLabel = (teamKey) => {
  return teamKey === 'team1' ? 'BLUFOR' : 'OPFOR';
};

const matchSizeLabel = computed(() => {
  const team1Count = lobbyStore.teams?.team1?.length || 0;
  const team2Count = lobbyStore.teams?.team2?.length || 0;
  if (team1Count || team2Count) {
    return `${team1Count}v${team2Count}`;
  }
  const total = lobbyStore.players?.length || 0;
  if (!total) return '';
  const left = Math.floor(total / 2);
  const right = total - left;
  return `${left}v${right}`;
});

 
</script>

<template>
  <div class="lobby-page">
    <div class="lobby-shell content-panel">
      <h1 class="lobby-title">{{ phaseTitle }}</h1>
    <div class="countdown-slot">
      <p class="countdown" :class="{ 'is-hidden': activeCountdown === null }">
        {{ activeCountdownLabel }} {{ activeCountdown ?? 0 }}s
      </p>
      <div class="countdown-actions">
        <button v-if="showPauseButton" class="pause-button" @click="toggleCountdownPause">
          {{ isCountdownPaused ? 'Unpause Countdown' : 'Pause Countdown' }}
        </button>
        <button v-if="isDev" class="skip-button" @click="prevPhase">
          Previous Phase
        </button>
        <button v-if="showPauseButton || isDev" class="skip-button" @click="skipPhase">
          Skip Phase
        </button>
        <button class="leave-lobby-button" @click="handleLeaveLobby">
          Leave Lobby
        </button>
      </div>
    </div>

      <div class="lobby-panel">
        <div v-if="lobbyStore.loading" class="loading">
          Loading lobby...
        </div>

      <!-- Step 2: Map Voting -->
      <div v-else-if="lobbyStore.step === 2" class="lobby-section">
      <div class="map-vote-layout">
        <div class="team map-vote-team">
          <h3>{{ getTeamLabel('team1') }}</h3>
          <ul>
            <li
              v-for="(group, index) in groupPlayers(lobbyStore.teams.team1)"
              :key="group.id || `solo-${index}`"
              :class="['team-group', { grouped: !!group.id }]"
            >
              <div class="team-group-members">
                <span v-for="member in group.members" :key="member" class="team-group-member">
                  <span :class="{ 'current-user': isCurrentUser(member) }">{{ member }}</span>
                  <span v-if="isCaptain(member, 'team1')" class="captain-tag">Captain</span>
                </span>
              </div>
            </li>
          </ul>
        </div>

        <div class="map-list">
          <button
            v-for="map in mapOptions"
            :key="map"
            @click="handleVoteMap(map)"
            :class="['map-button', { 'voted': lobbyStore.mapVotes[authStore.username] === map }]"
            :disabled="false"
          >
            {{ map }}
            <span class="vote-count" v-if="lobbyStore.getVotesForMap(map) > 0">
              ({{ lobbyStore.getVotesForMap(map) }})
            </span>
          </button>
        </div>

        <div class="team map-vote-team">
          <h3>{{ getTeamLabel('team2') }}</h3>
          <ul>
            <li
              v-for="(group, index) in groupPlayers(lobbyStore.teams.team2)"
              :key="group.id || `solo-${index}`"
              :class="['team-group', { grouped: !!group.id }]"
            >
              <div class="team-group-members">
                <span v-for="member in group.members" :key="member" class="team-group-member">
                  <span :class="{ 'current-user': isCurrentUser(member) }">{{ member }}</span>
                  <span v-if="isCaptain(member, 'team2')" class="captain-tag">Captain</span>
                </span>
              </div>
            </li>
          </ul>
        </div>
      </div>
    </div>

      <!-- Step 3: Map Selected -->
      <div v-else-if="lobbyStore.step === 3" class="lobby-section">
        <div class="map-vote-layout match-ready-layout">
          <div class="team map-vote-team">
            <h3>{{ getTeamLabel('team1') }}</h3>
            <ul>
              <li
                v-for="(group, index) in groupPlayers(lobbyStore.teams.team1)"
                :key="group.id || `solo-${index}`"
                :class="['team-group', { grouped: !!group.id }]"
              >
                <div class="team-group-members">
                  <span v-for="member in group.members" :key="member" class="team-group-member">
                    <span :class="{ 'current-user': isCurrentUser(member) }">{{ member }}</span>
                    <span v-if="isCaptain(member, 'team1')" class="captain-tag">Captain</span>
                  </span>
                </div>
              </li>
            </ul>
          </div>

          <div class="match-info match-info-center">
            <p v-if="matchSizeLabel">Format <span class="highlight">{{ matchSizeLabel }}</span></p>
            <p>Map <span class="highlight">{{ lobbyStore.selectedMap }}</span></p>
            <p>Server IP <span class="highlight">{{ lobbyStore.serverDetails?.ip || '192.168.1.100' }}</span></p>
          </div>

          <div class="team map-vote-team">
            <h3>{{ getTeamLabel('team2') }}</h3>
            <ul>
              <li
                v-for="(group, index) in groupPlayers(lobbyStore.teams.team2)"
                :key="group.id || `solo-${index}`"
                :class="['team-group', { grouped: !!group.id }]"
              >
                <div class="team-group-members">
                  <span v-for="member in group.members" :key="member" class="team-group-member">
                    <span :class="{ 'current-user': isCurrentUser(member) }">{{ member }}</span>
                    <span v-if="isCaptain(member, 'team2')" class="captain-tag">Captain</span>
                  </span>
                </div>
              </li>
            </ul>
          </div>
        </div>
    </div>

      <!-- Step 4: Server Details -->
      <div v-else-if="lobbyStore.step === 4" class="lobby-section">
      <div class="match-details">
        <div class="match-info">
          <p>Map: <span class="highlight">{{ lobbyStore.selectedMap }}</span></p>
          <p>Server: <span class="highlight">{{ lobbyStore.serverDetails?.ip }}</span></p>
        </div>
        
        <div class="teams-container">
          <div class="team">
            <h3>{{ getTeamLabel('team1') }}</h3>
            <ul>
              <li
                v-for="(group, index) in groupPlayers(lobbyStore.teams.team1)"
                :key="group.id || `solo-${index}`"
                :class="['team-group', { grouped: !!group.id }]"
              >
                <div class="team-group-members">
                  <span v-for="member in group.members" :key="member" class="team-group-member">
                    <span :class="{ 'current-user': isCurrentUser(member) }">{{ member }}</span>
                    <span v-if="isCaptain(member, 'team1')" class="captain-tag">Captain</span>
                  </span>
                </div>
              </li>
            </ul>
          </div>
          
          <div class="team">
            <h3>{{ getTeamLabel('team2') }}</h3>
            <ul>
              <li
                v-for="(group, index) in groupPlayers(lobbyStore.teams.team2)"
                :key="group.id || `solo-${index}`"
                :class="['team-group', { grouped: !!group.id }]"
              >
                <div class="team-group-members">
                  <span v-for="member in group.members" :key="member" class="team-group-member">
                    <span :class="{ 'current-user': isCurrentUser(member) }">{{ member }}</span>
                    <span v-if="isCaptain(member, 'team2')" class="captain-tag">Captain</span>
                  </span>
                </div>
              </li>
            </ul>
          </div>
        </div>
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
}

.lobby-title {
  color: inherit;
  font-weight: 500;
  margin: 28px 0 12px;
  text-align: center;
}

.lobby-panel {
  width: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
}

.lobby-section {
  padding: 30px;
  width: 100%;
  min-height: 500px;
  display: flex;
  flex-direction: column;
  align-items: center;
  --teams-column-width: 420px;
  --middle-column-width: 320px;
  --phase-column-gap: 72px;
  --teams-offset: -52px;
}

.countdown {
  display: block;
  font-size: 1.2em;
  color: #4CAF50;
  font-weight: bold;
  margin: 1rem auto 0;
  text-align: center;
  width: 100%;
  max-width: 520px;
}

.countdown.is-hidden {
  visibility: hidden;
}

.countdown-slot {
  min-height: 80px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.countdown-slot .countdown {
  margin-top: 0;
}

.pause-button {
  margin-top: 0.5rem;
  padding: 0.6rem 1.2rem;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.pause-button:hover {
  background: #4a4f56;
}

.countdown-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
}

.skip-button {
  margin-top: 0.5rem;
  padding: 0.6rem 1.2rem;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.skip-button:hover {
  background: #4a4f56;
}

.teams-container {
  display: flex;
  justify-content: space-between;
  margin: 20px auto 0;
  width: 100%;
  max-width: calc((2 * var(--teams-column-width)) + var(--middle-column-width) + (2 * var(--phase-column-gap)));
  gap: var(--phase-column-gap);
  align-items: flex-start;
}

.teams-container.teams-assigned {
  max-width: 100%;
  justify-content: space-between;
  gap: 72px;
}

.teams-container.teams-assigned .team {
  max-width: 45%;
}

.teams-container .team {
  margin-top: var(--teams-offset);
  max-width: var(--teams-column-width);
}

.team {
  flex: 1;
  margin: 0;
  padding: 20px;
  background: transparent;
  border-radius: 4px;
  min-width: 200px;
}

.teams-assigned .team ul {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  column-gap: 12px;
  row-gap: 6px;
}

.teams-assigned .team li {
  font-size: 0.8rem;
}

.team h3 {
  text-align: center;
  margin-bottom: 15px;
  color: inherit;
  font-weight: 600;
}

.team ul {
  list-style: none;
  padding: 0;
  margin: 0 auto;
  width: fit-content;
  max-width: 100%;
}

.team li {
  padding: 8px;
  margin: 5px 0;
  background: #243447;
  border-radius: 4px;
  text-align: center;
  color: inherit;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  font-size: 0.8rem;
}

.team-group {
  border-radius: 6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 8px 10px;
}

.team-group.grouped {
  border: 1px solid rgba(126, 217, 87, 0.25);
}

.team-group-members {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 4px;
  width: fit-content;
  margin: 0 auto;
  justify-content: center;
}

.team-group-member {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  text-align: center;
  min-width: 0;
}

.map-vote-layout {
  display: grid;
  grid-template-columns: var(--teams-column-width) var(--middle-column-width) var(--teams-column-width);
  gap: var(--phase-column-gap);
  width: 100%;
  max-width: calc((2 * var(--teams-column-width)) + var(--middle-column-width) + (2 * var(--phase-column-gap)));
  justify-content: center;
  align-items: start;
  min-height: 480px;
}

.match-ready-layout {
  min-height: 480px;
}

.match-info.match-info-center {
  align-self: center;
  justify-self: center;
}

.map-vote-team {
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  margin-top: var(--teams-offset);
}

.map-vote-layout .map-list {
  align-self: center;
  justify-self: center;
}

.map-vote-team ul {
  list-style: none;
  padding: 0;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.map-vote-team li {
  font-size: 0.8rem;
}

.map-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: stretch;
  margin-top: 0;
  padding-top: 34px;
  width: 100%;
  max-width: var(--middle-column-width);
}

.map-button {
  position: relative;
  padding: 15px 25px;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 120px;
  width: 100%;
  text-align: center;
}

.map-button:hover {
  background: #4a4f56;
}

.map-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.map-button.voted {
  background: #2E7D32;
  transform: scale(1.05);
}

.vote-count {
  position: absolute;
  top: -8px;
  right: -8px;
  background: #2d2d2d;
  color: #4CAF50;
  border-radius: 50%;
  padding: 2px 6px;
  font-size: 0.8em;
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

.selected-map {
  font-size: 1.2em;
  font-weight: bold;
  color: #4CAF50;
  text-align: center;
  margin: 20px 0;
}

.transition-message {
  text-align: center;
  margin-top: 20px;
  color: #888888;
  font-style: italic;
}

.match-info {
  background: #243447;
  padding: 20px;
  border-radius: 4px;
  width: 100%;
  max-width: var(--middle-column-width);
  text-align: center;
}

.match-info p {
  margin: 10px 0;
  font-size: 1.1em;
  color: inherit;
  text-align: center;
}

.highlight {
  color: #4CAF50;
  font-weight: bold;
}

.captain-tag {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  background: #1f1f1f;
  color: inherit;
  padding: 2px 6px;
  border-radius: 999px;
}

.teams-three {
  display: grid;
  grid-template-columns: 1fr 0.9fr 1fr;
  gap: 16px;
  width: 100%;
  max-width: 900px;
  align-items: start;
}

.leave-lobby-button {
  position: static;
  padding: 0.6rem 1.2rem;
  background: #3b3f45;
  color: inherit;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.leave-lobby-button:hover {
  background: #4a4f56;
}
</style>
  
