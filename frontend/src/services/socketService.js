import { io } from 'socket.io-client';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { SOCKET_URL } from '../config';

export class SocketService {
  constructor() {
    this.socket = null;
    this.baseURL = SOCKET_URL;
    this.connected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.connectionHandlers = new Set(); // Track handlers
  }

  async connect(token = null, username = null) {
    console.log('SocketService connect called with:', { token, username });

    if (this.socket?.connected) {
      console.log('Socket already connected, returning existing connection');
      return this.socket;
    }

    // Cleanup any existing socket
    if (this.socket) {
      console.log('Cleaning up existing socket');
      this.disconnect();
    }

    // Prepare auth object
    const auth = username ? { username, ...(token && { token }) } : {};
    console.log('Connecting with auth:', auth);

    return new Promise((resolve, reject) => {
      try {
        this.socket = io(this.baseURL, {
          auth,
          transports: ['websocket'],
          reconnection: true,
          reconnectionAttempts: 3,
          reconnectionDelay: 1000,
          timeout: 5000
        });

        this.socket.on('connect', () => {
          console.log('Socket connected successfully');
          resolve(this.socket);
        });

        this.socket.on('connect_error', (error) => {
          console.error('Socket connection error:', error);
          reject(error);
        });

        this.socket.on('error', (error) => {
          console.error('Socket error:', error);
          reject(error);
        });

        // Add timeout
        setTimeout(() => {
          if (!this.socket.connected) {
            reject(new Error('Connection timeout'));
          }
        }, 5000);

      } catch (error) {
        console.error('Socket creation error:', error);
        reject(error);
      }
    });
  }

  cleanup() {
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }
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
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }
  }

  emit(event, data) {
    if (!this.socket) {
      throw new Error('Socket not initialized');
    }
    return new Promise((resolve, reject) => {
      this.socket.emit(event, data, (response) => {
        resolve(response);
      });
    });
  }

  on(event, callback) {
    if (!this.socket) {
      throw new Error('Socket not initialized');
    }
    this.socket.on(event, callback);
  }

  off(event, callback) {
    if (!this.socket) {
      return;
    }
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
