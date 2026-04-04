<script setup>
import { onMounted, onBeforeUnmount, ref } from 'vue';
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

// Constants
const AVAILABLE_MAPS = ['Map 1', 'Map 2', 'Map 3', 'Map 4', 'Map 5'];

const listeners = ref([]);

// LIFECYCLE HOOKS
onMounted(async () => {
  const lobbyId = route.params.lobbyId;
  console.log('Lobby component mounted. ID:', lobbyId);
  lobbyStore.loading = true;
  
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
            if (data.isAssigningTeams !== undefined) {
              lobbyStore.startTeamAssignment();
            }
            if (data.teams) {
              lobbyStore.updateTeams(data.teams);
            }
            lobbyStore.updateLobbyState(data);
          }
        },
        {
          event: SOCKET_EVENTS.LOBBY.COUNTDOWN.TEAMS,
          handler: (data) => {
            lobbyStore.updateCountdown(data.countdown);
          }
        },
        {
          event: SOCKET_EVENTS.LOBBY.COUNTDOWN.VOTING,
          handler: (data) => {
            console.log('Received voting countdown update:', data);
            if (data.countdown !== undefined) {
              lobbyStore.updateVotingCountdown(data.countdown);
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
    const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.LEAVE, {
      lobby_id: lobbyStore.lobbyId,
      username: authStore.username
    });
    
    if (response.success) {
      // Clear lobby state
      lobbyStore.leaveLobby();
      // Remove from localStorage to prevent auto-rejoin
      localStorage.removeItem('currentLobby');
      router.push('/');
    } else {
      throw new Error(response.message || 'Failed to leave lobby');
    }
  } catch (error) {
    rootStore.setError({
      message: 'Failed to leave lobby',
      details: error.message,
      context: 'lobby-leave'
    });
  }
};
</script>

