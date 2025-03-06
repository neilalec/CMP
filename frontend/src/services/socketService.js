import { io } from 'socket.io-client';
import { getEnvConfig } from '../config/env';
import { SOCKET_EVENTS } from '../constants/socketEvents';

class SocketService {
  constructor() {
    this.socket = null;
    this.connected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.connectionHandlers = new Set(); // Track handlers
  }

  async connect(token, username) {
    const config = getEnvConfig();
    const socketUrl = config.VITE_SOCKET_URL;

    return new Promise((resolve, reject) => {
      if (this.socket?.connected) {
        console.log('Already connected, reusing connection');
        resolve();
        return;
      }

      if (this.socket) {
        console.log('Cleaning up existing socket...');
        this.disconnect();
      }

      try {
        console.log('Creating new socket connection...', { token, username });
        
        this.socket = io(socketUrl, {
          auth: { token, username },
          transports: ['websocket'],
          reconnection: true,
          reconnectionAttempts: this.maxReconnectAttempts,
          reconnectionDelay: 1000,
          timeout: 5000,
          autoConnect: false // Prevent auto-connection before auth check
        });

        // Add auth error handler
        this.socket.on('auth_error', (error) => {
          console.error('Authentication error:', error);
          localStorage.removeItem('token');
          localStorage.removeItem('username');
          window.location.href = '/auth';
        });

        this.socket.connect();
        this.setupConnectionHandlers(resolve, reject);
      } catch (error) {
        console.error('Socket connection error:', error);
        reject(new Error('Failed to initialize socket connection'));
      }
    });
  }

  setupConnectionHandlers(resolve, reject) {
    if (!this.socket) return;

    const connectHandler = () => {
      this.connected = true;
      this.reconnectAttempts = 0;
      this.socket.emit(SOCKET_EVENTS.QUEUE.STATUS);
      resolve();
    };
    this.socket.on(SOCKET_EVENTS.CONNECTION.CONNECT, connectHandler);
    this.connectionHandlers.add({ event: SOCKET_EVENTS.CONNECTION.CONNECT, handler: connectHandler });

    this.socket.on(SOCKET_EVENTS.CONNECTION.ERROR, (error) => {
      this.connected = false;
      reject(error);
    });

    const disconnectHandler = (reason) => {
      this.connected = false;
      if (reason === 'io server disconnect' && this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        setTimeout(() => {
          try {
            this.connect().catch(error => {
              this.emit('error', { message: 'Reconnection failed' });
            });
          } catch (error) {
            this.emit('error', { message: 'Reconnection failed' });
          }
        }, 1000 * this.reconnectAttempts);
      }
    };
    this.socket.on(SOCKET_EVENTS.CONNECTION.DISCONNECT, disconnectHandler);

    this.socket.on(SOCKET_EVENTS.CONNECTION.RECONNECT, (attemptNumber) => {
      this.reconnectAttempts = attemptNumber;
    });

    // Clean up on disconnect
    const cleanup = () => {
      for (const {event, handler} of this.connectionHandlers) {
        this.socket?.off(event, handler);
      }
      this.connectionHandlers.clear();
    };
    this.socket.on(SOCKET_EVENTS.CONNECTION.DISCONNECT, cleanup);
  }

  disconnect() {
    if (this.socket) {
      try {
        // First remove all listeners
        this.socket.removeAllListeners();
        // Then emit disconnect
        this.socket.emit('client_disconnect');
        // Finally disconnect
        this.socket.disconnect();
      } catch (error) {
        console.error('Error during socket disconnect:', error);
      } finally {
        this.socket = null;
        this.connected = false;
        this.connectionHandlers.clear();
      }
    }
  }

  emit(event, data) {
    return new Promise((resolve, reject) => {
      // Connection check
      if (!this.socket || !this.connected) {
        reject(new Error('Socket not connected'));
        return;
      }

      // Use Socket.IO's acknowledgment callback
      this.socket.emit(event, data, (response) => {
        if (response && response.success === false) {
          reject(new Error(response.message));
        } else {
          resolve(response);
        }
      });

      // Add timeout
      setTimeout(() => {
        reject(new Error('Socket request timeout'));
      }, 5000);
    });
  }

  on(event, callback) {
    if (!this.socket) {
      throw new Error('Socket not initialized');
    }
    this.socket.on(event, callback);
  }

  off(event, callback) {
    if (!this.socket) return;
    this.socket.off(event, callback);
  }

  // Specific event handlers for different features
  onQueueUpdate(callback) {
    this.on(SOCKET_EVENTS.QUEUE.UPDATE, callback);
  }

  onLobbyUpdate(callback) {
    this.on(SOCKET_EVENTS.LOBBY.UPDATE, callback);
  }

  onMatchFound(callback) {
    this.on(SOCKET_EVENTS.MATCH.FOUND, callback);
  }

  isConnected() {
    return this.connected && this.socket?.connected;
  }
}

// Create and export singleton instance
export const socketService = new SocketService(); 