import { defineStore } from 'pinia'
import { useSocketStore } from './socketStore'
import { SOCKET_EVENTS } from '../constants/socketEvents'

export const useQueueStore = defineStore('queue', {
  state: () => ({
    inQueue: false,
    playersInQueue: 0,
    queueList: [],
    loading: false,
    error: null
  }),

  actions: {
    setLoading(status) {
      this.loading = status;
    },

    setError(error) {
      this.error = error;
    },

    updateQueueState(data) {
      if (!data) return;
      
      // Handle both direct and response formats
      const queueData = data.success !== undefined ? data : { success: true, ...data };
      
      if (queueData.success) {
        this.inQueue = !!queueData.inQueue;
        this.playersInQueue = queueData.playersInQueue || 0;
        this.queueList = Array.isArray(queueData.queue) ? queueData.queue : [];
        this.countdown = queueData.countdown || null;
        this.error = null;
      } else {
        this.error = queueData.message || 'Failed to update queue state';
      }
    },

    async joinQueue(username) {
      const socketStore = useSocketStore();
      this.setLoading(true);
      try {
        const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.JOIN, { username });
        this.updateQueueState(response);
        return response;
      } catch (error) {
        this.setError(error.message);
        throw error;
      } finally {
        this.setLoading(false);
      }
    },

    async leaveQueue(username) {
      const socketStore = useSocketStore();
      this.setLoading(true);
      try {
        console.log('[Queue Debug] Starting leave queue operation:', {
          username,
          event: SOCKET_EVENTS.QUEUE.LEAVE,
          currentState: {
            inQueue: this.inQueue,
            playersInQueue: this.playersInQueue,
            queueList: this.queueList
          }
        });

        // Verify socket connection before emit
        const socketStatus = await socketStore.checkConnection();
        console.log('[Queue Debug] Socket status:', socketStatus);

        const response = await socketStore.emit(SOCKET_EVENTS.QUEUE.LEAVE, { 
          username,
          timestamp: Date.now() // Add timestamp for debugging
        });
        
        console.log('[Queue Debug] Leave queue response:', response);
        this.updateQueueState(response);
        
        return response;
      } catch (error) {
        console.error('[Queue Debug] Leave queue error:', {
          error,
          errorType: error.constructor.name,
          errorMessage: error.message,
          stack: error.stack
        });
        this.setError(error.message);
        throw error;
      } finally {
        this.setLoading(false);
      }
    },

    resetQueue() {
      this.inQueue = false;
      this.playersInQueue = 0;
      this.queueList = [];
      this.loading = false;
      this.error = null;
    }
  }
})
