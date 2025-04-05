jest.mock('socket.io-client');

import { socketService } from '@/services/socketService';
import { io } from 'socket.io-client';
import { SOCKET_EVENTS } from '@/constants/socketEvents';

describe('SocketService', () => {
    beforeEach(() => {
        jest.clearAllMocks();
    });

    // Create a consistent mock socket factory
    const createMockSocket = () => ({
        on: jest.fn((event, callback) => {
            if (event === 'connect') {
                callback();
            }
        }),
        connected: false,
        emit: jest.fn(),
        removeAllListeners: jest.fn(),
        disconnect: jest.fn(),
        off: jest.fn()
    });

    test('connect establishes socket connection with correct config', async () => {
        const mockSocket = createMockSocket();
        io.mockImplementation(() => mockSocket);

        await socketService.connect('test-token', 'testuser');

        expect(io).toHaveBeenCalledWith('http://localhost:5000', {
            auth: { token: 'test-token', username: 'testuser' },
            transports: ['websocket'],
            reconnection: true,
            reconnectionAttempts: 3,
            reconnectionDelay: 1000,
            timeout: 5000
        });
    });

    test('emit returns promise that resolves on response', async () => {
        const mockSocket = createMockSocket();
        // Override emit for this specific test
        mockSocket.emit = jest.fn((event, data, callback) => callback({ success: true }));
        io.mockImplementation(() => mockSocket);

        await socketService.connect('test-token', 'testuser');
        const response = await socketService.emit('test-event', { data: 'test' });

        expect(response).toEqual({ success: true });
        expect(mockSocket.emit).toHaveBeenCalledWith('test-event', { data: 'test' }, expect.any(Function));
    });

    test('disconnect cleans up socket connection', async () => {
        const mockSocket = createMockSocket();
        io.mockImplementation(() => mockSocket);
        
        await socketService.connect('test-token', 'testuser');
        socketService.disconnect();

        expect(mockSocket.removeAllListeners).toHaveBeenCalled();
        expect(mockSocket.disconnect).toHaveBeenCalled();
    });

    test('handles disconnect event from server', async () => {
        const mockSocket = createMockSocket();
        const registeredHandlers = new Map();
        
        // Override the on method to capture all event handlers
        mockSocket.on = jest.fn((event, callback) => {
            registeredHandlers.set(event, callback);
            if (event === 'connect') {
                callback();
            }
        });
        
        io.mockImplementation(() => mockSocket);

        // Connect the socket
        await socketService.connect('test-token', 'testuser');
        
        // Call setupConnectionHandlers explicitly
        socketService.setupConnectionHandlers(
            () => {}, // resolve
            () => {}  // reject
        );

        // Get all registered events
        const registeredEvents = mockSocket.on.mock.calls.map(call => call[0]);
        console.log('Registered events:', registeredEvents);

        // Verify disconnect event was registered using the correct event constant
        expect(mockSocket.on).toHaveBeenCalledWith(
            SOCKET_EVENTS.CONNECTION.DISCONNECT, 
            expect.any(Function)
        );

        // Get the disconnect handler and simulate disconnect
        const disconnectHandler = registeredHandlers.get(SOCKET_EVENTS.CONNECTION.DISCONNECT);
        if (disconnectHandler) {
            disconnectHandler('io server disconnect');
            expect(socketService.isConnected()).toBeFalsy();
        } else {
            fail('Disconnect handler was not registered');
        }
    });
});