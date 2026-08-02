import { defineStore } from 'pinia';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { createDefaultGroupState } from './state/groupState';
import { runStoreSocketAction } from './helpers/storeSocketAction';

export const useGroupStore = defineStore('group', {
  state: () => createDefaultGroupState(),

  getters: {
    inGroup: (state) => !!state.code,
    getDisplayName: (state) => (username) => {
      return state.playerProfiles?.[username]?.display_name || username;
    },
  },

  actions: {
    setGroup(group) {
      if (!group) {
        this.resetGroup();
        return;
      }
      this.code = group.code || null;
      this.leader = group.leader || null;
      this.members = Array.isArray(group.members) ? group.members : [];
      this.playerProfiles = group.player_profiles || group.playerProfiles || {};
      this.lastSync = Date.now();
      this.error = null;
    },

    handleUpdate(payload) {
      if (payload?.group) {
        this.setGroup(payload.group);
        return;
      }
      if (payload && payload.group === null) {
        this.resetGroup();
      }
    },

    async createGroup(username) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.GROUP.CREATE,
        payload: { username },
        fallbackMessage: 'Failed to create group',
        validate: (response) => {
          if (!response?.success || !response?.group) {
            throw new Error(response?.message || 'Failed to create group');
          }
        },
        onSuccess: (response) => {
          this.setGroup(response.group);
        }
      });
    },

    async joinGroup(username, code) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.GROUP.JOIN,
        payload: { username, code },
        fallbackMessage: 'Failed to join group',
        validate: (response) => {
          if (!response?.success || !response?.group) {
            throw new Error(response?.message || 'Failed to join group');
          }
        },
        onSuccess: (response) => {
          this.setGroup(response.group);
        }
      });
    },

    async leaveGroup(username) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.GROUP.LEAVE,
        payload: { username },
        fallbackMessage: 'Failed to leave group',
        validate: (response) => {
          if (!response?.success) {
            throw new Error(response?.message || 'Failed to leave group');
          }
        },
        onSuccess: () => {
          this.resetGroup();
        }
      });
    },

    async transferOwnership(username, targetUsername) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.GROUP.TRANSFER,
        payload: { username, targetUsername },
        fallbackMessage: 'Failed to transfer group ownership',
        validate: (response) => {
          if (!response?.success || !response?.group) {
            throw new Error(response?.message || 'Failed to transfer group ownership');
          }
        },
        onSuccess: (response) => {
          this.setGroup(response.group);
        }
      });
    },

    async kickMember(username, targetUsername) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.GROUP.KICK,
        payload: { username, targetUsername },
        fallbackMessage: 'Failed to kick group member',
        validate: (response) => {
          if (!response?.success || !response?.group) {
            throw new Error(response?.message || 'Failed to kick group member');
          }
        },
        onSuccess: (response) => {
          this.setGroup(response.group);
        }
      });
    },

    async syncStatus(username) {
      await runStoreSocketAction(this, {
        event: SOCKET_EVENTS.GROUP.STATUS,
        payload: { username },
        setLoading: false,
        swallowError: true,
        fallbackMessage: 'Failed to sync group status',
        onSuccess: (response) => {
          if (response?.success) {
          this.setGroup(response.group || null);
          }
        }
      });
    },

    async queueGroup(username, queueMode) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.GROUP.QUEUE,
        payload: { username, queueMode },
        fallbackMessage: 'Failed to queue group',
        validate: (response) => {
          if (!response?.success) {
            throw new Error(response?.message || 'Failed to queue group');
          }
        }
      });
    },

    async unqueueGroup(username, queueMode) {
      return runStoreSocketAction(this, {
        event: SOCKET_EVENTS.GROUP.UNQUEUE,
        payload: { username, queueMode },
        fallbackMessage: 'Failed to leave queue',
        validate: (response) => {
          if (!response?.success) {
            throw new Error(response?.message || 'Failed to leave queue');
          }
        }
      });
    },

    resetGroup() {
      Object.assign(this, createDefaultGroupState());
    }
  }
});