<template>
  <div class="lobby">
    <div class="lobby-header">
      <h1>Game Lobby</h1>
      <button @click="handleLeaveLobby" class="leave-button">
        Leave Lobby
      </button>
    </div>

    <div v-if="lobbyStore.loading" class="loading">
      Loading lobby...
    </div>
    
    <!-- Step 1: Waiting with Countdown -->
    <div v-if="lobbyStore.step === 1" class="lobby-section">
      <!-- Countdown Display -->
      <div v-if="lobbyStore.countdown !== null" class="countdown">
        <h3>Teams will be assigned in:</h3>
        <div class="countdown-timer">{{ lobbyStore.countdown }}</div>
      </div>
      
      <!-- Show players list if not assigning teams and not showing teams -->
      <div v-if="!lobbyStore.isAssigningTeams && !lobbyStore.showingTeams" class="players-list">
        <h3>Players in Lobby:</h3>
        <ul>
          <li v-for="player in lobbyStore.players" :key="player">
            {{ player }}
          </li>
        </ul>
      </div>
      
      <!-- Show teams after assignment -->
      <div v-else-if="lobbyStore.showingTeams" class="teams-display">
        <h3>Teams have been assigned!</h3>
          <!-- Countdown Display -->
          <div v-if="lobbyStore.teamCountdown" class="countdown">
          <h3>Map voting will begin in:</h3>
          <div class="countdown-timer">{{ lobbyStore.teamCountdown }}</div>
          <p>seconds remaining</p>
        </div>
        <div class="teams-container">
          <div class="team">
            <h3>Team 1</h3>
            <ul>
              <li v-for="player in lobbyStore.teams.team1" :key="player">
                {{ player }}
              </li>
            </ul>
          </div>
          
          <div class="team">
            <h3>Team 2</h3>
            <ul>
              <li v-for="player in lobbyStore.teams.team2" :key="player">
                {{ player }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- Step 2: Map Voting -->
    <div v-else-if="lobbyStore.step === 2" class="lobby-section">
      <!-- Countdown Display -->
      <div v-if="lobbyStore.votingCountdown" class="countdown">
        <h3>Vote for a Map:</h3>
        <div class="countdown-timer">{{ lobbyStore.votingCountdown }}</div>
        <p>seconds remaining</p>
      </div>

      <div class="map-list">
        <button
          v-for="map in AVAILABLE_MAPS"
          :key="map"
          @click="handleVoteMap(map)"
          :class="['map-button', { 'voted': lobbyStore.mapVotes[authStore.username] === map }]"
          :disabled="lobbyStore.mapVotes[authStore.username] && lobbyStore.mapVotes[authStore.username] !== map"
        >
          {{ map }}
          <span class="vote-count" v-if="lobbyStore.getVotesForMap(map) > 0">
            ({{ lobbyStore.getVotesForMap(map) }})
          </span>
        </button>
      </div>
    </div>

    <!-- Step 3: Map Selected -->
    <div v-else-if="lobbyStore.step === 3" class="lobby-section">
      <h2>Match Ready</h2>
      <div class="match-details">
        <div class="match-info">
          <p>Selected Map: <span class="highlight">{{ lobbyStore.selectedMap }}</span></p>
          <p>Server IP: <span class="highlight">{{ lobbyStore.serverDetails?.ip || '192.168.1.100' }}</span></p>
        </div>
        
        <div class="teams-container">
          <div class="team">
            <h3>Team 1</h3>
            <ul>
              <li v-for="player in lobbyStore.teams.team1" :key="player">
                {{ player }}
              </li>
            </ul>
          </div>
          
          <div class="team">
            <h3>Team 2</h3>
            <ul>
              <li v-for="player in lobbyStore.teams.team2" :key="player">
                {{ player }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>

    <!-- Step 4: Server Details -->
    <div v-else-if="lobbyStore.step === 4" class="lobby-section">
      <h2>Match Ready</h2>
      <div class="match-details">
        <div class="match-info">
          <p>Map: <span class="highlight">{{ lobbyStore.selectedMap }}</span></p>
          <p>Server: <span class="highlight">{{ lobbyStore.serverDetails?.ip }}</span></p>
        </div>
        
        <div class="teams-container">
          <div class="team">
            <h3>Team 1</h3>
            <ul>
              <li v-for="player in lobbyStore.teams.team1" :key="player">
                {{ player }}
              </li>
            </ul>
          </div>
          
          <div class="team">
            <h3>Team 2</h3>
            <ul>
              <li v-for="player in lobbyStore.teams.team2" :key="player">
                {{ player }}
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.lobby {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  min-height: 600px;
}

.lobby-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.lobby-header h1 {
  color: #ffffff;
  margin: 0;
}

.lobby-section {
  background: #2d2d2d;
  padding: 30px;
  border-radius: 8px;
  margin-bottom: 20px;
  min-height: 500px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
  display: flex;
  flex-direction: column;
  align-items: center;
}

.countdown {
  text-align: center;
  margin: 20px 0;
  width: 100%;
}

.countdown h3 {
  color: #cccccc;
  margin-bottom: 10px;
}

.countdown-timer {
  font-size: 48px;
  font-weight: bold;
  color: #4CAF50;
  margin: 20px 0;
}

.players-list {
  width: 100%;
  max-width: 400px;
  margin: 20px auto;
}

.players-list h3 {
  color: #cccccc;
  text-align: center;
  margin-bottom: 15px;
}

.players-list ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.players-list li {
  padding: 10px;
  margin: 5px 0;
  background: #3d3d3d;
  border-radius: 4px;
  text-align: center;
  color: #ffffff;
}

.teams-container {
  display: flex;
  justify-content: space-around;
  margin: 20px 0;
  width: 100%;
  max-width: 600px;
}

.team {
  flex: 1;
  margin: 0 10px;
  padding: 20px;
  background: #3d3d3d;
  border-radius: 4px;
  min-width: 200px;
}

.team h3 {
  text-align: center;
  margin-bottom: 15px;
  color: #cccccc;
}

.team ul {
  list-style: none;
  padding: 0;
  margin: 0;
}

.team li {
  padding: 8px;
  margin: 5px 0;
  background: #2d2d2d;
  border-radius: 4px;
  text-align: center;
  color: #ffffff;
}

.map-list {
  display: flex;
  flex-wrap: wrap;
  gap: 15px;
  justify-content: center;
  margin-top: 20px;
  width: 100%;
  max-width: 600px;
}

.map-button {
  position: relative;
  padding: 15px 25px;
  background: #3d3d3d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 120px;
}

.map-button:hover {
  background: #4d4d4d;
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

.leave-button {
  padding: 8px 16px;
  background: #ff4444;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.2s;
}

.leave-button:hover {
  background: #ff5555;
}

.loading {
  text-align: center;
  padding: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 500px;
  color: #cccccc;
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

.teams-display h3 {
  text-align: center;
  color: #cccccc;
  margin-bottom: 20px;
}

.match-details {
  width: 100%;
  max-width: 600px;
  margin: 0 auto;
  text-align: center;
}

.match-details p {
  margin: 10px 0;
  font-size: 1.1em;
  color: #cccccc;
}

.match-details h2 {
  color: #ffffff;
  margin-bottom: 20px;
}

.match-info {
  background: #3d3d3d;
  padding: 20px;
  border-radius: 4px;
  margin-bottom: 20px;
  width: 100%;
  max-width: 400px;
}

.match-info p {
  margin: 10px 0;
  font-size: 1.1em;
  color: #cccccc;
  text-align: center;
}

.highlight {
  color: #4CAF50;
  font-weight: bold;
}
</style>
  