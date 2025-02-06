<template>
    <div v-if="lobbyData">
      <h1>Welcome to {{ lobbyId }}</h1>
      <p>Teams:</p>
      <ul>
        <li v-for="(team, index) in lobbyData.teams" :key="index">{{ team }}</li>
      </ul>
      <button @click="step = 2">Proceed to Map Voting</button>
    </div>
    <div v-else>
      <p>Loading lobby data...</p>
    </div>

    <!-- Step 2: Map Voting -->
    <div v-if="step === 2">
      <h3>Vote for a Map</h3>
      <ul>
        <li v-for="map in maps" :key="map">
          <button @click="voteForMap(map)">{{ map }}</button>
        </li>
      </ul>
      <div v-if="selectedMap">You voted for: {{ selectedMap }}</div>
    </div>

    <!-- Step 3: Map Selected -->
    <div v-if="step === 3">
      <h3>Map Selected: {{ lobbyData.selected_map }}</h3>
      <button @click="proceedToServerDetails">Show Server Details</button>
    </div>

    <!-- Step 4: Server Details -->
    <div v-if="step === 4">
      <h3>Match Ready</h3>
      <p>Map: {{ lobbyData.selected_map }}</p>
      <p>Server IP: {{ lobbyData.server_ip }}</p>
      <div>
        <h4>Team 1</h4>
        <ul>
          <li v-for="player in lobbyData.teams.team1" :key="player">{{ player }}</li>
        </ul>
      </div>
      <div>
        <h4>Team 2</h4>
        <ul>
          <li v-for="player in lobbyData.teams.team2" :key="player">{{ player }}</li>
        </ul>
      </div>
    </div>
</template>
  
<script setup>
  import { ref, onMounted } from 'vue';
  import { useRouter, useRoute } from 'vue-router';
  import { io } from 'socket.io-client';

  // Declare props
  defineProps({
    lobbyId: String,
  });

  // Initialize required variables and Socket.IO connection
  const router = useRouter();
  const route = useRoute();
  const socket = io('http://localhost:5000', {
    transports: ['websocket'], // Force WebSocket
}); // Ensure your socket is connected here
  const lobbyId = route.params.lobbyId;


  // Reactive variables for component state
  const lobbyData = ref(null);
  const step = ref(1);
  const maps = ['Map 1', 'Map 2', 'Map 3', 'Map 4', 'Map 5'];
  const selectedMap = ref('');  
  const players = ref([]); // List of players in the lobby
  const loading = ref(false);
  

  onMounted(() => {
    
    socket.emit('get-lobby-data', { lobby_id: lobbyId });
    socket.on('lobby_data', (data) => {
      lobbyData.value = data;
      step.value = 1;
      console.log('Lobby data received:', data);
    });

    socket.on('map_selected', (data) => {
      lobbyData.value.selected_map = data.map;  
      step.value = 3;
    });

    socket.on('lobby_ready', (data) => {
      lobbyData.value = data;
      step.value = 4;
    });
});


const voteForMap = (map) => {
  socket.emit('vote-map', { lobby_id: lobbyId, player: localStorage.getItem('username'), vote: map });
};

const startLobby = () => {
  socket.emit('start-lobby', { lobby_id: lobbyId });
};

</script>
  
<style scoped>
  .lobby {
    padding: 20px;
    text-align: center;
  }
</style>
  