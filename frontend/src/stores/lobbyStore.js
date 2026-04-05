import { defineStore } from 'pinia';
import { useSocketStore } from './socketStore';
import { useRootStore } from './rootStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';


export const useLobbyStore = defineStore('lobby', {
  state: () => ({
    lobbyId: null,
    players: [],
    playerStatuses: {},
    selectedMap: null,
    teams: {
      team1: [],
      team2: []
    },
    serverDetails: null,
    step: 1,
    loading: false,
    error: null,
    countdown: null,
    isAssigningTeams: false,
    showingTeams: false,
    teamCountdown: null,
    mapVotes: {},
    votingCountdown: null,
    voteCounts: {}
  }),

  actions: {
    setLoading(status) {
      this.loading = status;
    },

    async updateLobbyState(data) {
      console.log('Updating lobby state with:', data);
      this.setLoading(true);
      try {
        if (data.lobby_id) {
          this.lobbyId = data.lobby_id;
          if (data.players?.length > 0) {
            localStorage.setItem('currentLobby', data.lobby_id);
          }
        }
        if (data.players) {
          this.players = data.players;
          data.players.forEach(player => {
            if (!this.playerStatuses[player]) {
              this.playerStatuses[player] = 'connected';
            }
          });
        }
        if (data.selected_map) this.selectedMap = data.selected_map;
        if (data.teams) this.teams = data.teams;
        if (data.server_details) this.serverDetails = data.server_details;
        if (data.step) {
          this.step = data.step;
          if (data.step === 2) {
            this.showingTeams = false;
            this.isAssigningTeams = false;
          }
          if (data.step >= 3) {
            this.countdown = null;
            this.votingCountdown = null;
          }
        }
        if (data.countdown !== undefined) {
          this.countdown = data.countdown;
        }
        if (data.isAssigningTeams !== undefined) {
          this.isAssigningTeams = data.isAssigningTeams;
        }
        this.error = null;
      } catch (error) {
        console.error('Error updating lobby state:', error);
        this.error = 'Failed to update lobby state';
      } finally {
        this.setLoading(false);
      }
    },

    updatePlayerStatus(username, status) {
      if (this.players.includes(username)) {
        this.playerStatuses[username] = status;
      }
    },

    removePlayer(username) {
      this.players = this.players.filter(p => p !== username);
      delete this.playerStatuses[username];
      this.teams.team1 = this.teams.team1.filter(p => p !== username);
      this.teams.team2 = this.teams.team2.filter(p => p !== username);
    },

    handleDisconnect() {
      this.error = 'Disconnected from lobby';
    },

    leaveLobby() {
      this.reset();
      localStorage.removeItem('currentLobby');
    },

    reset() {
      this.lobbyId = null;
      this.players = [];
      this.playerStatuses = {};
      this.selectedMap = null;
      this.teams = { team1: [], team2: [] };
      this.serverDetails = null;
      this.step = 1;
      this.loading = false;
      this.error = null;
      this.countdown = null;
      this.isAssigningTeams = false;
      this.showingTeams = false;
      this.teamCountdown = null;
      this.mapVotes = {};
      this.votingCountdown = null;
      this.voteCounts = {};
    },

    updateCountdown(count) {
      this.countdown = count > 0 ? count : null;
    },

    startTeamAssignment() {
      this.isAssigningTeams = true;
      this.showingTeams = false;
    },

    updateTeams(teams) {
      this.teams = teams;
      this.showingTeams = true;
      this.isAssigningTeams = false;
    },

    submitMapVote(map) {
      const socketStore = useSocketStore();
      return socketStore.emit(SOCKET_EVENTS.LOBBY.VOTE_MAP, {
        lobby_id: this.lobbyId,
        player: this.username,
        map: map
      });
    },

    updateTeamCountdown(count) {
      console.log('[Pinia] Setting teamCountdown to:', count);
      this.teamCountdown = count > 0 ? count : null;
    },

    updateMapVotes(votes) {
      this.mapVotes = votes;
    },

    updateVoteCounts(counts) {
      this.voteCounts = counts;
    },

    updateVotingCountdown(count) {
      this.votingCountdown = count > 0 ? count : null;
    },

    setSelectedMap(map) {
      this.selectedMap = map;
    }
  },

  getters: {
    connectedPlayers: (state) => {
      return state.players.filter(player => 
        state.playerStatuses[player] === 'connected'
      );
    },
    
    disconnectedPlayers: (state) => {
      return state.players.filter(player => 
        state.playerStatuses[player] === 'disconnected'
      );
    },
    
    isLobbyViable: (state) => {
      return state.connectedPlayers.length >= 2;
    },

    getVotesForMap: (state) => (map) => {
      return state.voteCounts[map] || 0;
    }
  }
});
