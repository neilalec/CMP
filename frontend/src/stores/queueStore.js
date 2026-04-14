import { defineStore } from 'pinia'
import { useSocketStore } from './socketStore'
import { useAuthStore } from './authStore'
import { SOCKET_EVENTS } from '../constants/socketEvents'

export const useQueueStore = defineStore('queue', {
  state: () => ({
    inQueue: false,
    playersInQueue: 0,
    queueList: [],
    openLobbies: [],
    activeLobbies: [],
    loading: false,
    error: null,
    lastSync: null,
    countdown: null,
    matchAccept: {
      active: false,
      cancelled: false,
      cancelReason: '',
      players: [],
      acceptedPlayers: [],
      acceptedCount: 0,
      requiredCount: 0,
      countdown: null,
      hasAccepted: false
    }
  }),

  actions: {
    updateQueueState(data) {
      if (!data) return;
      const authStore = useAuthStore();
      
      this.inQueue = !!data.inQueue;
      this.playersInQueue = data.playersInQueue || 0;
      this.queueList = Array.isArray(data.queue) ? data.queue : [];
      this.countdown = data.countdown || null;
      if (data.matchAccept?.active) {
        this.matchAccept = {
          active: true,
          cancelled: false,
          cancelReason: '',
          players: Array.isArray(data.matchAccept.players) ? data.matchAccept.players : [],
          acceptedPlayers: Array.isArray(data.matchAccept.acceptedPlayers) ? data.matchAccept.acceptedPlayers : [],
          acceptedCount: data.matchAccept.acceptedCount || 0,
          requiredCount: data.matchAccept.requiredCount || 0,
          countdown: data.matchAccept.countdown ?? null,
          hasAccepted: Array.isArray(data.matchAccept.acceptedPlayers)
            ? data.matchAccept.acceptedPlayers.includes(authStore.username)
            : !!data.matchAccept.hasAccepted
        };
      } else {
        this.resetMatchAccept();
      }
      this.error = null;
      this.lastSync = Date.now();
    },

    resetMatchAccept() {
      this.matchAccept = {
        active: false,
        cancelled: false,
        cancelReason: '',
        players: [],
        acceptedPlayers: [],
        acceptedCount: 0,
        requiredCount: 0,
        countdown: null,
        hasAccepted: false
      };
    },

    setMatchAcceptCancelled(reason = 'Match cancelled') {
      this.matchAccept = {
        active: false,
        cancelled: true,
        cancelReason: reason,
        players: [],
        acceptedPlayers: [],
        acceptedCount: 0,
        requiredCount: 0,
        countdown: null,
        hasAccepted: false
      };
    },

    updateOpenLobbies(list) {
      this.openLobbies = Array.isArray(list) ? list : [];
    },

    updateActiveLobbies(list) {
      this.activeLobbies = Array.isArray(list) ? list : [];
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

    async syncWithServer(username) {
      try {
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.STATUS, { username });
        this.updateQueueState(response);
      } catch (error) {
        this.error = error.message;
      }
    },

    resetQueue() {
      this.inQueue = false;
      this.playersInQueue = 0;
      this.queueList = [];
      this.openLobbies = [];
      this.activeLobbies = [];
      this.loading = false;
      this.error = null;
      this.lastSync = null;
      this.countdown = null;
      this.resetMatchAccept();
    },

    async acceptMatch(username) {
      this.loading = true;
      try {
        const authStore = useAuthStore();
        const socketStore = useSocketStore();
        const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.ACCEPT_MATCH, { username });
        if (!response?.success) {
          throw new Error(response?.message || 'Failed to accept match');
        }
        if (response.matchAccept?.active) {
          this.matchAccept = {
            active: true,
            players: Array.isArray(response.matchAccept.players) ? response.matchAccept.players : this.matchAccept.players,
            acceptedPlayers: Array.isArray(response.matchAccept.acceptedPlayers) ? response.matchAccept.acceptedPlayers : this.matchAccept.acceptedPlayers,
            acceptedCount: response.matchAccept.acceptedCount ?? this.matchAccept.acceptedCount,
            requiredCount: response.matchAccept.requiredCount ?? this.matchAccept.requiredCount,
            countdown: response.matchAccept.countdown ?? this.matchAccept.countdown,
            hasAccepted: Array.isArray(response.matchAccept.acceptedPlayers)
              ? response.matchAccept.acceptedPlayers.includes(authStore.username)
              : true
          };
        } else {
          this.matchAccept.hasAccepted = true;
        }
        return response;
      } catch (error) {
        this.error = error.message;
        throw error;
      } finally {
        this.loading = false;
      }
    }
  }
})
