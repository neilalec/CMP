import { defineStore } from 'pinia';
import { useSocketStore } from './socketStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';

export const useGroupStore = defineStore('group', {
  state: () => ({
    code: null,
    leader: null,
    members: [],
    loading: false,
    error: null,
    lastSync: null
  }),

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
      this.loading = true;
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.GROUP.CREATE, { username });
        if (response?.success && response?.group) {
          this.setGroup(response.group);
        } else {
          throw new Error(response?.message || 'Failed to create group');
        }
        return response;
      } catch (error) {
        this.error = error.message;
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async joinGroup(username, code) {
      this.loading = true;
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.GROUP.JOIN, { username, code });
        if (response?.success && response?.group) {
          this.setGroup(response.group);
        } else {
          throw new Error(response?.message || 'Failed to join group');
        }
        return response;
      } catch (error) {
        this.error = error.message;
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async leaveGroup(username) {
      this.loading = true;
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.GROUP.LEAVE, { username });
        if (response?.success) {
          this.resetGroup();
        } else {
          throw new Error(response?.message || 'Failed to leave group');
        }
        return response;
      } catch (error) {
        this.error = error.message;
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async syncStatus(username) {
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.GROUP.STATUS, { username });
        if (response?.success) {
          this.setGroup(response.group || null);
        }
      } catch (error) {
        this.error = error.message;
      }
    },

    async queueGroup(username) {
      this.loading = true;
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.GROUP.QUEUE, { username });
        if (!response?.success) {
          throw new Error(response?.message || 'Failed to queue group');
        }
        return response;
      } catch (error) {
        this.error = error.message;
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async unqueueGroup(username) {
      this.loading = true;
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.GROUP.UNQUEUE, { username });
        if (!response?.success) {
          throw new Error(response?.message || 'Failed to leave queue');
        }
        return response;
      } catch (error) {
        this.error = error.message;
        throw error;
      } finally {
        this.loading = false;
      }
    },

    resetGroup() {
      this.code = null;
      this.leader = null;
      this.members = [];
      this.loading = false;
      this.error = null;
      this.lastSync = null;
    }
  }
});
