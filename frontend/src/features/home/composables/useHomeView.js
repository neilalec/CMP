import { computed, onMounted, onBeforeUnmount, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '../../../stores/authStore';
import { useGroupStore } from '../../../stores/groupStore';
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
  const groupStore = useGroupStore();
  const rootStore = useRootStore();

  const loading = ref(false);
  let isDisposed = false;
  const isDev = import.meta.env.DEV;
  const queueDisplayOrder = ['ocbt15', 'ocbt5', 'ocbt1', 'ocbt2', 'ocbt3', 'ocbt4'];
  const canManageQueueTools = computed(() => !!authStore.isAdmin);
  const queueModes = computed(() => (
    queueDisplayOrder
      .map((modeId) => queueStore.queueModes?.[modeId])
      .filter(Boolean)
  ));

  const isInLobby = computed(() => !!getCurrentLobbyId());
  const isInGroup = computed(() => groupStore.inGroup);
  const canBypassSteamIdForLocalDev = computed(() => (
    isDev && authStore.username?.trim().toLowerCase() === 'sam'
  ));
  const isGroupLeader = computed(() => {
    if (!groupStore.leader || !authStore.username) return false;
    return groupStore.leader.toLowerCase() === authStore.username.toLowerCase();
  });
  const currentQueueMode = computed(() => queueStore.queueMode);
  const serverAvailable = computed(() => queueStore.serverAvailable);
  const serverAvailabilityReason = computed(() => queueStore.serverAvailabilityReason);
  const activeView = computed(() => (route.path.startsWith('/lobbies') ? 'lobbies' : 'queue'));

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
      if (isDisposed) return;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }
    if (isDisposed) return;

    try {
      await authStore.syncProfile();
    } catch (error) {
      // ignore profile sync failures here and let the profile page surface them explicitly
    }

    await queueStore.syncWithServer(authStore.username);
    if (isDisposed) return;

    try {
      const openLobbies = await socketStore.emit(SOCKET_EVENTS.OPEN_LOBBIES.STATUS);
      if (isDisposed) return;
      if (openLobbies?.openLobbies) {
        queueStore.updateOpenLobbies(openLobbies.openLobbies);
      }
      if (openLobbies?.activeLobbies) {
        queueStore.updateActiveLobbies(openLobbies.activeLobbies);
      }
    } catch (error) {
      // ignore
    }

    socketStore.on(SOCKET_EVENTS.OPEN_LOBBIES.UPDATE, handleOpenLobbiesUpdate);
  });

  onBeforeUnmount(() => {
    isDisposed = true;
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
    if (!authStore.hasSteamId && !canBypassSteamIdForLocalDev.value) {
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

  const spectateLobby = (lobbyId) => {
    if (!authStore.isAdmin || !lobbyId) {
      rootStore.setError('Admin access required.');
      return;
    }
    router.push(`/lobby/${lobbyId}?spectate=1`);
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

  const deleteLobby = async (lobbyId) => {
    if (!authStore.isAdmin) {
      rootStore.setError('Admin access required.');
      return;
    }
    const confirmed = window.confirm('Delete this lobby and release its server allocation?');
    if (!confirmed) return;

    loading.value = true;
    try {
      const response = await socketStore.emit(SOCKET_EVENTS.LOBBY.DELETE, {
        lobby_id: lobbyId
      });
      if (!response?.success) {
        throw new Error(response?.message || 'Failed to delete lobby');
      }
    } catch (error) {
      rootStore.setError(error.message || 'Failed to delete lobby');
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

  const setQueueEnabled = async (queueMode, enabled) => {
    if (!canManageQueueTools.value) {
      rootStore.setError('Admin access required.');
      return;
    }
    loading.value = true;
    try {
      await queueStore.setQueueEnabled(queueMode, enabled);
    } catch (error) {
      rootStore.setError(error.message || 'Failed to update queue availability');
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
    canBypassSteamIdForLocalDev,
    clearQueue,
    currentQueueMode,
    deleteLobby,
    getLobbyLabel,
    getQueueProgressPercent,
    groupStore,
    isGroupLeader,
    isInGroup,
    isInLobby,
    isModeQueueFull,
    joinOpenLobby,
    joinQueue,
    leaveQueue,
    loading,
    queueModes,
    serverAvailable,
    serverAvailabilityReason,
    seedQueue,
    setQueueEnabled,
    spectateLobby,
    queueStore
  };
}
