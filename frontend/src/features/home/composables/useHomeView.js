import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../../../stores/authStore';
import { useGroupStore } from '../../../stores/groupStore';
import { useLobbyStore } from '../../../stores/lobbyStore';
import { useQueueStore } from '../../../stores/queueStore';
import { useRootStore } from '../../../stores/rootStore';
import { useSocketStore } from '../../../stores/socketStore';
import { SOCKET_EVENTS } from '../../../constants/socketEvents';
import { getCurrentLobbyId, setCurrentLobbyId } from '../../../utils/lobbyPersistence';

export function useHomeView() {
  const router = useRouter();
  const route = useRoute();
  const queueStore = useQueueStore();
  const socketStore = useSocketStore();
  const authStore = useAuthStore();
  const lobbyStore = useLobbyStore();
  const groupStore = useGroupStore();
  const rootStore = useRootStore();

  const loading = ref(false);
  const isDev = import.meta.env.DEV;
  const canManageQueueTools = computed(() => isDev && !!authStore.isAdmin);
  const queueModes = computed(() => Object.values(queueStore.queueModes || {}));

  const isInLobby = computed(() => !!lobbyStore.lobbyId || !!getCurrentLobbyId());
  const isInGroup = computed(() => groupStore.inGroup);
  const isGroupLeader = computed(() => {
    if (!groupStore.leader || !authStore.username) return false;
    return groupStore.leader.toLowerCase() === authStore.username.toLowerCase();
  });
  const dashboardPhase = computed(() => {
    if (isInLobby.value) return 'map';
    if (queueStore.matchAccept.active || queueStore.matchAccept.cancelled) return 'accept';
    return 'queue';
  });
  const profileStatusLabel = computed(() => (authStore.hasSteamId ? 'Steam ID ready' : 'Steam ID required'));
  const groupStatusLabel = computed(() => {
    if (!isInGroup.value) return 'Solo queue ready';
    if (isGroupLeader.value) return `Leading ${groupStore.members.length} player group`;
    return `Grouped with ${groupStore.leader || 'leader'}`;
  });
  const lobbyStatusLabel = computed(() => {
    const open = queueStore.openLobbies.length;
    const active = queueStore.activeLobbies.length;
    return `${open} open / ${active} active`;
  });
  const currentQueueMode = computed(() => queueStore.queueMode);
  const serverAvailable = computed(() => queueStore.serverAvailable);
  const activeView = computed(() => {
    if (route.path === '/play' || route.path === '/') return 'queue';
    if (route.path === '/lobbies') return 'lobbies';
    return 'queue';
  });

  const handleQueueUpdate = (data) => {
    queueStore.updateQueueState(data);
  };

  const handleOpenLobbiesUpdate = (data) => {
    if (data?.openLobbies) {
      queueStore.updateOpenLobbies(data.openLobbies);
    }
    if (data?.activeLobbies) {
      queueStore.updateActiveLobbies(data.activeLobbies);
    }
  };

  onMounted(async () => {
    while (!socketStore.isConnected) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    try {
      await authStore.syncProfile();
    } catch (error) {
      // ignore profile sync failures here and let the profile page surface them explicitly
    }

    await queueStore.syncWithServer(authStore.username);

    try {
      const openLobbies = await socketStore.emit(SOCKET_EVENTS.OPEN_LOBBIES.STATUS);
      if (openLobbies?.openLobbies) {
        queueStore.updateOpenLobbies(openLobbies.openLobbies);
      }
      if (openLobbies?.activeLobbies) {
        queueStore.updateActiveLobbies(openLobbies.activeLobbies);
      }
    } catch (error) {
      // ignore
    }

    socketStore.on(SOCKET_EVENTS.QUEUE.UPDATE, handleQueueUpdate);
    socketStore.on(SOCKET_EVENTS.OPEN_LOBBIES.UPDATE, handleOpenLobbiesUpdate);
  });

  onBeforeUnmount(() => {
    socketStore.off(SOCKET_EVENTS.QUEUE.UPDATE, handleQueueUpdate);
    socketStore.off(SOCKET_EVENTS.OPEN_LOBBIES.UPDATE, handleOpenLobbiesUpdate);
  });

  const getQueueProgressPercent = (modeId) => {
    const queue = queueStore.queueModes?.[modeId];
    if (!queue?.maxPlayers) return 0;
    return Math.min(100, Math.round((queue.playersInQueue / queue.maxPlayers) * 100));
  };

  const isModeQueueFull = (modeId) => {
    const queue = queueStore.queueModes?.[modeId];
    return !!queue && queue.playersInQueue >= queue.maxPlayers;
  };

  const joinQueue = async (queueMode) => {
    if (isInLobby.value) {
      rootStore.setError('You are already in a lobby. Return to the lobby to continue.');
      return;
    }
    if (!authStore.hasSteamId) {
      rootStore.setError('Set your Steam ID in your profile before joining the queue.');
      return;
    }
    if (isInGroup.value && !isGroupLeader.value) {
      rootStore.setError('Only the group leader can queue the group.');
      return;
    }
    loading.value = true;
    try {
      if (isInGroup.value && isGroupLeader.value) {
        const response = await groupStore.queueGroup(authStore.username, queueMode);
        if (response?.queue) {
          queueStore.updateQueueState({
            ...response,
            inQueue: true
          });
        }
      } else {
        await queueStore.joinQueue(authStore.username, queueMode);
      }
    } finally {
      loading.value = false;
    }
  };

  const joinOpenLobby = async (lobbyId) => {
    if (isInLobby.value) {
      rootStore.setError('You are already in a lobby. Return to the lobby to continue.');
      return;
    }
    loading.value = true;
    try {
      const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.JOIN, {
        lobby_id: lobbyId,
        username: authStore.username,
        allow_new: true
      });
      if (response?.success) {
        setCurrentLobbyId(lobbyId);
        router.push(`/lobby/${lobbyId}`);
      } else {
        throw new Error(response?.message || 'Failed to join lobby');
      }
    } catch (error) {
      rootStore.setError(error.message || 'Failed to join lobby');
    } finally {
      loading.value = false;
    }
  };

  const leaveQueue = async (queueMode = null) => {
    if (isInGroup.value && !isGroupLeader.value) {
      rootStore.setError('Only the group leader can leave the queue. Leave the group to exit.');
      return;
    }
    loading.value = true;
    try {
      if (isInGroup.value && isGroupLeader.value) {
        const response = await groupStore.unqueueGroup(authStore.username, queueMode || currentQueueMode.value);
        if (response?.queue) {
          queueStore.updateQueueState({
            ...response,
            inQueue: false
          });
        } else {
          queueStore.updateQueueState({
            inQueue: false,
            queueMode: null,
            queueModes: queueStore.queueModes
          });
        }
      } else {
        await queueStore.leaveQueue(authStore.username, queueMode || currentQueueMode.value);
      }
    } finally {
      loading.value = false;
    }
  };

  const seedQueue = async (queueMode, count = null) => {
    if (!canManageQueueTools.value) {
      rootStore.setError('Admin access required.');
      return;
    }
    loading.value = true;
    try {
      const queue = queueStore.queueModes?.[queueMode];
      const seedCount = count ?? Math.max(0, (queue?.maxPlayers || 0) - (queue?.playersInQueue || 0));
      await queueStore.seedQueue(seedCount, queueMode);
    } catch (error) {
      rootStore.setError(error.message || 'Failed to seed queue');
    } finally {
      loading.value = false;
    }
  };

  const clearQueue = async (queueMode = null) => {
    if (!canManageQueueTools.value) {
      rootStore.setError('Admin access required.');
      return;
    }
    loading.value = true;
    try {
      await queueStore.clearQueue(queueMode);
    } catch (error) {
      rootStore.setError(error.message || 'Failed to clear queue');
    } finally {
      loading.value = false;
    }
  };

  const getLobbyLabel = (lobby) => {
    const maxPlayers = Number(lobby?.max_players || 0);
    const left = Math.floor(maxPlayers / 2);
    const right = maxPlayers - left;
    const mapLabel = lobby?.selected_map || 'Map TBD';
    const modeLabel = lobby?.queue_label || `${left}v${right}`;
    return `${modeLabel} - ${mapLabel}`;
  };

  return {
    activeView,
    authStore,
    canManageQueueTools,
    clearQueue,
    currentQueueMode,
    dashboardPhase,
    getLobbyLabel,
    getQueueProgressPercent,
    groupStore,
    groupStatusLabel,
    handleOpenLobbiesUpdate,
    handleQueueUpdate,
    isDev,
    isGroupLeader,
    isInGroup,
    isInLobby,
    isModeQueueFull,
    joinOpenLobby,
    joinQueue,
    leaveQueue,
    lobbyStatusLabel,
    loading,
    profileStatusLabel,
    queueModes,
    serverAvailable,
    seedQueue,
    queueStore
  };
}
