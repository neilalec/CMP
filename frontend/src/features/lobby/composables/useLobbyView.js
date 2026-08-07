import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../../../stores/authStore';
import { useGroupStore } from '../../../stores/groupStore';
import { useLobbyStore } from '../../../stores/lobbyStore';
import { useRootStore } from '../../../stores/rootStore';
import { useSocketStore } from '../../../stores/socketStore';
import { SOCKET_EVENTS } from '../../../constants/socketEvents';
import { clearCurrentLobby } from '../../../utils/lobbyPersistence';
import { API_BASE_URL } from '../../../config';
import { getLobbyPhaseTitle } from '../utils/lobbyPhase';

export function useLobbyView() {
  const router = useRouter();
  const route = useRoute();
  const lobbyStore = useLobbyStore();
  const groupStore = useGroupStore();
  const socketStore = useSocketStore();
  const rootStore = useRootStore();
  const authStore = useAuthStore();
  const isCountdownPaused = ref(false);
  const serverPresencePoll = ref(null);
  const liveRollTimer = ref(null);
  const listeners = ref([]);
  const handleCountdownPauseState = (data) => {
    if (data && typeof data.paused === 'boolean') {
      isCountdownPaused.value = data.paused;
    }
  };

  const AVAILABLE_MAPS = [
    'Al Basrah Skirmish v1',
    'Belaya Skirmish v1',
    'Chora Skirmish v1',
    "Fool's Road Skirmish v1",
    'Narva Skirmish v1'
  ];
  const HOTDROP_MAPS = [
    'HotDrop_SumariBala',
    'HotDrop_Narva',
    'HotDrop_Harju',
    'HotDrop_Goose_Bay',
    'HotDrop_BlackCoast',
    'HotDrop_Fallujah',
    'HotDrop_Mutaha',
    'HotDrop_Chora',
    'HotDrop_Yehorivka',
    'HotDrop_Skorpo'
  ];

  const activeCountdown = computed(() => {
    if (lobbyStore.step === 2) return lobbyStore.votingCountdown;
    if (lobbyStore.step === 3 && lobbyStore.liveRollCountdown !== null) return lobbyStore.liveRollCountdown;
    return null;
  });
  const activeCountdownLabel = computed(() => (
    lobbyStore.step === 3 ? 'Force Roll in' : 'Map selected in'
  ));
  const phaseTitle = computed(() => getLobbyPhaseTitle({
    step: lobbyStore.step,
    loading: lobbyStore.loading
  }));
  const lobbyPhase = computed(() => {
    if (lobbyStore.step === 5) return 'complete';
    if (lobbyStore.step === 4) return 'live';
    if (lobbyStore.step === 3) return 'server';
    return 'map';
  });
  const showPauseButton = computed(() => lobbyStore.step === 2 && activeCountdown.value !== null);
  const mapOptions = computed(() => {
    if (lobbyStore.mapPool?.length) return lobbyStore.mapPool;
    const isHotdropLobby = (
      lobbyStore.queueMode === 'hotdrop'
      || (lobbyStore.queueLabel || '').toLowerCase().includes('hotdrop')
      || lobbyStore.matchSizeLabel === '30v30'
      || lobbyStore.maxPlayers === 60
    );
    if (isHotdropLobby) return HOTDROP_MAPS;
    return AVAILABLE_MAPS;
  });
  const isDev = import.meta.env.DEV;
  const canAdminLobby = computed(() => !!authStore.isAdmin);
  const groupedTeam1 = computed(() => groupPlayers(lobbyStore.teams.team1));
  const groupedTeam2 = computed(() => groupPlayers(lobbyStore.teams.team2));
  const hasSteamLobbyId = computed(() => {
    const rawSteamLobbyId = (
      lobbyStore.serverDetails?.steamLobbyId
      || lobbyStore.serverDetails?.steam_lobby_id
      || ''
    );
    return /^\d{17,20}$/.test(String(rawSteamLobbyId).trim());
  });
  const canAutoConnect = computed(() => {
    const connectAddress = lobbyStore.serverDetails?.connectAddress || lobbyStore.serverDetails?.ip || '';
    return (hasSteamLobbyId.value || !!connectAddress) && (lobbyStore.step === 3 || lobbyStore.step === 4);
  });
  const canDirectConnect = computed(() => {
    const connectAddress = lobbyStore.serverDetails?.connectAddress || lobbyStore.serverDetails?.ip || '';
    return !!connectAddress && (lobbyStore.step === 3 || lobbyStore.step === 4);
  });
  const serverConnectedCount = computed(() => (
    lobbyStore.players.filter((player) => lobbyStore.serverPresence?.[player]?.connected).length
  ));
  const liveRollRequiredPercent = 95;
  const liveRollThresholdSeconds = 300;
  const liveRollRequiredCount = computed(() => {
    const total = lobbyStore.players.length;
    return total > 0 ? Math.ceil(total * (liveRollRequiredPercent / 100)) : 0;
  });
  const liveRollGraceSeconds = computed(() => {
    const providedAt = Number(lobbyStore.serverDetailsProvidedAt || 0);
    const readyAt = Number(lobbyStore.liveRollReadyAt || 0);
    const derivedSeconds = readyAt > providedAt ? Math.round(readyAt - providedAt) : 0;
    return derivedSeconds || 600;
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
  const getPlayerDisplayName = (player) => lobbyStore.getDisplayName(player);
  const getTeamLabel = (teamKey) => {
    return teamKey === 'team1' ? 'BLUFOR' : 'OPFOR';
  };
  const getServerPresence = (player) => lobbyStore.serverPresence?.[player] || null;
  const isServerConnected = (player) => !!getServerPresence(player)?.connected;
  const isServerTeamAligned = (player) => {
    const presence = getServerPresence(player);
    if (!presence?.connected) return false;
    return presence.teamAligned !== false;
  };
  const getConnectionFlagClass = (player) => {
    if (lobbyStore.serverPresenceAvailable === false) return 'is-unavailable';
    if (!isServerConnected(player)) return 'is-missing';
    return isServerTeamAligned(player) ? 'is-connected' : 'is-misaligned';
  };
  const showConnectionStatus = computed(() => lobbyStore.step >= 3);
  const getConnectionLabel = (player) => {
    if (lobbyStore.serverPresenceAvailable === false) return 'Unavailable';
    if (!isServerConnected(player)) return 'Missing';
    return isServerTeamAligned(player) ? 'Connected' : 'Wrong team';
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

  const updateLiveRollCountdown = () => {
    if (lobbyStore.step !== 3 || !lobbyStore.liveRollReadyAt) return;
    const remaining = Math.max(0, Math.ceil(lobbyStore.liveRollReadyAt - (Date.now() / 1000)));
    lobbyStore.updateLiveRollCountdown(remaining);
  };

  const startLiveRollTimer = () => {
    if (liveRollTimer.value) clearInterval(liveRollTimer.value);
    updateLiveRollCountdown();
    liveRollTimer.value = setInterval(updateLiveRollCountdown, 1000);
  };

  const stopLiveRollTimer = () => {
    if (liveRollTimer.value) {
      clearInterval(liveRollTimer.value);
      liveRollTimer.value = null;
    }
  };

  const connectToServer = async () => {
    const lobbyId = lobbyStore.lobbyId || route.params.lobbyId;
    if (!lobbyId) return;
    try {
      const response = await fetch(`${API_BASE_URL}/lobbies/${lobbyId}/join-link`, {
        headers: {
          Authorization: `Bearer ${authStore.token}`
        }
      });
      const payload = await response.json();
      if (!response.ok || !payload?.success || !payload?.join_url) {
        throw new Error(payload?.message || 'Failed to build server join link');
      }
      window.location.href = payload.join_url;
    } catch (error) {
      rootStore.setError({
        message: 'Failed to open Squad connect link',
        details: error.message,
        context: 'lobby-connect'
      });
    }
  };

  const directConnectToServer = () => {
    const connectAddress = lobbyStore.serverDetails?.connectAddress || lobbyStore.serverDetails?.ip || '';
    const serverPassword = lobbyStore.serverDetails?.password || '';
    if (!connectAddress) return;

    const joinUrl = serverPassword
      ? `steam://connect/${connectAddress}/${encodeURIComponent(serverPassword)}`
      : `steam://connect/${connectAddress}`;

    window.location.href = joinUrl;
  };

  const syncLobbyData = async (lobbyId = lobbyStore.lobbyId || route.params.lobbyId) => {
    if (!lobbyId) return null;
    const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.GET_DATA, { lobby_id: lobbyId });
    if (response?.success && response.data) {
      lobbyStore.updateLobbyState(response.data);
      if (response.data.live_roll_ready_at || lobbyStore.liveRollReadyAt) {
        startLiveRollTimer();
      }
      if (response.data.step && response.data.step !== 3) {
        stopLiveRollTimer();
      }
    }
    return response;
  };

  const handleVoteMap = async (map) => {
    if (lobbyStore.isSpectator) return;
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
    if (lobbyStore.isSpectator) {
      try {
        const lobbyId = lobbyStore.lobbyId || route.params.lobbyId;
        if (lobbyId) {
          await socketStore.emit(SOCKET_EVENTS.LOBBY.LEAVE, {
            lobby_id: lobbyId,
            username: authStore.username
          });
        }
      } catch (error) {
        // Spectator leave is best-effort; leaving the page removes local listeners.
      }
      lobbyStore.leaveLobby();
      router.push('/lobbies');
      return;
    }

    const leaveGroupToo = !!groupStore.inGroup;
    const confirmed = window.confirm(
      leaveGroupToo ? 'Leave lobby and group?' : 'Leave lobby?'
    );
    if (!confirmed) return;

    try {
      const lobbyId = lobbyStore.lobbyId || route.params.lobbyId;
      if (!lobbyId) return;
      const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.LEAVE, {
        lobby_id: lobbyId,
        username: authStore.username
      });
      if (response?.success) {
        let groupLeaveError = null;
        lobbyStore.leaveLobby();
        clearCurrentLobby();
        if (leaveGroupToo) {
          try {
            await groupStore.leaveGroup(authStore.username);
          } catch (error) {
            groupLeaveError = error;
          }
        }
        router.push('/');
        if (groupLeaveError) {
          rootStore.setError({
            message: 'Left lobby but failed to leave group',
            details: groupLeaveError.message,
            context: 'group-leave-after-lobby'
          });
        }
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
      if (!response?.success) {
        throw new Error(response?.message || 'Failed to toggle countdown pause');
      }
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
      const lobbyId = lobbyStore.lobbyId || route.params.lobbyId;
      const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.SKIP_PHASE, {
        lobby_id: lobbyId
      });
      if (!response?.success) {
        throw new Error(response?.message || 'Failed to skip phase');
      }
      if (response.data) {
        lobbyStore.updateLobbyState(response.data);
      } else {
        await syncLobbyData(lobbyId);
      }
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
      const lobbyId = lobbyStore.lobbyId || route.params.lobbyId;
      const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.PREV_PHASE, {
        lobby_id: lobbyId
      });
      if (!response?.success) {
        throw new Error(response?.message || 'Failed to go back a phase');
      }
      if (response.data) {
        lobbyStore.updateLobbyState(response.data);
      } else {
        await syncLobbyData(lobbyId);
      }
    } catch (error) {
      rootStore.setError({
        message: 'Failed to go back a phase',
        details: error.message,
        context: 'lobby-prev'
      });
    }
  };

  const deleteLobby = async () => {
    const confirmed = window.confirm('Delete this lobby and release its server allocation?');
    if (!confirmed) return;

    try {
      const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.DELETE, {
        lobby_id: lobbyStore.lobbyId || route.params.lobbyId
      });
      if (!response?.success) {
        throw new Error(response?.message || 'Failed to delete lobby');
      }
      lobbyStore.leaveLobby();
      clearCurrentLobby();
      router.push('/');
    } catch (error) {
      rootStore.setError({
        message: 'Failed to delete lobby',
        details: error.message,
        context: 'lobby-delete'
      });
    }
  };

  const forceLiveReady = async () => {
    try {
      const lobbyId = lobbyStore.lobbyId || route.params.lobbyId;
      const emitForceLiveReady = (forceLobbyReady = false) => socketStore.emit(SOCKET_EVENTS.LOBBY.FORCE_LIVE_READY, {
        lobby_id: lobbyId,
        force_lobby_ready: forceLobbyReady
      });
      const confirmForceLobbyReady = async () => {
        const confirmed = window.confirm('Force lobby as ready?');
        if (!confirmed) return false;

        return true;
      };

      if (lobbyStore.step !== 3) {
        const wasForcedReady = await confirmForceLobbyReady();
        if (!wasForcedReady) return;
      }

      const response = await emitForceLiveReady(lobbyStore.step !== 3);
      if (!response?.success) {
        const wasForcedReady = await confirmForceLobbyReady();
        if (!wasForcedReady) return;
        const retryResponse = await emitForceLiveReady(true);
        if (retryResponse?.success) {
          if (retryResponse.data) {
            lobbyStore.updateLobbyState(retryResponse.data);
          } else {
            await syncLobbyData(lobbyId);
          }
          return;
        }
        throw new Error(retryResponse?.message || response?.message || 'Failed to mark lobby ready');
      }
      if (response.data) {
        lobbyStore.updateLobbyState(response.data);
      } else {
        await syncLobbyData(lobbyId);
      }
    } catch (error) {
      rootStore.setError({
        message: 'Failed to force live readiness',
        details: error.message,
        context: 'lobby-force-live-ready'
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
            if (data.live_roll_ready_at || lobbyStore.liveRollReadyAt) {
              startLiveRollTimer();
            }
            if (data.step && data.step !== 3) {
              stopLiveRollTimer();
            }
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
              selected_map: data.map,
              step: 3,
              voting_countdown: null,
              server_details: data.server_details,
              team_labels: data.team_labels,
              server_details_provided_at: data.server_details_provided_at,
              live_roll_ready_at: data.live_roll_ready_at,
              live_roll_countdown: data.live_roll_countdown
            });
            startLiveRollTimer();
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

      socketStore.on(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE, handleCountdownPauseState);

      try {
        const response = await socketStore.emit(SOCKET_EVENTS.COUNTDOWN.STATUS);
        if (response && typeof response.paused === 'boolean') {
          isCountdownPaused.value = response.paused;
        }
      } catch (error) {
        // ignore
      }

      try {
        await authStore.syncProfile();
      } catch (error) {
        // ignore profile sync failures; the join response will still enforce access.
      }

      const wantsSpectator = route.query.spectate === '1';
      let joinResponse = await socketStore.emit(
        wantsSpectator ? SOCKET_EVENTS.LOBBY.SPECTATE : SOCKET_EVENTS.LOBBY.JOIN,
        wantsSpectator
          ? { lobby_id: lobbyId }
          : {
              lobby_id: lobbyId,
              username: authStore.username,
              rejoin: true
            }
      );

      if (!joinResponse?.success && authStore.isAdmin && !wantsSpectator) {
        joinResponse = await socketStore.emit(SOCKET_EVENTS.LOBBY.SPECTATE, {
          lobby_id: lobbyId
        });
      }

      if (joinResponse?.success) {
        lobbyStore.updateLobbyState(joinResponse.data);
        if (joinResponse.data?.live_roll_ready_at || lobbyStore.liveRollReadyAt) {
          startLiveRollTimer();
        }
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
    stopLiveRollTimer();
    listeners.value.forEach(({ event, handler }) => socketStore.off(event, handler));
    listeners.value = [];
    lobbyStore.reset();
    socketStore.off(SOCKET_EVENTS.COUNTDOWN.PAUSE_STATE, handleCountdownPauseState);
  });

  return {
    activeCountdown,
    activeCountdownLabel,
    authStore,
    canAdminLobby,
    canAutoConnect,
    canDirectConnect,
    connectToServer,
    directConnectToServer,
    getConnectionFlagClass,
    getConnectionLabel,
    getPlayerDisplayName,
    getTeamLabel,
    forceLiveReady,
    groupedTeam1,
    groupedTeam2,
    handleLeaveLobby,
    handleVoteMap,
    isCaptain,
    isCountdownPaused,
    isCurrentUser,
    isDev,
    lobbyStore,
    lobbyPhase,
    liveRollGraceSeconds,
    liveRollRequiredCount,
    liveRollRequiredPercent,
    liveRollThresholdSeconds,
    mapOptions,
    phaseTitle,
    showConnectionStatus,
    showPauseButton,
    serverConnectedCount,
    skipPhase,
    toggleCountdownPause,
    prevPhase,
    deleteLobby
  };
}
