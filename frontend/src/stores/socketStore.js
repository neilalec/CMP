import { defineStore } from 'pinia';
import { socketService } from '../services/socketService';
import { useRootStore } from './rootStore';
import { AppError } from '../utils/errorHandler';

export const useSocketStore = defineStore('socket', {
  state: () => ({
    isConnected: false,
    loading: false,
    reconnectAttempts: 0,
    lastError: null
  }),

  actions: {
    async initSocket(token = null, username = null) {
      const rootStore = useRootStore();
      
      console.log('SocketStore initSocket called with:', { token, username });
      
      try {
        this.loading = true;
        this.lastError = null;

        await socketService.connect(token, username);

        this.isConnected = true;
        console.log('Socket connection established');

        if (import.meta.env.DEV) {
          window.socket = socketService.socket;
        }
        
        return true;
      } catch (error) {
        this.isConnected = false;
        this.lastError = error.message;
        console.error('Socket initialization failed:', error);
        rootStore.setError('Failed to connect to server');
        throw error;
      } finally {
        this.loading = false;
      }
    },

    cleanupSocket() {
      console.log('Cleaning up socket connection');
      socketService.disconnect();
      this.isConnected = false;
      this.reconnectAttempts = 0;
      this.lastError = null;
    },

    async emit(event, data) {
      const rootStore = useRootStore();
      
      // Wait for existing connection attempt to complete
      while (this.loading) {
        await new Promise(resolve => setTimeout(resolve, 100));
      }
      
      if (!this.isConnected) {
        console.log('Socket not connected, waiting for connection...');
        // Don't try to reconnect here, just throw
        throw new Error('Socket not connected');
      }

      try {
        const response = await socketService.emit(event, data);
        return response;
      } catch (error) {
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
      if (!this.isConnected) {
        console.warn('Adding listener while socket is not connected:', event);
      }
      socketService.on(event, callback);
    },

    off(event, callback) {
      socketService.off(event, callback);
    }
  }
});
