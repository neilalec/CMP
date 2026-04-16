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
    captains: {
      team1: null,
      team2: null
    },
    serverDetails: null,
    step: 2,
    loading: false,
    error: null,
    countdown: null,
    mapVotes: {},
    votingCountdown: null,
    voteCounts: {},
    mapPool: [],
    playerGroups: {},
    serverPresence: {},
    serverPresenceAvailable: true,
    serverPresenceError: null,
    announcement: null
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
        if (data.map_pool) this.mapPool = data.map_pool;
        if (data.mapPool) this.mapPool = data.mapPool;
        if (data.map_votes) this.mapVotes = data.map_votes;
        if (data.vote_counts) this.voteCounts = data.vote_counts;
        if (data.voting_countdown !== undefined) {
          this.updateVotingCountdown(data.voting_countdown);
        }
        if (data.teams) this.teams = data.teams;
        if (data.player_groups) this.playerGroups = data.player_groups;
        if (data.captains) {
          this.captains = data.captains;
          if (data.captains.team1 && data.captains.team2) {
            localStorage.setItem('currentLobbyCaptains', JSON.stringify(data.captains));
          }
        }
        if (data.server_details) this.serverDetails = data.server_details;
        if (data.announcement !== undefined) this.announcement = data.announcement;
        if (data.step) {
          this.step = data.step;
          if (data.step >= 3) {
            this.countdown = null;
            this.votingCountdown = null;
          }
        }
        if (data.countdown !== undefined) {
          this.countdown = data.countdown;
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
      delete this.serverPresence[username];
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
      this.captains = { team1: null, team2: null };
      this.serverDetails = null;
      this.step = 2;
      this.loading = false;
      this.error = null;
      this.countdown = null;
      this.mapVotes = {};
      this.votingCountdown = null;
      this.voteCounts = {};
      this.mapPool = [];
      this.playerGroups = {};
      this.serverPresence = {};
      this.serverPresenceAvailable = true;
      this.serverPresenceError = null;
      this.announcement = null;
    },

    updateServerPresence(rows, options = {}) {
      const next = {};
      (rows || []).forEach((row) => {
        if (row?.username) {
          next[row.username] = row;
        }
      });
      this.serverPresence = next;
      this.serverPresenceAvailable = options.bridgeAvailable !== false;
      this.serverPresenceError = options.bridgeError || null;
    },

    updateCountdown(count) {
      this.countdown = count > 0 ? count : null;
    },

    updateTeams(teams) {
      this.teams = teams;
    },

    submitMapVote(map) {
      const socketStore = useSocketStore();
      return socketStore.emit(SOCKET_EVENTS.LOBBY.VOTE_MAP, {
        lobby_id: this.lobbyId,
        player: this.username,
        map: map
      });
    },

    updateMapVotes(votes) {
      this.mapVotes = votes;
    },

    updateVoteCounts(counts) {
      this.voteCounts = counts;
    },

    updateMapPool(pool) {
      this.mapPool = Array.isArray(pool) ? pool : [];
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
