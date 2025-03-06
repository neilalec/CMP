import { mount } from '@vue/test-utils';
import { createTestingPinia } from '@pinia/testing';
import Home from '@/views/Home.vue';
import { useQueueStore } from '@/stores/queueStore';
import { useSocketStore } from '@/stores/socketStore';
import { useAuthStore } from '@/stores/authStore';
import { SOCKET_EVENTS } from '@/constants/socketEvents';

describe('Home.vue', () => {
    let wrapper;
    let queueStore;
    let socketStore;
    let authStore;

    beforeEach(() => {
        wrapper = mount(Home, {
            global: {
                plugins: [createTestingPinia()],
                stubs: ['RouterLink']
            }
        });
        
        queueStore = useQueueStore();
        socketStore = useSocketStore();
        authStore = useAuthStore();
    });

    afterEach(() => {
        jest.clearAllMocks();
    });

    test('renders queue status correctly', () => {
        queueStore.playersInQueue = 5;
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
        const joinQueueSpy = jest.spyOn(queueStore, 'joinQueue');
        
        await wrapper.find('button').trigger('click');
        expect(joinQueueSpy).toHaveBeenCalledWith(authStore.username);
    });

    test('handles queue update events', async () => {
        const updateQueueStateSpy = jest.spyOn(queueStore, 'updateQueueState');
        
        socketStore.on(SOCKET_EVENTS.QUEUE.UPDATE, (data) => {
            queueStore.updateQueueState(data);
        });

        // Simulate server update
        socketStore.emit(SOCKET_EVENTS.QUEUE.UPDATE, {
            playersInQueue: 3,
            queue: ['user1', 'user2', 'user3']
        });

        expect(queueStore.playersInQueue).toBe(3);
        expect(updateQueueStateSpy).toHaveBeenCalledWith({
            playersInQueue: 3,
            queue: ['user1', 'user2', 'user3']
        });
    });
}); 
