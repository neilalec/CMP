import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import { createRouter, createWebHistory } from 'vue-router';
import Home from '@/views/Home.vue';
import { useQueueStore } from '@/stores/queueStore';
import { useSocketStore } from '@/stores/socketStore';
import { useAuthStore } from '@/stores/authStore';
import { SOCKET_EVENTS } from '@/constants/socketEvents';
import { socketService } from '@/services/socketService';

// Mock socketService
jest.mock('@/services/socketService', () => ({
    socketService: {
        connect: jest.fn().mockResolvedValue(true),
        emit: jest.fn().mockResolvedValue({}),
        on: jest.fn(),
        off: jest.fn(),
        isConnected: jest.fn().mockReturnValue(true),
        socket: { connected: true }
    }
}));

// Create mock router with home route
const router = createRouter({
    history: createWebHistory(),
    routes: [
        {
            path: '/',
            name: 'Home',
            component: Home
        }
    ]
});

describe('Home.vue', () => {
    let wrapper;
    let queueStore;
    let socketStore;
    let authStore;

    beforeEach(() => {
        // Reset all mocks
        jest.clearAllMocks();

        wrapper = mount(Home, {
            global: {
                plugins: [
                    createTestingPinia({
                        createSpy: jest.fn,
                        initialState: {
                            queue: {
                                playersInQueue: 0,
                                inQueue: false,
                                queueList: []
                            },
                            socket: {
                                isConnected: true
                            },
                            auth: {
                                username: 'testuser'
                            }
                        },
                        stubActions: false
                    }),
                    router
                ],
                stubs: ['RouterLink']
            }
        });
        
        queueStore = useQueueStore();
        socketStore = useSocketStore();
        authStore = useAuthStore();

        // Mock socket store methods
        socketStore.emit = jest.fn().mockImplementation(async (event, data) => {
            if (event === SOCKET_EVENTS.QUEUE.JOIN) {
                return {
                    success: true,
                    inQueue: true,
                    playersInQueue: 1,
                    queue: [data.username]
                };
            }
            if (event === SOCKET_EVENTS.QUEUE.STATUS) {
                return {
                    inQueue: false,
                    playersInQueue: 0,
                    queue: []
                };
            }
            return {};
        });

        // Mock socket store on/off methods
        socketStore.on = jest.fn();
        socketStore.off = jest.fn();
    });

    afterEach(() => {
        wrapper.unmount();
    });

    test('renders queue status correctly', async () => {
        queueStore.playersInQueue = 5;
        await wrapper.vm.$nextTick();
        expect(wrapper.text()).toContain('Players in queue: 5');
    });

    test('shows join queue button when not in queue', () => {
        queueStore.inQueue = false;
        expect(wrapper.find('button').text()).toBe('Join Queue');
    });

    test('shows leave queue button when in queue', async () => {
        queueStore.inQueue = true;
        await wrapper.vm.$nextTick();
        expect(wrapper.find('button').text()).toBe('Leave Queue');
    });

    test('calls joinQueue when join button clicked', async () => {
        queueStore.inQueue = false;
        authStore.username = 'testuser';
        const joinQueueSpy = jest.spyOn(queueStore, 'joinQueue');
        
        await wrapper.find('button').trigger('click');
        expect(joinQueueSpy).toHaveBeenCalledWith('testuser');
        expect(socketStore.emit).toHaveBeenCalledWith(
            SOCKET_EVENTS.QUEUE.JOIN,
            { username: 'testuser' }
        );
    });

    test('handles queue update events', async () => {
        const queueData = {
            inQueue: true,
            playersInQueue: 3,
            queue: ['user1', 'user2', 'user3']
        };

        queueStore.updateQueueState(queueData);
        await wrapper.vm.$nextTick();

        expect(queueStore.playersInQueue).toBe(3);
        expect(queueStore.queueList).toEqual(['user1', 'user2', 'user3']);
        expect(queueStore.inQueue).toBe(true);
    });

    test('sets up socket listeners on mount', () => {
        expect(socketStore.on).toHaveBeenCalledWith(
            SOCKET_EVENTS.QUEUE.UPDATE,
            expect.any(Function)
        );
        expect(socketStore.on).toHaveBeenCalledWith(
            SOCKET_EVENTS.LOBBY.CREATED,
            expect.any(Function)
        );
    });
}); 
