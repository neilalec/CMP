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

    test('registers connection handlers and disconnects cleanly', async () => {
        const mockSocket = createMockSocket();
        
        // Override the on method to capture all event handlers
        mockSocket.on = jest.fn((event, callback) => {
            if (event === 'connect') {
                callback();
            }
        });
        
        io.mockImplementation(() => mockSocket);

        // Connect the socket
        await socketService.connect('test-token', 'testuser');

        // Get all registered events
        const registeredEvents = mockSocket.on.mock.calls.map(call => call[0]);

        expect(registeredEvents).toEqual(
            expect.arrayContaining([
                SOCKET_EVENTS.CONNECTION.CONNECT,
                SOCKET_EVENTS.CONNECTION.ERROR
            ])
        );

        socketService.disconnect();

        expect(mockSocket.removeAllListeners).toHaveBeenCalled();
        expect(mockSocket.disconnect).toHaveBeenCalled();
        expect(socketService.isConnected()).toBeFalsy();
    });
});
