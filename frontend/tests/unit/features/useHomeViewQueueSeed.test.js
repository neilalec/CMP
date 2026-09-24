import { defineComponent } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import { useRoute, useRouter } from 'vue-router';
import { useAuthStore } from '@/stores/authStore';
import { useGroupStore } from '@/stores/groupStore';
import { useQueueStore } from '@/stores/queueStore';
import { useRootStore } from '@/stores/rootStore';
import { useSocketStore } from '@/stores/socketStore';
import { useHomeView } from '@/features/home/composables/useHomeView';

jest.mock('vue-router', () => ({ useRoute: jest.fn(), useRouter: jest.fn() }));
jest.mock('@/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('@/stores/groupStore', () => ({ useGroupStore: jest.fn() }));
jest.mock('@/stores/queueStore', () => ({ useQueueStore: jest.fn() }));
jest.mock('@/stores/rootStore', () => ({ useRootStore: jest.fn() }));
jest.mock('@/stores/socketStore', () => ({ useSocketStore: jest.fn() }));

describe('useHomeView queue seeding', () => {
  let authStore;
  let queueStore;
  let rootStore;

  beforeEach(() => {
    authStore = {
      isAdmin: true, token: 'dev-token', username: 'neil', hasSteamId: true,
      syncProfile: jest.fn().mockResolvedValue(null)
    };
    queueStore = {
      queueModes: {
        wardogs_beta9: { id: 'wardogs_beta9', gameType: 'wardogs', maxPlayers: 9, playersInQueue: 1 },
        skirmish: { id: 'skirmish', gameType: 'squad', maxPlayers: 40, playersInQueue: 12 }
      },
      seedQueue: jest.fn().mockResolvedValue({ success: true }),
      syncWithServer: jest.fn().mockResolvedValue({ success: true })
    };
    rootStore = { setError: jest.fn() };

    useRoute.mockReturnValue({ path: '/play' });
    useRouter.mockReturnValue({ push: jest.fn() });
    useAuthStore.mockReturnValue(authStore);
    useGroupStore.mockReturnValue({ inGroup: false, leader: null });
    useQueueStore.mockReturnValue(queueStore);
    useRootStore.mockReturnValue(rootStore);
    useSocketStore.mockReturnValue({
      isConnected: true, emit: jest.fn().mockResolvedValue({}), on: jest.fn(), off: jest.fn()
    });
    global.fetch = jest.fn();
  });

  const mountHomeView = async () => {
    const wrapper = mount(defineComponent({
      setup: () => useHomeView(),
      template: '<div />'
    }));
    await flushPromises();
    return wrapper;
  };

  test('fills WARDOGS through the local dev endpoint and refreshes queue state', async () => {
    global.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ success: true, seeded: ['__dev_wardogs_01__'] })
    });
    const wrapper = await mountHomeView();

    await wrapper.vm.seedQueue('wardogs_beta9');

    expect(global.fetch).toHaveBeenCalledWith(
      expect.stringMatching(/\/api\/admin\/dev\/wardogs\/fill$/),
      { method: 'POST', headers: { Authorization: 'Bearer dev-token' } }
    );
    expect(queueStore.seedQueue).not.toHaveBeenCalled();
    expect(queueStore.syncWithServer).toHaveBeenNthCalledWith(2, 'neil');
    expect(rootStore.setError).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  test('surfaces WARDOGS dev endpoint errors to the user', async () => {
    global.fetch.mockResolvedValue({
      ok: false,
      json: async () => ({ success: false, message: 'Join the WARDOGS beta queue before filling it' })
    });
    const wrapper = await mountHomeView();

    await wrapper.vm.seedQueue('wardogs_beta9');

    expect(rootStore.setError).toHaveBeenCalledWith('Join the WARDOGS beta queue before filling it');
    expect(queueStore.syncWithServer).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  test('keeps Squad seeding on the existing socket path', async () => {
    const wrapper = await mountHomeView();

    await wrapper.vm.seedQueue('skirmish');

    expect(queueStore.seedQueue).toHaveBeenCalledWith(28, 'skirmish');
    expect(global.fetch).not.toHaveBeenCalled();
    wrapper.unmount();
  });
});
