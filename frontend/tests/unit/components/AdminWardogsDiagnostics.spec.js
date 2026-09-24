import { mount, flushPromises } from '@vue/test-utils';
import Admin from '@/views/Admin.vue';
import { buildRoutes } from '@/router';
import { useAuthStore } from '@/stores/authStore';
import { useRootStore } from '@/stores/rootStore';
import { useSocketStore } from '@/stores/socketStore';

jest.mock('@/stores/authStore', () => ({ useAuthStore: jest.fn() }));
jest.mock('@/stores/rootStore', () => ({ useRootStore: jest.fn() }));
jest.mock('@/stores/socketStore', () => ({ useSocketStore: jest.fn() }));

const response = (payload, ok = true) => ({ ok, text: async () => JSON.stringify(payload),
  headers: { get: () => 'application/json' } });
const mountAdmin = () => mount(Admin, { global: {
  stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }
} });

describe('WARDOGS Admin console', () => {
  let diagnostics;
  let servers;
  let dev;
  let auth;
  beforeEach(() => {
    auth = { token: 'test-token', username: 'neil', isAdmin: true,
      canToggleAdmin: false, syncProfile: jest.fn().mockResolvedValue(null) };
    useAuthStore.mockReturnValue(auth);
    useRootStore.mockReturnValue({ setError: jest.fn() });
    useSocketStore.mockReturnValue({ emit: jest.fn() });
    diagnostics = { generatedAt: 1790260000, database: { ok: true }, queueSize: 1,
      queueModes: { wardogs_beta9: { id: 'wardogs_beta9', gameType: 'wardogs',
        label: 'WARDOGS Beta · 3 factions', size: 1, requiredPlayers: 9,
        factionCount: 3, activePerFaction: 3, reservePerFaction: 0 } },
      serverAvailabilityByGame: { wardogs: { available: false, reason: 'no_servers', capacity: 0 } },
      bridge: { enabled: false }, automation: { mode: 'on', rconWritesEnabled: true },
      eos: { configured: false }, activeLobbies: [], historyCounts: {}, recentEvents: [] };
    servers = [{ id: 7, game_type: 'wardogs', display_name: 'Test WARDOGS',
      status: 'healthy', enabled: true, approved_by: 'admin', current_lobby_id: 'wd-7',
      last_health_status: 'healthy', last_health_check_at: '2026-09-24T12:00:00+00:00',
      metadata: { bearer_token: 'private-secret' } }];
    dev = { queue: ['neil'], pendingMatch: false, lobbyId: 'wd-7' };
    global.fetch = jest.fn(async (url) => {
      if (url.endsWith('/admin/diagnostics')) return response({ success: true, diagnostics });
      if (url.endsWith('/admin/servers')) return response({ success: true, servers, available: [] });
      if (url.endsWith('/admin/dev/wardogs')) return response({ success: true, ...dev });
      return response({ success: true });
    });
  });

  test('shows diagnostics and server state without raw credentials or referee controls', async () => {
    const wrapper = mountAdmin();
    await flushPromises();
    const page = wrapper.text();
    expect(page).toContain('Backend databaseHealthy');
    expect(page).toContain('WARDOGS servers0 available · 1 registered');
    expect(page).toContain('WARDOGS Beta · 3 factions');
    expect(page).toContain('9 total players · 3 factions · 3 active/faction · 0 reserve/faction');
    expect(page).toContain('Test WARDOGS');
    expect(page).toContain('Approved');
    expect(page).toContain('Last probe');
    expect(wrapper.find('a[href="/wardogs/lobby/wd-7"]').exists()).toBe(true);
    expect(page).not.toContain('private-secret');
    expect(page).not.toContain('Confirm result');
    expect(page).not.toContain('Correct result');
    expect(page).not.toContain('Bridge');
    wrapper.unmount();
  });

  test('keeps local test controls separate from destructive cleanup', async () => {
    const wrapper = mountAdmin();
    await flushPromises();
    const devSection = wrapper.get('[aria-label="WARDOGS developer tools"]');
    const danger = wrapper.get('[aria-label="Reset and cleanup"]');
    expect(devSection.text()).toContain('Fill test queue');
    expect(devSection.text()).toContain('Simulate connected');
    expect(devSection.text()).toContain('Real observations only');
    expect(devSection.text()).toContain('Retry allocation');
    expect(danger.text()).toContain('Reset test queue / overlay');
    expect(danger.text()).toContain('Delete test lobby');
    expect(devSection.text()).not.toContain('Delete test lobby');
    wrapper.unmount();
  });

  test('hides dev tools in production and all admin operations from a regular user', async () => {
    const oldEnvironment = process.env.NODE_ENV;
    process.env.NODE_ENV = 'production';
    try {
      const wrapper = mountAdmin();
      await flushPromises();
      expect(wrapper.find('[aria-label="WARDOGS developer tools"]').exists()).toBe(false);
      expect(global.fetch.mock.calls.some(([url]) => url.endsWith('/admin/dev/wardogs'))).toBe(false);
      wrapper.unmount();
    } finally {
      process.env.NODE_ENV = oldEnvironment;
    }
    auth.isAdmin = false;
    global.fetch.mockClear();
    const wrapper = mountAdmin();
    await flushPromises();
    expect(wrapper.find('[aria-label="System and integration"]').exists()).toBe(false);
    expect(wrapper.find('[aria-label="WARDOGS servers"]').exists()).toBe(false);
    expect(global.fetch).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  test('keeps diagnostics when server loading fails and offers independent retry', async () => {
    global.fetch = jest.fn(async (url) => {
      if (url.endsWith('/admin/diagnostics')) return response({ success: true, diagnostics });
      if (url.endsWith('/admin/servers')) return response({ success: false, message: 'Servers unavailable' }, false);
      return response({ success: true, ...dev });
    });
    const wrapper = mountAdmin();
    await flushPromises();
    expect(wrapper.text()).toContain('Backend databaseHealthy');
    expect(wrapper.text()).toContain('Servers unavailable');
    expect(wrapper.findAll('button').some((button) => button.text() === 'Retry servers')).toBe(true);
    wrapper.unmount();
  });

  test('keeps server state visible when diagnostics fail', async () => {
    global.fetch = jest.fn(async (url) => {
      if (url.endsWith('/admin/diagnostics')) return response({ success: false, message: 'Diagnostics unavailable' }, false);
      if (url.endsWith('/admin/servers')) return response({ success: true, servers, available: [] });
      return response({ success: true, ...dev });
    });
    const wrapper = mountAdmin();
    await flushPromises();
    expect(wrapper.text()).toContain('Diagnostics unavailable');
    expect(wrapper.text()).toContain('Test WARDOGS');
    expect(wrapper.findAll('button').some((button) => button.text() === 'Retry diagnostics')).toBe(true);
    wrapper.unmount();
  });

  test('keeps diagnostics and servers visible when dev-tool state is unavailable', async () => {
    let devFails = false;
    global.fetch = jest.fn(async (url) => {
      if (url.endsWith('/admin/diagnostics')) return response({ success: true, diagnostics });
      if (url.endsWith('/admin/servers')) return response({ success: true, servers, available: [] });
      if (url.endsWith('/admin/dev/wardogs')) {
        return devFails ? response({ success: false, message: 'Test tools unavailable' }, false)
          : response({ success: true, ...dev });
      }
      return response({ success: true });
    });
    const wrapper = mountAdmin();
    await flushPromises();
    expect(wrapper.text()).toContain('Backend databaseHealthy');
    expect(wrapper.text()).toContain('Test WARDOGS');
    devFails = true;
    await wrapper.findAll('button').find((button) => button.text() === 'Simulate connected').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('Test tools unavailable');
    expect(wrapper.text()).toContain('Showing the last successful test state');
    expect(wrapper.text()).toContain('wd-7');
    expect(wrapper.findAll('button').find((button) => button.text() === 'Fill test queue').attributes('disabled')).toBeDefined();
    expect(wrapper.findAll('button').some((button) => button.text() === 'Retry test tools')).toBe(true);
    wrapper.unmount();
  });

  test('shows compact loading states before admin reads finish', async () => {
    let finishDiagnostics;
    let finishServers;
    global.fetch = jest.fn((url) => new Promise((resolve) => {
      if (url.endsWith('/admin/diagnostics')) finishDiagnostics = resolve;
      else if (url.endsWith('/admin/servers')) finishServers = resolve;
      else resolve(response({ success: true, ...dev }));
    }));
    const wrapper = mountAdmin();
    await flushPromises();
    expect(wrapper.text()).toContain('Loading diagnostics');
    expect(wrapper.text()).toContain('Loading servers');
    finishDiagnostics(response({ success: true, diagnostics }));
    await flushPromises();
    expect(wrapper.text()).toContain('Backend databaseHealthy');
    finishServers(response({ success: true, servers, available: [] }));
    await flushPromises();
    expect(wrapper.text()).toContain('Test WARDOGS');
    wrapper.unmount();
  });

  test('keeps the existing confirmation before deleting a test lobby', async () => {
    const confirm = jest.spyOn(window, 'confirm').mockReturnValue(false);
    const wrapper = mountAdmin();
    await flushPromises();
    const deleteButton = wrapper.get('[aria-label="Reset and cleanup"]').findAll('button')
      .find((button) => button.text() === 'Delete test lobby');
    await deleteButton.trigger('click');
    expect(confirm).toHaveBeenCalled();
    expect(global.fetch.mock.calls.some(([url]) => url.includes('/admin/wardogs/lobbies/wd-7'))).toBe(false);
    confirm.mockRestore();
    wrapper.unmount();
  });

  test('keeps WARDOGS and Squad Admin routes separate and protected', () => {
    const wardogs = buildRoutes('wardogs').find((route) => route.name === 'admin');
    const squad = buildRoutes('squad').find((route) => route.name === 'admin');
    expect(wardogs.meta).toMatchObject({ requiresAuth: true, requiresAdmin: true });
    expect(squad.meta).toMatchObject({ requiresAuth: true, requiresAdmin: true });
    expect(wardogs.component).not.toBe(squad.component);
  });
});
