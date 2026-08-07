import { defineStore } from 'pinia';
import { useSocketStore } from './socketStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import {
  clearCurrentLobby,
  setCurrentLobbyId
} from '../utils/lobbyPersistence';
import { createDefaultLobbyState } from './state/lobbyState';

const assignFirstDefined = (store, targetKey, data, sourceKeys, transform = (value) => value) => {
  for (const sourceKey of sourceKeys) {
    if (data[sourceKey] !== undefined) {
      store[targetKey] = transform(data[sourceKey])
      return
    }
  }
}

const normalizeArray = (value) => (Array.isArray(value) ? value : [])

export const useLobbyStore = defineStore('lobby', {
  state: () => createDefaultLobbyState(),

  actions: {
    setLoading(status) {
      this.loading = status;
    },

    applyLobbyPhase(step) {
      if (!step) return
      this.step = step
      if (step >= 3) {
        this.countdown = null
        this.votingCountdown = null
        return
      }
      this.serverPresence = {}
      this.serverPresenceAvailable = true
      this.serverPresenceError = null
    },

    async updateLobbyState(data) {
      console.log('Updating lobby state with:', data);
      this.setLoading(true);
      try {
        if (data.lobby_id) {
          this.lobbyId = data.lobby_id;
          if (data.players?.length > 0 && !data.is_spectator) {
            setCurrentLobbyId(data.lobby_id);
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
        assignFirstDefined(this, 'playerProfiles', data, ['player_profiles', 'playerProfiles'], (value) => (
          value && typeof value === 'object' ? value : {}
        ));
        assignFirstDefined(this, 'selectedMap', data, ['selected_map', 'map']);
        assignFirstDefined(this, 'queueMode', data, ['queue_mode', 'queueMode']);
        assignFirstDefined(this, 'queueLabel', data, ['queue_label', 'queueLabel']);
        assignFirstDefined(this, 'matchSizeLabel', data, ['match_size_label', 'matchSizeLabel']);
        assignFirstDefined(this, 'maxPlayers', data, ['max_players', 'maxPlayers']);
        assignFirstDefined(this, 'mapPool', data, ['map_pool', 'mapPool'], normalizeArray);
        if (data.map_votes) this.mapVotes = data.map_votes;
        if (data.vote_counts) this.voteCounts = data.vote_counts;
        if (data.voting_countdown !== undefined) {
          this.updateVotingCountdown(data.voting_countdown);
        }
        if (data.teams) this.teams = data.teams;
        assignFirstDefined(this, 'teamLabels', data, ['team_labels', 'teamLabels'], (value) => (
          value && typeof value === 'object' ? value : {}
        ));
        if (data.player_groups) this.playerGroups = data.player_groups;
        if (data.captains) this.captains = data.captains;
        if (data.server_details) this.serverDetails = data.server_details;
        if (data.server_details === null) this.serverDetails = null;
        assignFirstDefined(this, 'serverDetailsProvidedAt', data, ['server_details_provided_at']);
        assignFirstDefined(this, 'liveStartedAt', data, ['live_started_at', 'liveStartedAt']);
        assignFirstDefined(this, 'liveMatchMaxSeconds', data, ['live_match_max_seconds', 'liveMatchMaxSeconds']);
        if (!this.liveMatchMaxSeconds && this.serverDetails) {
          this.liveMatchMaxSeconds = this.serverDetails.liveMatchMaxSeconds || this.serverDetails.live_match_max_seconds || null;
        }
        if (!this.liveStartedAt && this.serverDetails) {
          this.liveStartedAt = this.serverDetails.liveStartedAt || this.serverDetails.live_started_at || null;
        }
        assignFirstDefined(this, 'liveRollReadyAt', data, ['live_roll_ready_at']);
        assignFirstDefined(this, 'liveRollCountdown', data, ['live_roll_countdown']);
        assignFirstDefined(this, 'announcement', data, ['announcement']);
        assignFirstDefined(this, 'isSpectator', data, ['is_spectator', 'isSpectator'], Boolean);
        assignFirstDefined(this, 'adminLiveReadyOverride', data, ['admin_live_ready_override', 'adminLiveReadyOverride'], Boolean);
        this.applyLobbyPhase(data.step);
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
      delete this.playerProfiles[username];
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
      clearCurrentLobby();
    },

    reset() {
      Object.assign(this, createDefaultLobbyState());
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
    },

    updateLiveRollCountdown(count) {
      this.liveRollCountdown = count > 0 ? count : 0;
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
    },

    getDisplayName: (state) => (username) => {
      return state.playerProfiles?.[username]?.display_name || username;
    }
  }
});
