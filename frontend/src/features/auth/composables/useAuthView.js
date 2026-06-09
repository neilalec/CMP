import { ref } from 'vue';
import { API_BASE_URL } from '../../../config';
import { setCurrentLobbyId } from '../../../utils/lobbyPersistence';

export function useAuthView({
  router,
  authStore,
  rootStore,
  socketStore,
  lobbyStore
}) {
  const formType = ref('login');
  const username = ref('');
  const password = ref('');
  const loading = ref(false);

  const resetForm = () => {
    username.value = '';
    password.value = '';
    loading.value = false;
  };

  const handleSubmit = async () => {
    loading.value = true;
    rootStore.clearError();

    try {
      const eventType = formType.value === 'login' ? 'login' : 'register';
      const response = await socketStore.emit(eventType, {
        username: username.value,
        password: password.value
      });

      if (!response.success) {
        throw new Error(response.message || `${formType.value} failed`);
      }

      await authStore.setAuth(response.access_token, username.value, response.profile);

      if (response.active_lobby) {
        setCurrentLobbyId(response.active_lobby);
        router.push(`/lobby/${response.active_lobby}`);
        return;
      }

      lobbyStore.leaveLobby();
      router.push('/');
    } catch (error) {
      console.error(`${formType.value} error:`, error);
      rootStore.setError(error.message);
    } finally {
      loading.value = false;
    }
  };

  const toggleForm = () => {
    formType.value = formType.value === 'login' ? 'register' : 'login';
    rootStore.clearError();
    resetForm();
  };

  const handleSteamSignIn = () => {
    rootStore.clearError();
    const params = new URLSearchParams({
      frontend_origin: window.location.origin
    });
    window.location.href = `${API_BASE_URL}/auth/steam/start?${params.toString()}`;
  };

  return {
    formType,
    username,
    password,
    loading,
    handleSubmit,
    toggleForm,
    handleSteamSignIn
  };
}
