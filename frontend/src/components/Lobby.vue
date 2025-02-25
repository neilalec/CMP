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
  lobbyStore.loading = true;
  
  try {
    if (!socketStore.isConnected) {
      throw new Error('Not connected to server');
    }

    // Join the lobby first
    await socketStore.emit(SOCKET_EVENTS.LOBBY.JOIN, { lobby_id: lobbyId });

    const setupListeners = () => {
      const addListener = (event, callback) => {
        socketStore.on(event, callback);
        listeners.value.push({ event, callback });
      };

      addListener(SOCKET_EVENTS.LOBBY.UPDATE, (data) => {
        lobbyStore.updateLobbyState(data);
      });

      addListener(SOCKET_EVENTS.LOBBY.MAP_SELECTED, async (data) => {
        // Get fresh state first
        await socketStore.emit(SOCKET_EVENTS.LOBBY.GET_DATA, { lobby_id: lobbyId });
        lobbyStore.updateLobbyState({
          selectedMap: data.map,
          step: 3
        });
      });

      addListener(SOCKET_EVENTS.LOBBY.READY, (data) => {
        lobbyStore.updateLobbyState({
          ...data,
          step: 4
        });
      });
    };

    setupListeners();

    // Join lobby and get initial data
    if (!authStore.username) {
      throw new Error('No username available');
    }

    await socketStore.emit(SOCKET_EVENTS.LOBBY.JOIN, { 
      lobby_id: lobbyId,
      username: authStore.username
    });
    
    const lobbyData = await socketStore.emit(SOCKET_EVENTS.LOBBY.GET_DATA, {
      lobby_id: lobbyId 
    });

    if (!lobbyData || !lobbyData.lobby_id) {
      throw new Error('Invalid lobby data received');
    }
    
    lobbyStore.updateLobbyState(lobbyData);
    
  } catch (error) {
    rootStore.setError(error.message);
    router.push('/');
  } finally {
    lobbyStore.loading = false;
  }
});

onBeforeUnmount(() => {
  listeners.value.forEach(({ event, callback }) => {
    socketStore.off(event, callback);
  });
  listeners.value = [];
  lobbyStore.reset();
});

// METHODS
const handleVoteMap = async (map) => {
  try {
    await socketStore.emit(SOCKET_EVENTS.LOBBY.VOTE_MAP, {
      lobby_id: lobbyStore.lobbyId,
      map
    });
  } catch (error) {
    rootStore.setError('Failed to vote for map');
  }
};

const handleLeaveLobby = async () => {
  try {
    await socketStore.emit(SOCKET_EVENTS.LOBBY.LEAVE, {
      lobby_id: lobbyStore.lobbyId
    });
    router.push('/');
  } catch (error) {
    rootStore.setError('Failed to leave lobby');
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
    
    <!-- Step 1: Waiting -->
    <div v-else-if="lobbyStore.step === 1" class="lobby-section">
      <h2>Waiting for Players</h2>
      <div class="players-list">
        <h3>Players in Lobby:</h3>
        <ul>
          <li v-for="player in lobbyStore.players" :key="player">
            {{ player }}
          </li>
        </ul>
      </div>
    </div>

    <!-- Step 2: Map Voting -->
    <div v-else-if="lobbyStore.step === 2" class="lobby-section">
      <h2>Vote for a Map</h2>
      <div class="map-list">
        <button
          v-for="map in AVAILABLE_MAPS"
          :key="map"
          @click="handleVoteMap(map)"
          class="map-button"
        >
          {{ map }}
        </button>
      </div>
    </div>

    <!-- Step 3: Map Selected -->
    <div v-else-if="lobbyStore.step === 3" class="lobby-section">
      <h2>Map Selected</h2>
      <p class="selected-map">{{ lobbyStore.selectedMap }}</p>
      <p>Waiting for server allocation...</p>
    </div>

    <!-- Step 4: Server Details -->
    <div v-else-if="lobbyStore.step === 4" class="lobby-section">
      <h2>Match Ready</h2>
      <div class="match-details">
        <p>Map: {{ lobbyStore.selectedMap }}</p>
        <p>Server: {{ lobbyStore.serverDetails?.ip }}</p>
        
        <div class="teams">
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
}

.lobby-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.lobby-section {
  background: #f5f5f5;
  padding: 20px;
  border-radius: 4px;
  margin-bottom: 20px;
}

.map-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 20px;
}

.map-button {
  padding: 10px 20px;
  background: #4CAF50;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.leave-button {
  padding: 8px 16px;
  background: #f44336;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.teams {
  display: flex;
  justify-content: space-between;
  margin-top: 20px;
}

.team {
  flex: 1;
  margin: 0 10px;
  padding: 15px;
  background: white;
  border-radius: 4px;
}

.loading {
  text-align: center;
  padding: 20px;
}

.selected-map {
  font-size: 1.2em;
  font-weight: bold;
  color: #4CAF50;
}
</style>
  