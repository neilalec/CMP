import { defineComponent, h, reactive } from 'vue'
import { flushPromises, mount } from '@vue/test-utils'
import { useAppSession } from '@/features/app/composables/useAppSession'
import { SOCKET_EVENTS } from '@/constants/socketEvents'

const mountSessionWithProfile = async (currentMatch, activeLobby = null) => {
  localStorage.clear()
  const authStore = reactive({
    isLoggedIn: true,
    username: 'alpha',
    token: 'token',
    restoreAuth: () => true,
    syncProfile: jest.fn().mockResolvedValue({ current_match: currentMatch, active_lobby: activeLobby })
  })
  const queueStore = {
    matchAccept: { active: false, cancelled: false, players: [] },
    syncWithServer: jest.fn().mockResolvedValue(undefined),
    updateQueueState: jest.fn(),
    setMatchAcceptCancelled: jest.fn(),
    resetQueue: jest.fn()
  }
  const socketStore = {
    isConnected: false,
    initSocket: jest.fn().mockResolvedValue(true),
    cleanupSocket: jest.fn().mockResolvedValue(true),
    on: jest.fn(),
    off: jest.fn()
  }
  const lobbyStore = { lobbyId: null, leaveLobby: jest.fn(), reset: jest.fn() }
  const groupStore = { syncStatus: jest.fn().mockResolvedValue(undefined), handleUpdate: jest.fn(), resetGroup: jest.fn() }
  const rootStore = { clearError: jest.fn(), setError: jest.fn(), setLoading: jest.fn() }
  const router = { push: jest.fn(), replace: jest.fn() }
  const route = reactive({ path: '/play', params: {}, meta: {} })
  const Host = defineComponent({
    setup() {
      useAppSession({ router, route, authStore, socketStore, rootStore,
        lobbyStore, queueStore, groupStore })
      return () => h('div')
    }
  })
  const wrapper = mount(Host)
  await flushPromises()
  return { wrapper, router, lobbyStore }
}

describe('app session match acceptance transition', () => {
  test('restores profile matches through game-aware routes for both products', async () => {
    const wardogs = await mountSessionWithProfile({ gameType: 'wardogs', lobbyId: 'wd-recovered' })
    expect(wardogs.router.push).toHaveBeenCalledWith('/wardogs/lobby/wd-recovered')
    expect(wardogs.lobbyStore.leaveLobby).toHaveBeenCalled()
    wardogs.wrapper.unmount()

    const squad = await mountSessionWithProfile({ gameType: 'squad', lobbyId: 'squad-recovered' }, 'squad-recovered')
    expect(squad.router.push).toHaveBeenCalledWith('/lobby/squad-recovered')
    squad.wrapper.unmount()

    const none = await mountSessionWithProfile(null)
    expect(none.router.push).not.toHaveBeenCalled()
    none.wrapper.unmount()

    const unknown = await mountSessionWithProfile({ gameType: 'unknown', lobbyId: 'mystery' })
    expect(unknown.router.push).not.toHaveBeenCalled()
    unknown.wrapper.unmount()
  })

  test('waits for the authoritative WARDOGS lobby-created event before routing', async () => {
    const listeners = new Map()
    const authStore = reactive({
      isLoggedIn: true,
      username: 'alpha',
      token: 'token',
      restoreAuth: () => true,
      syncProfile: jest.fn().mockResolvedValue({ active_lobby: null })
    })
    const queueStore = reactive({
      matchAccept: { active: true, cancelled: false, players: ['alpha'], queueMode: 'wardogs_beta9' },
      resetQueue: jest.fn(),
      syncWithServer: jest.fn().mockResolvedValue(undefined),
      acceptMatch: jest.fn().mockResolvedValue({ success: true, allAccepted: true, finalizingLobby: true })
    })
    const socketStore = {
      isConnected: false,
      initSocket: jest.fn().mockResolvedValue(true),
      cleanupSocket: jest.fn().mockResolvedValue(true),
      on: jest.fn((event, callback) => listeners.set(event, callback)),
      off: jest.fn()
    }
    const lobbyStore = { lobbyId: null, leaveLobby: jest.fn(), reset: jest.fn() }
    const groupStore = { syncStatus: jest.fn().mockResolvedValue(undefined), handleUpdate: jest.fn(), resetGroup: jest.fn() }
    const rootStore = { clearError: jest.fn(), setError: jest.fn(), setLoading: jest.fn() }
    const router = { push: jest.fn(), replace: jest.fn() }
    const route = reactive({ path: '/play', params: {}, meta: {} })
    let session
    const Host = defineComponent({
      setup() {
        session = useAppSession({ router, route, authStore, socketStore, rootStore,
          lobbyStore, queueStore, groupStore })
        return () => h('div')
      }
    })

    const wrapper = mount(Host)
    await flushPromises()
    router.push.mockClear()
    await session.handleAcceptMatch()
    expect(router.push).not.toHaveBeenCalled()
    expect(queueStore.acceptMatch).toHaveBeenCalledWith('alpha')

    listeners.get(SOCKET_EVENTS.LOBBY.CREATED)({
      lobby_id: 'wardogs-room-1', game_type: 'wardogs', players: ['alpha']
    })
    expect(queueStore.resetQueue).toHaveBeenCalledTimes(1)
    expect(router.push).toHaveBeenCalledWith('/wardogs/lobby/wardogs-room-1')
    wrapper.unmount()
  })
})
