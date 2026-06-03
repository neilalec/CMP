import { onMounted, ref } from 'vue';
import { useAuthStore } from '../../../stores/authStore';
import { useGroupStore } from '../../../stores/groupStore';
import { useRootStore } from '../../../stores/rootStore';

export function useGroupView() {
  const authStore = useAuthStore();
  const groupStore = useGroupStore();
  const rootStore = useRootStore();
  const joinCode = ref('');

  onMounted(async () => {
    if (authStore.username) {
      await groupStore.syncStatus(authStore.username);
    }
  });

  const handleCreate = async () => {
    try {
      await groupStore.createGroup(authStore.username);
    } catch (error) {
      rootStore.setError(error.message || 'Failed to create group');
    }
  };

  const handleJoin = async () => {
    const code = joinCode.value.trim().toUpperCase();
    if (!code) {
      rootStore.setError('Enter a group code.');
      return;
    }
    try {
      await groupStore.joinGroup(authStore.username, code);
      joinCode.value = '';
    } catch (error) {
      rootStore.setError(error.message || 'Failed to join group');
    }
  };

  const handleLeave = async () => {
    try {
      await groupStore.leaveGroup(authStore.username);
    } catch (error) {
      rootStore.setError(error.message || 'Failed to leave group');
    }
  };

  return {
    authStore,
    groupStore,
    handleCreate,
    handleJoin,
    handleLeave,
    joinCode
  };
}
