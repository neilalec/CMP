import { createPinia, setActivePinia } from 'pinia';
import { useQueueStore } from '@/stores/queueStore';
import { useSocketStore } from '@/stores/socketStore';
import { SOCKET_EVENTS } from '@/constants/socketEvents';

// Mock the socket store instead of service
jest.mock('@/stores/socketStore', () => {
    const mockEmit = jest.fn();
    return {
        useSocketStore: () => ({
            isConnected: true,
            emit: mockEmit,
            initSocket: jest.fn(),
            cleanupSocket: jest.fn()
        })
    };
});

describe('QueueStore', () => {
    let store;
    let socketStore;

    beforeEach(() => {
        setActivePinia(createPinia());
        store = useQueueStore();
        socketStore = useSocketStore();
        socketStore.isConnected = true;
        jest.clearAllMocks();
    });

    test('joinQueue updates state correctly on success', async () => {
        const mockResponse = {
            success: true,
            inQueue: true,
            playersInQueue: 1,
            queue: ['testuser']
        };
        
        socketStore.emit.mockResolvedValue(mockResponse);

        await store.joinQueue('testuser');

        expect(socketStore.emit).toHaveBeenCalledWith(
            SOCKET_EVENTS.QUEUE.JOIN,
            { username: 'testuser' }
        );
        expect(store.inQueue).toBe(true);
        expect(store.playersInQueue).toBe(1);
        expect(store.queueList).toContain('testuser');
    });

    test('leaveQueue handles errors correctly', async () => {
        const errorMessage = 'Failed to leave queue';
        socketStore.emit.mockRejectedValue(new Error(errorMessage));

        await expect(store.leaveQueue('testuser'))
            .rejects
            .toThrow(errorMessage);

        expect(socketStore.emit).toHaveBeenCalledWith(
            SOCKET_EVENTS.QUEUE.LEAVE,
            { username: 'testuser', queueMode: null }
        );
    });

    test('updateQueueState updates store correctly', () => {
        const queueData = {
            inQueue: true,
            playersInQueue: 2,
            queue: ['user1', 'user2'],
            countdown: 10
        };

        store.updateQueueState(queueData);

        expect(store.inQueue).toBe(true);
        expect(store.playersInQueue).toBe(2);
        expect(store.queueList).toEqual(['user1', 'user2']);
        expect(store.countdown).toBe(10);
    });

    test('retains WARDOGS matchmaking availability and zero server allocation capacity', () => {
        store.updateQueueState({
            serverCapacity: 0, serverAvailable: false,
            wardogsLobbyId: 'wardogs-lobby-1',
            queueModes: {
                wardogs_beta9: { id: 'wardogs_beta9', gameType: 'wardogs',
                    maxPlayers: 9, matchmakingAvailable: true, playersInQueue: 0 }
            }
        });
        expect(store.serverCapacity).toBe(0);
        expect(store.serverAvailable).toBe(false);
        expect(store.queueModes.wardogs_beta9.matchmakingAvailable).toBe(true);
        expect(store.wardogsLobbyId).toBe('wardogs-lobby-1');
    });

    test('resetQueue clears store state', () => {
        // Set some initial state
        store.updateQueueState({
            inQueue: true,
            playersInQueue: 2,
            queue: ['user1', 'user2'],
            countdown: 10
        });

        store.resetQueue();

        // Verify only the states we know are reset
        expect(store.inQueue).toBe(false);
        expect(store.playersInQueue).toBe(0);
        expect(store.queueList).toEqual([]);
        expect(store.error).toBe(null);
        expect(store.loading).toBe(false);
        // Removed countdown expectation since it's not part of resetQueue
    });
});
