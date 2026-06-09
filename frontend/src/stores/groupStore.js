import { defineStore } from 'pinia';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { createDefaultGroupState } from './state/groupState';
import { runStoreSocketAction } from './helpers/storeSocketAction';

export const useGroupStore = defineStore('group', {
  state: () => createDefaultGroupState(),

  getters: {
    inGroup: (state) => !!state.code,
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
