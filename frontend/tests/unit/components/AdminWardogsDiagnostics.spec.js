import { mount, flushPromises } from '@vue/test-utils'
import Admin from '@/views/Admin.vue'
import { useAuthStore } from '@/stores/authStore'
import { useRootStore } from '@/stores/rootStore'
import { useSocketStore } from '@/stores/socketStore'

jest.mock('@/stores/authStore', () => ({ useAuthStore: jest.fn() }))
jest.mock('@/stores/rootStore', () => ({ useRootStore: jest.fn() }))
jest.mock('@/stores/socketStore', () => ({ useSocketStore: jest.fn() }))

describe('Admin WARDOGS diagnostics', () => {
  beforeEach(() => {
    useAuthStore.mockReturnValue({
      token: 'test-token',
      username: 'neil',
      isAdmin: true,
      canToggleAdmin: false,
      syncProfile: jest.fn().mockResolvedValue(null)
    })
    useRootStore.mockReturnValue({ setError: jest.fn() })
    useSocketStore.mockReturnValue({ emit: jest.fn() })
    global.fetch = jest.fn(async (url) => {
      const payload = url.endsWith('/admin/diagnostics')
        ? {
            success: true,
            diagnostics: {
              queueSize: 1,
              queueModes: {
                wardogs_beta9: {
                  id: 'wardogs_beta9',
                  gameType: 'wardogs',
                  label: 'WARDOGS Beta · 3 factions',
                  size: 1,
                  requiredPlayers: 9,
                  maxPlayers: 9,
                  factionCount: 3,
                  activePerFaction: 3,
                  reservePerFaction: 0,
                  teamSize: null
                }
              },
              bridge: { enabled: false, ok: null, url: null },
              automation: { mode: 'on' },
              eos: { configured: false },
              activeLobbies: [],
              historyCounts: {},
              recentEvents: []
            }
          }
        : url.endsWith('/admin/servers')
          ? { success: true, servers: [], available: [] }
          : { success: true }
      return {
        ok: true,
        text: async () => JSON.stringify(payload),
        headers: { get: () => 'application/json' }
      }
    })
  })

  test('renders game-aware WARDOGS capacity without a teamSize', async () => {
    const wrapper = mount(Admin, {
      global: {
        stubs: { RouterLink: { template: '<a><slot /></a>' } }
      }
    })
    await flushPromises()

    expect(wrapper.text()).toContain('WARDOGS Beta · 3 factions')
    expect(wrapper.text()).toContain('9 total players · 3 factions · 3 active/faction · 0 reserve/faction')
    expect(wrapper.text()).not.toContain('undefinedvundefined')
    expect(wrapper.text()).not.toContain('Bridge')
    wrapper.unmount()
  })
})
