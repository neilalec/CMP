import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../../stores/authStore';
import { useLobbyStore } from '../../../stores/lobbyStore';
import { useQueueStore } from '../../../stores/queueStore';
import { useRootStore } from '../../../stores/rootStore';
import { useSocketStore } from '../../../stores/socketStore';

export function useProfileView() {
  const authStore = useAuthStore();
  const queueStore = useQueueStore();
  const lobbyStore = useLobbyStore();
  const socketStore = useSocketStore();
  const rootStore = useRootStore();
  const router = useRouter();
  const steamId = ref('');
  const loading = ref(false);
  const savingSteamId = ref(false);

  const isSteamIdLocked = computed(() => (
    loading.value ||
    savingSteamId.value ||
    queueStore.inQueue ||
    !!lobbyStore.lobbyId ||
    authStore.steamIdLocked
  ));
  const hasSteamId = computed(() => !!authStore.steamId);

  const loadProfile = async () => {
    loading.value = true;
    try {
      const profile = await authStore.syncProfile();
      steamId.value = profile?.steam_id || '';
    } catch (error) {
      rootStore.setError(error.message || 'Failed to load profile');
    } finally {
      loading.value = false;
    }
  };

  onMounted(async () => {
    steamId.value = authStore.steamId || '';
    try {
      await queueStore.syncWithServer(authStore.username);
    } catch (error) {
      // ignore queue sync failures here
    }
    await loadProfile();
  });

  const saveSteamId = async () => {
    savingSteamId.value = true;
    rootStore.clearError();
    try {
      const profile = await authStore.updateSteamId(steamId.value);
      steamId.value = profile?.steam_id || '';
    } catch (error) {
      rootStore.setError(error.message || 'Failed to save Steam ID');
    } finally {
      savingSteamId.value = false;
    }
  };

  const handleLogout = async () => {
    try {
      await socketStore.cleanupSocket();
      lobbyStore.reset();
      queueStore.resetQueue();
      authStore.logout();
      await socketStore.initSocket();
      router.push('/auth');
    } catch (error) {
      rootStore.setError('Logout failed');
    }
  };

  return {
    authStore,
    handleLogout,
    hasSteamId,
    isSteamIdLocked,
    saveSteamId,
    savingSteamId,
    socketStore,
    steamId
  };
}
