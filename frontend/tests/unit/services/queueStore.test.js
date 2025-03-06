import { createPinia, setActivePinia } from 'pinia';
import { useQueueStore } from '@/stores/queueStore';
import { socketService } from '@/services/socketService';

jest.mock('@/services/socketService');

describe('QueueStore', () => {
    beforeEach(() => {
        jest.clearAllMocks();
        setActivePinia(createPinia());
    });

    afterEach(() => {
        jest.resetModules();
    });

    test('joinQueue updates state correctly on success', async () => {
        const store = useQueueStore();
        socketService.emit.mockResolvedValue({
            success: true,
            inQueue: true,
            playersInQueue: 1
        });

        await store.joinQueue('testuser');

        expect(store.inQueue).toBe(true);
        expect(store.playersInQueue).toBe(1);
    });

    test('leaveQueue handles errors correctly', async () => {
        const store = useQueueStore();
        socketService.emit.mockRejectedValue(new Error('Network error'));

        await expect(store.leaveQueue('testuser')).rejects.toThrow('Failed to leave queue');
    });
});