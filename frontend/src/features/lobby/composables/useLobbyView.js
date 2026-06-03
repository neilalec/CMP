import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../../../stores/authStore';
import { useLobbyStore } from '../../../stores/lobbyStore';
import { useRootStore } from '../../../stores/rootStore';
import { useSocketStore } from '../../../stores/socketStore';
import { SOCKET_EVENTS } from '../../../constants/socketEvents';
import { clearCurrentLobby } from '../../../utils/lobbyPersistence';

export function useLobbyView() {
  const router = useRouter();
  const route = useRoute();
  const lobbyStore = useLobbyStore();
  const socketStore = useSocketStore();
  const rootStore = useRootStore();
  const authStore = useAuthStore();
  const isCountdownPaused = ref(false);
  const serverPresencePoll = ref(null);
  const listeners = ref([]);

  const AVAILABLE_MAPS = [
    'Al Basrah Skirmish v1',
    'Belaya Skirmish v1',
    'Chora Skirmish v1',
    "Fool's Road Skirmish v1",
    'Narva Skirmish v1'
  ];

  const activeCountdown = computed(() => (lobbyStore.step === 2 ? lobbyStore.votingCountdown : null));
  const activeCountdownLabel = computed(() => (lobbyStore.step === 2 ? 'Map selected in' : 'Match starting in'));
  const phaseTitle = computed(() => {
    if (lobbyStore.loading) return 'Loading Lobby...';
    if (lobbyStore.step === 2) return 'Map Voting';
    if (lobbyStore.step === 3) return 'Match Ready';
    if (lobbyStore.step === 4) return 'Server Details';
    return 'Lobby';
  });
  const showPauseButton = computed(() => activeCountdown.value !== null);
  const mapOptions = computed(() => (lobbyStore.mapPool?.length ? lobbyStore.mapPool : AVAILABLE_MAPS));
  const isDev = import.meta.env.DEV;
  const groupedTeam1 = computed(() => groupPlayers(lobbyStore.teams.team1));
  const groupedTeam2 = computed(() => groupPlayers(lobbyStore.teams.team2));
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

  const isCaptain = (player, teamKey) => lobbyStore.captains?.[teamKey] === player;
  const isCurrentUser = (player) => player === authStore.username;
  const getTeamLabel = (teamKey) => (teamKey === 'team1' ? 'BLUFOR' : 'OPFOR');
  const getServerPresence = (player) => lobbyStore.serverPresence?.[player] || null;
  const isServerConnected = (player) => !!getServerPresence(player)?.connected;
  const getConnectionFlagClass = (player) => {
    if (lobbyStore.serverPresenceAvailable === false) return 'is-unavailable';
    return isServerConnected(player) ? 'is-connected' : 'is-missing';
  };
  const getConnectionLabel = (player) => {
    if (lobbyStore.serverPresenceAvailable === false) return 'server unavailable';
    return isServerConnected(player) ? 'connected' : 'not connected';
  };

  const fetchServerPresence = async () => {
    const lobbyId = lobbyStore.lobbyId || route.params.lobbyId;
    if (!lobbyId || !socketStore.isConnected) return;

    try {
      const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.SERVER_PRESENCE, {
        lobby_id: lobbyId
      });
      if (!response?.success) {
        throw new Error(response?.message || 'Failed to load server presence');
      }
      lobbyStore.updateServerPresence(response.presence?.players || [], {
        bridgeAvailable: response.presence?.bridgeAvailable,
        bridgeError: response.presence?.bridgeError || null
      });
    } catch (error) {
      console.error('Failed to fetch server presence:', error);
    }
  };

  const startServerPresencePolling = () => {
    if (serverPresencePoll.value) clearInterval(serverPresencePoll.value);
    fetchServerPresence();
    serverPresencePoll.value = setInterval(fetchServerPresence, 5000);
  };

  const stopServerPresencePolling = () => {
    if (serverPresencePoll.value) {
      clearInterval(serverPresencePoll.value);
      serverPresencePoll.value = null;
    }
  };

  const handleVoteMap = async (map) => {
    try {
      await socketStore.emit(SOCKET_EVENTS.LOBBY.VOTE_MAP, {
        lobby_id: lobbyStore.lobbyId,
        map
      });
      lobbyStore.mapVotes[authStore.username] = map;
    } catch (error) {
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
        clearCurrentLobby();
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

  onMounted(async () => {
    const lobbyId = route.params.lobbyId;
    if (lobbyStore.lobbyId && lobbyStore.lobbyId !== lobbyId) {
      lobbyStore.reset();
    }
    const hasCachedLobby = lobbyStore.lobbyId === lobbyId && lobbyStore.players?.length;
    lobbyStore.loading = !hasCachedLobby;

    try {
      let attempts = 0;
      while (!socketStore.isConnected) {
        await new Promise((resolve) => setTimeout(resolve, 100));
        if (attempts++ > 50) throw new Error('Socket connection timeout');
      }

      const events = [
        {
          event: SOCKET_EVENTS.LOBBY.UPDATE,
          handler: (data) => {
            if (data.teams && (data.teams.team1?.length || data.teams.team2?.length)) {
              lobbyStore.updateTeams(data.teams);
            }
            lobbyStore.updateLobbyState(data);
          }
        },
        {
          event: SOCKET_EVENTS.LOBBY.COUNTDOWN.VOTING,
          handler: (data) => {
            if (lobbyStore.step !== 2 && data?.countdown !== undefined && data.countdown <= 1) {
              return;
            }
            if (data.countdown !== undefined) {
              lobbyStore.updateVotingCountdown(data.countdown);
            }
            if (data.map_pool) lobbyStore.updateMapPool(data.map_pool);
            if (data.map_votes) lobbyStore.updateMapVotes(data.map_votes);
            if (data.vote_counts) lobbyStore.updateVoteCounts(data.vote_counts);
          }
        },
        {
          event: SOCKET_EVENTS.LOBBY.MAP_SELECTED,
          handler: async (data) => {
            await socketStore.emit(SOCKET_EVENTS.LOBBY.GET_DATA, { lobby_id: lobbyId });
            lobbyStore.updateLobbyState({
              selectedMap: data.map,
              step: 3,
              votingCountdown: null
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
            if (data.username === authStore.username) {
              lobbyStore.handleDisconnect();
            } else {
              lobbyStore.updatePlayerStatus(data.username, 'disconnected');
            }
          }
        },
        {
          event: 'player_reconnected',
          handler: (data) => lobbyStore.updatePlayerStatus(data.username, 'connected')
        },
        {
          event: 'player_left',
          handler: (data) => lobbyStore.removePlayer(data.username)
        }
      ];

      events.forEach(({ event, handler }) => {
        socketStore.on(event, handler);
        listeners.value.push({ event, handler });
      });

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

      const joinResponse = await socketStore.emit(SOCKET_EVENTS.LOBBY.JOIN, {
        lobby_id: lobbyId,
        username: authStore.username,
        rejoin: true
      });

      if (joinResponse?.success) {
        lobbyStore.updateLobbyState(joinResponse.data);
        startServerPresencePolling();
      } else {
        throw new Error(joinResponse?.message || 'Failed to join lobby');
      }
    } catch (error) {
      lobbyStore.leaveLobby();
      clearCurrentLobby();
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
    stopServerPresencePolling();
    listeners.value.forEach(({ event, handler }) => socketStore.off(event, handler));
    listeners.value = [];
    lobbyStore.reset();
    socketStore.off(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE);
  });

  return {
    activeCountdown,
    activeCountdownLabel,
    authStore,
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
    mapOptions,
    matchSizeLabel,
    phaseTitle,
    showPauseButton,
    skipPhase,
    toggleCountdownPause,
    prevPhase
  };
}
