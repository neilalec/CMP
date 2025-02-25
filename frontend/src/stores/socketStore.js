import { defineStore } from 'pinia';
import { socketService } from '../services/socketService';
import { useRootStore } from './rootStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { AppError } from '../utils/errorHandler';
import { useAuthStore } from './authStore';

export const useSocketStore = defineStore('socket', {
  state: () => ({
    isConnected: false,
    loading: false,
    reconnectAttempts: 0
  }),

  actions: {
    async initSocket(token = null, username = null, retryCount = 0) {
      const maxRetries = 3;
      const rootStore = useRootStore();
      
      console.log('Initializing socket connection...'); // Debug log
      
      try {
        this.loading = true;
        await socketService.connect(token, username);
        this.isConnected = true;
        console.log('Socket connected successfully');
      } catch (error) {
        console.error('Socket initialization error:', error);
        if (retryCount < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          return this.initSocket(token, username, retryCount + 1);
        }
        throw error;
      } finally {
        this.loading = false;
      }
    },

    cleanupSocket() {
      socketService.disconnect();
      this.isConnected = false;
      this.reconnectAttempts = 0;
    },

    // Proxy methods to socketService with error handling
    async emit(event, data, retryCount = 0) {
      const rootStore = useRootStore();
      const maxRetries = 2;
      
      try {
        return await socketService.emit(event, data);
      } catch (error) {
        if (error.message === 'Socket not connected' && retryCount < maxRetries) {
          await new Promise(resolve => setTimeout(resolve, 1000));
          return this.emit(event, data, retryCount + 1);
        }
        
        rootStore.setError(`Failed to emit ${event}: ${error.message}`);
        throw new AppError(error.message, 'SOCKET_ERROR', event);
      }
    },

    async checkConnection() {
      const status = {
        isConnected: this.isConnected,
        socketExists: !!socketService.socket,
        socketConnected: socketService.socket?.connected,
        socketId: socketService.socket?.id,
        transport: socketService.socket?.transport?.name
      };
      console.log('[Socket Debug] Connection status:', status);
      return status;
    },

    on(event, callback) {
      socketService.on(event, callback);
    },

    off(event, callback) {
      socketService.off(event, callback);
    }
  }
});