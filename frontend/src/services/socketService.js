import { io } from 'socket.io-client';
import { SOCKET_URL } from '../config';

export class SocketService {
  constructor() {
    this.socket = null;
    this.baseURL = SOCKET_URL;
    this.lastConnectError = null;
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
      let settled = false;
      let timeoutId = null;

      const settleResolve = (value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeoutId);
        resolve(value);
      };

      const settleReject = (error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timeoutId);
        this.lastConnectError = error;
        reject(error);
      };

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
          this.lastConnectError = null;
          settleResolve(this.socket);
        });

        this.socket.on('connect_error', (error) => {
          console.error('Socket connection error:', error);
          settleReject(error);
        });

        this.socket.on('error', (error) => {
          console.error('Socket error:', error);
          settleReject(error);
        });

        // Add timeout
        timeoutId = setTimeout(() => {
          if (!this.socket.connected) {
            settleReject(new Error('Connection timeout'));
          }
        }, 5000);

      } catch (error) {
        console.error('Socket creation error:', error);
        settleReject(error);
      }
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.removeAllListeners();
      this.socket.disconnect();
      this.socket = null;
    }
    this.lastConnectError = null;
  }

  emit(event, data) {
    if (!this.socket) {
      throw new Error('Socket not initialized');
    }
    return new Promise((resolve) => {
      if (import.meta.env.DEV) {
        console.debug('[socket emit]', event, data);
      }
      this.socket.emit(event, data, (response) => {
        if (import.meta.env.DEV) {
          console.debug('[socket ack]', event, response);
        }
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

  isConnected() {
    return !!this.socket?.connected;
  }
}

// Create and export singleton instance
export const socketService = new SocketService(); 
