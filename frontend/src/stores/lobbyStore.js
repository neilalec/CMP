import { defineStore } from 'pinia';
import { useSocketStore } from './socketStore';
import { useRootStore } from './rootStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';


export const useLobbyStore = defineStore('lobby', {
  state: () => ({
    lobbyId: null,
    players: [],
    selectedMap: null,
    teams: {
      team1: [],
      team2: []
    },
    serverDetails: null,
    step: 1,
    loading: false
  }),

  actions: {
    setLoading(status) {
      this.loading = status;
    },

    async updateLobbyState(data) {
      this.setLoading(true);
      try {
        this.lobbyId = data.lobby_id;
        this.players = data.players || [];
        this.selectedMap = data.selected_map;
        this.teams = data.teams || { team1: [], team2: [] };
        this.serverDetails = data.server_details;
        this.step = data.step || 1;
      } catch (error) {
        rootStore.setError('Failed to update lobby state');
      } finally {
        this.setLoading(false);
      }
    },

    reset() {
      this.lobbyId = null;
      this.players = [];
      this.selectedMap = null;
      this.teams = { team1: [], team2: [] };
      this.serverDetails = null;
      this.step = 1;
      this.loading = false;
    }
  }
});
