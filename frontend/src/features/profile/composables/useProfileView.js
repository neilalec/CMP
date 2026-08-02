import { computed, onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useAuthStore } from '../../../stores/authStore';
import { useLobbyStore } from '../../../stores/lobbyStore';
import { useQueueStore } from '../../../stores/queueStore';
import { useRootStore } from '../../../stores/rootStore';
import { useSocketStore } from '../../../stores/socketStore';
import { clearCurrentLobby } from '../../../utils/lobbyPersistence';

export function useProfileView() {
  const authStore = useAuthStore();
  const queueStore = useQueueStore();
  const lobbyStore = useLobbyStore();
  const socketStore = useSocketStore();
  const rootStore = useRootStore();
  const router = useRouter();
  const displayName = ref('');
  const steamId = ref('');
  const hasSteamId = computed(() => !!authStore.steamId);

  const loadProfile = async () => {
    try {
      const profile = await authStore.syncProfile();
      displayName.value = profile?.display_name || authStore.playerName || '';
      steamId.value = profile?.steam_id || '';
    } catch (error) {
      rootStore.setError(error.message || 'Failed to load profile');
    }
  };

  onMounted(async () => {
    displayName.value = authStore.playerName || '';
    steamId.value = authStore.steamId || '';
    try {
      await queueStore.syncWithServer(authStore.username);
    } catch (error) {
      // ignore queue sync failures here
    }
    await loadProfile();
  });

  const handleLogout = async () => {
    if (!window.confirm('Are you sure you want to log out?')) return;

    try {
      await socketStore.cleanupSocket();
      lobbyStore.reset();
      queueStore.resetQueue();
      clearCurrentLobby();
      authStore.logout();
      await socketStore.initSocket();
      router.replace('/auth');
    } catch (error) {
      rootStore.setError('Logout failed');
    }
  };

  const handleDisplayNameSave = async () => {
    try {
      const profile = await authStore.updateDisplayName(displayName.value);
      displayName.value = profile?.display_name || authStore.playerName || '';
    } catch (error) {
      rootStore.setError(error.message || 'Failed to update display name');
    }
  };

  return {
    authStore,
    displayName,
    handleDisplayNameSave,
    handleLogout,
    hasSteamId,
    steamId
  };
}
