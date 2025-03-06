import { socketService } from '@/services/socketService';
import { io } from 'socket.io-client';

// Use beforeAll for one-time setup
beforeAll(() => {
    jest.mock('socket.io-client');
});

describe('SocketService', () => {
    beforeEach(() => {
        jest.clearAllMocks(); // More comprehensive than io.mockClear()
    });

    test('connect establishes socket connection with correct config', async () => {
        const mockSocket = {
            on: jest.fn(),
            connect: jest.fn(),
            emit: jest.fn()
        };
        io.mockReturnValue(mockSocket);

        await socketService.connect('test-token', 'testuser');

        expect(io).toHaveBeenCalledWith(expect.any(String), {
            auth: { token: 'test-token', username: 'testuser' },
            transports: ['websocket'],
            reconnection: true,
            timeout: 5000
        });
    });

    test('emit returns promise that resolves on response', async () => {
        const mockSocket = {
            on: jest.fn(),
            once: jest.fn((event, cb) => cb({ success: true })),
            emit: jest.fn(),
            connect: jest.fn()
        };
        io.mockReturnValue(mockSocket);

        await socketService.connect('test-token', 'testuser');
        const response = await socketService.emit('test-event', { data: 'test' });

        expect(response).toEqual({ success: true });
        expect(mockSocket.emit).toHaveBeenCalledWith('test-event', { data: 'test' });
    });
});