import { computed, onMounted, ref } from 'vue';
import { useAuthStore } from '../../../stores/authStore';
import { useGroupStore } from '../../../stores/groupStore';
import { useQueueStore } from '../../../stores/queueStore';
import { useRootStore } from '../../../stores/rootStore';

export function useGroupView() {
  const authStore = useAuthStore();
  const groupStore = useGroupStore();
  const queueStore = useQueueStore();
  const rootStore = useRootStore();
  const joinCode = ref('');
  const isGroupLeader = computed(() => (
    !!authStore.username
    && !!groupStore.leader
    && groupStore.leader.toLowerCase() === authStore.username.toLowerCase()
  ));
  const getMemberDisplayName = (username) => groupStore.getDisplayName(username);

  onMounted(async () => {
    if (authStore.username) {
      await queueStore.syncWithServer(authStore.username);
      await groupStore.syncStatus(authStore.username);
    }
  });

  const currentQueueLabel = computed(() => (
    queueStore.currentQueueConfig?.shortLabel
    || queueStore.currentQueueConfig?.label
    || 'a queue'
  ));

  const queuedGroupBlockMessage = computed(() => (
    `Leave ${currentQueueLabel.value} before creating or joining a group.`
  ));

  const handleCreate = async () => {
    if (queueStore.inQueue) {
      rootStore.setError(queuedGroupBlockMessage.value);
      return;
    }

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
    if (queueStore.inQueue) {
      rootStore.setError(queuedGroupBlockMessage.value);
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
    if (!window.confirm('Are you sure you want to leave this group?')) return;

    try {
      await groupStore.leaveGroup(authStore.username);
    } catch (error) {
      rootStore.setError(error.message || 'Failed to leave group');
    }
  };

  const handleTransferOwnership = async (targetUsername) => {
    if (!targetUsername) return;
    if (!window.confirm(`Transfer group ownership to ${getMemberDisplayName(targetUsername)}?`)) return;

    try {
      await groupStore.transferOwnership(authStore.username, targetUsername);
    } catch (error) {
      rootStore.setError(error.message || 'Failed to transfer group ownership');
    }
  };

  const handleKickMember = async (targetUsername) => {
    if (!targetUsername) return;
    if (!window.confirm(`Kick ${getMemberDisplayName(targetUsername)} from the group?`)) return;

    try {
      await groupStore.kickMember(authStore.username, targetUsername);
    } catch (error) {
      rootStore.setError(error.message || 'Failed to kick group member');
    }
  };

  return {
    authStore,
    groupStore,
    handleCreate,
    handleJoin,
    handleKickMember,
    handleLeave,
    handleTransferOwnership,
    getMemberDisplayName,
    isGroupLeader,
    joinCode
  };
}
