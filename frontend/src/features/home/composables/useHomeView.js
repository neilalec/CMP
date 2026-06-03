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
  const MAX_PLAYERS = 2;

  const isInLobby = computed(() => !!lobbyStore.lobbyId || !!getCurrentLobbyId());
  const isInGroup = computed(() => groupStore.inGroup);
  const isGroupLeader = computed(() => {
    if (!groupStore.leader || !authStore.username) return false;
    return groupStore.leader.toLowerCase() === authStore.username.toLowerCase();
  });
  const isQueueFull = computed(() => queueStore.playersInQueue >= MAX_PLAYERS);
  const activeView = computed(() => {
    if (route.path === '/queue') return 'queue';
    if (route.path === '/lobbies') return 'lobbies';
    return null;
  });

  const handleQueueUpdate = (data) => {
    queueStore.updateQueueState({
      ...data,
      inQueue: data.queue?.includes(authStore.username)
    });
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

  const joinQueue = async () => {
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
        const response = await groupStore.queueGroup(authStore.username);
        if (response?.queue) {
          queueStore.updateQueueState({
            ...response,
            inQueue: response.queue.includes(authStore.username)
          });
        }
      } else {
        await queueStore.joinQueue(authStore.username);
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

  const leaveQueue = async () => {
    if (isInGroup.value && !isGroupLeader.value) {
      rootStore.setError('Only the group leader can leave the queue. Leave the group to exit.');
      return;
    }
    loading.value = true;
    try {
      if (isInGroup.value && isGroupLeader.value) {
        const response = await groupStore.unqueueGroup(authStore.username);
        if (response?.queue) {
          queueStore.updateQueueState({
            ...response,
            inQueue: response.queue.includes(authStore.username)
          });
        } else {
          queueStore.updateQueueState({
            inQueue: false,
            playersInQueue: queueStore.playersInQueue,
            queue: queueStore.queueList
          });
        }
      } else {
        await queueStore.leaveQueue(authStore.username);
      }
    } finally {
      loading.value = false;
    }
  };

  const seedQueue = async (count = 20) => {
    loading.value = true;
    try {
      const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.SEED, { count });
      if (!response?.success) {
        throw new Error(response?.message || 'Failed to seed queue');
      }
    } catch (error) {
      rootStore.setError(error.message || 'Failed to seed queue');
    } finally {
      loading.value = false;
    }
  };

  const clearQueue = async () => {
    loading.value = true;
    try {
      const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.CLEAR);
      if (!response?.success) {
        throw new Error(response?.message || 'Failed to clear queue');
      }
    } catch (error) {
      rootStore.setError(error.message || 'Failed to clear queue');
    } finally {
      loading.value = false;
    }
  };

  const getLobbyLabel = (lobby) => {
    const maxPlayers = Number(lobby?.max_players || MAX_PLAYERS);
    const left = Math.floor(maxPlayers / 2);
    const right = maxPlayers - left;
    const mapLabel = lobby?.selected_map || 'Map TBD';
    return `${left}vs${right} - ${mapLabel}`;
  };

  return {
    MAX_PLAYERS,
    activeView,
    authStore,
    clearQueue,
    getLobbyLabel,
    groupStore,
    handleOpenLobbiesUpdate,
    handleQueueUpdate,
    isDev,
    isGroupLeader,
    isInGroup,
    isInLobby,
    isQueueFull,
    joinOpenLobby,
    joinQueue,
    leaveQueue,
    loading,
    queueStore
  };
}
