import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import { createRouter, createWebHistory } from 'vue-router';
import Home from '@/views/Home.vue';
import { useQueueStore } from '@/stores/queueStore';
import { useSocketStore } from '@/stores/socketStore';
import { useAuthStore } from '@/stores/authStore';
import { SOCKET_EVENTS } from '@/constants/socketEvents';

describe('Queue Integration', () => {
    let wrapper;
    let router;
    let queueStore;
    let socketStore;
    let authStore;

    beforeEach(() => {
        router = createRouter({
            history: createWebHistory(),
            routes: [{ path: '/', component: Home }]
        });

        wrapper = mount(Home, {
            global: {
                plugins: [
                    createTestingPinia({
                        initialState: {
                            auth: { username: 'testuser', isLoggedIn: true }
                        }
                    }),
                    router
                ]
            }
        });

        queueStore = useQueueStore();
        socketStore = useSocketStore();
        authStore = useAuthStore();
    });

    test('complete queue workflow', async () => {
        // Initialize socket connection
        await socketStore.initSocket('test-token', 'testuser');
        expect(socketStore.isConnected).toBe(true);

        // Test joining queue
        await queueStore.joinQueue('testuser');
        expect(queueStore.inQueue).toBe(true);
        expect(queueStore.playersInQueue).toBe(1);

        // Simulate server queue update
        socketStore.socket.emit(SOCKET_EVENTS.QUEUE.UPDATE, {
            playersInQueue: 2,
            queue: ['testuser', 'otheruser']
        });
        
        await wrapper.vm.$nextTick();
        expect(queueStore.playersInQueue).toBe(2);

        // Test leaving queue
        await queueStore.leaveQueue('testuser');
        expect(queueStore.inQueue).toBe(false);
    });

    test('handles lobby creation', async () => {
        await socketStore.initSocket('test-token', 'testuser');
        await queueStore.joinQueue('testuser');

        // Simulate lobby creation from server
        socketStore.socket.emit(SOCKET_EVENTS.LOBBY.CREATED, {
            lobby_id: 'test-lobby',
            players: ['testuser', 'otheruser'],
            teams: {
                team1: ['testuser'],
                team2: ['otheruser']
            }
        });

        await wrapper.vm.$nextTick();
        expect(router.currentRoute.value.path).toBe('/lobby/test-lobby');
    });

    test('handles connection errors', async () => {
        const connectSpy = jest.spyOn(socketStore, 'initSocket');
        connectSpy.mockRejectedValue(new Error('Connection failed'));

        try {
            await socketStore.initSocket('test-token', 'testuser');
        } catch (error) {
            expect(error.message).toBe('Connection failed');
        }
    });
}); 