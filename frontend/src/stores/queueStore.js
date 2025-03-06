import { defineStore } from 'pinia'
import { useSocketStore } from './socketStore'
import { SOCKET_EVENTS } from '../constants/socketEvents'

export const useQueueStore = defineStore('queue', {
  state: () => ({
    inQueue: false,
    playersInQueue: 0,
    queueList: [],
    loading: false,
    error: null,
    lastSync: null,
    countdown: null
  }),

  actions: {
    updateQueueState(data) {
      if (!data) return;
      
      this.inQueue = !!data.inQueue;
      this.playersInQueue = data.playersInQueue || 0;
      this.queueList = Array.isArray(data.queue) ? data.queue : [];
      this.countdown = data.countdown || null;
      this.error = null;
      this.lastSync = Date.now();
    },

    async joinQueue(username) {
      this.loading = true;
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.JOIN, { username });
        this.updateQueueState(response);
      } catch (error) {
        this.error = error.message;
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async leaveQueue(username) {
      this.loading = true;
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.LEAVE, { username });
        this.updateQueueState(response);
      } catch (error) {
        this.error = error.message;
        throw error;
      } finally {
        this.loading = false;
      }
    },

    async syncWithServer() {
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.STATUS);
        this.updateQueueState(response);
      } catch (error) {
        this.error = error.message;
      }
    },

    resetQueue() {
      this.inQueue = false;
      this.playersInQueue = 0;
      this.queueList = [];
      this.loading = false;
      this.error = null;
      this.lastSync = null;
    }
  }
})
