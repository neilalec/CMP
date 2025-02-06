// src/composables/useSocket.js
import { ref } from 'vue';
import { io } from 'socket.io-client';
import { useQueueStore } from '../stores/queueStore';

// Singleton state - these variables are shared across all instances of useSocket()
let socketInstance = null; // Single socket instance
let isInitialized = false;
const playersInQueue = ref(0);
const inQueue = ref(false);
const loading = ref(false);
const lobbyId = ref(null);
const isLoggedIn = ref(false);
const isConnected = ref(false);





// Create socket instance with all the configuration
function createSocket() {
  console.log('Creating new socket instance');
  return io('http://localhost:5000', {
      transports: ['polling', 'websocket'],
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      withCredentials: true,
      autoConnect: true
  });
}






// Setup socket event listeners
function setupSocketListeners(socket, queueStore) {
  if (isInitialized) {
    console.log('Socket listeners already initialized');
    return;
  }

  console.log('Initializing socket listeners');
  isInitialized = true;

  socket.on('connect', () => {
      console.log('Socket connected successfully:', socket.id);
      isLoggedIn.value = true;
      isConnected.value = true;
      
      const storedUsername = localStorage.getItem('username');
      const storedToken = localStorage.getItem('token');
      
      if (storedUsername && storedToken) {
          socket.emit('authenticate', { 
              username: storedUsername, 
              token: storedToken 
          });
      }
  });

  socket.off('queue_status');
  socket.on('queue_status', (data) => {
      console.log('Socket received queue status:', data);
      queueStore.updateQueueState(data);
  });

  socket.on('queue_update', (data) => {
      console.log('Socket received queue update:', data);
      queueStore.updateQueueState(data);
  });


  socket.on('lobby_update', (data) => {
      console.log('Lobby update received:', data);
      lobbyId.value = data.lobby_id;
  });

  socket.on('disconnect', (reason) => {
    console.log('Socket disconnected:', reason);
    isConnected.value = false;
    queueStore.resetQueue();
  });

  // Debug listeners
  socket.io.on("debug", (debug) => console.log("Socket.IO debug:", debug));
  socket.io.on("reconnect_attempt", (attempt) => console.log("Reconnection attempt:", attempt));
  socket.io.on("transport", (transport) => console.log("Current transport:", transport.name));
  socket.io.on("error", (error) => console.error("Socket.IO manager error:", error));

  socket.on('connect_error', (error) => {
      console.error('Connection error:', {
          message: error.message,
          description: error.description,
          type: error.type,
          transport: socket.io.engine.transport.name
      });
  });
}








export function useSocket() {
  const queueStore = useQueueStore();

    // Initialize socket if it doesn't exist and we have a token
    if (!socketInstance) {
      socketInstance = createSocket();
      setupSocketListeners(socketInstance, queueStore);
    }

    const findMatch = (username) => {
        if (!socketInstance) return;
        
        console.log('Attempting to join queue:', username);
        loading.value = true;
        
        // Remove any existing listeners
        socketInstance.off('queue_joined');
        
        // Listen for immediate join confirmation
        socketInstance.once('queue_joined', (data) => {
            console.log('Queue joined response:', data);
            if (data.success) {
                queueStore.updateQueueState({
                  inQueue: true,
                  playersInQueue: data.playersInQueue,
                  queue: data.queue
                });
            } else {
                console.error('Failed to join queue:', data.message);
                queueStore.updateQueueState({
                  inQueue: data.inQueue,
                  playersInQueue: data.playersInQueue,
                  queue:data.queue
            });
            }
            loading.value = false;
          });

        
        socketInstance.emit('join-queue', { username });
        
        setTimeout(() => {
            if (loading.value) {
                loading.value = false;
                console.error('Queue join timeout');
            }
        }, 5000);
  };

    const leaveQueue = (username) => {
        if (!socketInstance) return;
        socketInstance.emit('leave-queue', { username });
    };


    const cleanupSocket = () => {
      if (socketInstance) {
        console.log('Cleaning up socket', socketInstance.id);

        //log all listeners
        console.log('Current listeners:', socketInstance.listeners());


        socketInstance.off('connect');
        socketInstance.off('queue_update');
        socketInstance.off('queue_status');
        socketInstance.off('lobby_update');
        socketInstance.off('disconnect');
        socketInstance.disconnect();
        socketInstance = null;
        isInitialized = false;
        isConnected.value = false;

        queueStore.resetQueue();

        // Reset other state
        loading.value = false;
        lobbyId.value = null;

        console.log('Socket cleaned complete');
      }
    };


    return {
      socket: ref(socketInstance),
      playersInQueue: queueStore.playersInQueue,
      inQueue: queueStore.inQueue,
      queueList: queueStore.queueList,
      loading,
      lobbyId,
      isConnected,
      findMatch,
      leaveQueue,
      cleanupSocket,

  };
}
    
 

