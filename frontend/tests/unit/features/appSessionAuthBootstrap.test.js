import { defineComponent, h, onMounted, reactive } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { useAppSession } from '@/features/app/composables/useAppSession'

jest.mock('@/config', () => ({ PASSWORD_AUTH_ENABLED: false }))

describe('app session authentication bootstrap', () => {
  test('uses initial restore for a callback login instead of initializing a second socket', async () => {
    const authStore = reactive({
      isLoggedIn: false,
      token: null,
      username: null,
      restoreAuth() {
        this.isLoggedIn = true
        this.token = 'signed-token'
        this.username = 'steam_user'
        return true
      },
      async syncProfile() { return null },
      logout() { this.isLoggedIn = false }
    })
    const socketStore = {
      isConnected: false,
      initSocket: jest.fn().mockResolvedValue(true),
      cleanupSocket: jest.fn().mockResolvedValue(true),
      on: jest.fn(),
      off: jest.fn()
    }
    const route = reactive({ path: '/auth/steam/callback', params: {}, meta: {} })
    const emptyStore = { reset: jest.fn(), leaveLobby: jest.fn() }
    const rootStore = { setLoading: jest.fn(), setError: jest.fn(), clearError: jest.fn() }
    const queueStore = {
      matchAccept: { players: [], active: false, cancelled: false },
      syncWithServer: jest.fn().mockResolvedValue(undefined),
      updateQueueState: jest.fn(),
      setMatchAcceptCancelled: jest.fn(),
      resetQueue: jest.fn()
    }
    const groupStore = { handleUpdate: jest.fn(), syncStatus: jest.fn(), resetGroup: jest.fn() }
    const router = { push: jest.fn(), replace: jest.fn() }

    const Callback = defineComponent({
      setup() {
        onMounted(() => {
          authStore.isLoggedIn = true
          authStore.token = 'signed-token'
          authStore.username = 'steam_user'
        })
        return () => h('div')
      }
    })
    const Host = defineComponent({
      setup() {
        useAppSession({ router, route, authStore, socketStore, rootStore,
          lobbyStore: emptyStore, queueStore, groupStore })
        return () => h(Callback)
      }
    })

    const wrapper = mount(Host)
    await flushPromises()

    expect(socketStore.initSocket).toHaveBeenCalledTimes(1)
    expect(socketStore.initSocket).toHaveBeenCalledWith('signed-token', 'steam_user')
    expect(socketStore.cleanupSocket).not.toHaveBeenCalled()
    expect(authStore.isLoggedIn).toBe(true)
    wrapper.unmount()
  })

  test('waits for a Steam callback instead of bootstrapping an anonymous session', async () => {
    const authStore = reactive({
      isLoggedIn: false,
      token: null,
      username: null,
      restoreAuth: jest.fn(() => false),
      async syncProfile() { return null },
      logout: jest.fn()
    })
    const socketStore = {
      isConnected: false,
      initSocket: jest.fn().mockResolvedValue(true),
      cleanupSocket: jest.fn().mockResolvedValue(true),
      on: jest.fn(),
      off: jest.fn()
    }
    const route = reactive({ path: '/auth/steam/callback', params: {}, meta: { steamCallback: true } })
    const emptyStore = { reset: jest.fn(), leaveLobby: jest.fn() }
    const rootStore = { setLoading: jest.fn(), setError: jest.fn(), clearError: jest.fn() }
    const queueStore = {
      matchAccept: { players: [], active: false, cancelled: false },
      syncWithServer: jest.fn().mockResolvedValue(undefined),
      updateQueueState: jest.fn(),
      setMatchAcceptCancelled: jest.fn(),
      resetQueue: jest.fn()
    }
    const groupStore = { handleUpdate: jest.fn(), syncStatus: jest.fn(), resetGroup: jest.fn() }
    const router = { push: jest.fn(), replace: jest.fn() }

    const Callback = defineComponent({
      setup() {
        onMounted(() => {
          authStore.token = 'signed-token'
          authStore.username = 'steam_user'
          authStore.isLoggedIn = true
        })
        return () => h('div')
      }
    })
    const Host = defineComponent({
      setup() {
        useAppSession({ router, route, authStore, socketStore, rootStore,
          lobbyStore: emptyStore, queueStore, groupStore })
        return () => h(Callback)
      }
    })

    const wrapper = mount(Host)
    await flushPromises()

    expect(socketStore.initSocket).toHaveBeenCalledTimes(1)
    expect(socketStore.initSocket).toHaveBeenCalledWith('signed-token', 'steam_user')
    expect(router.replace).not.toHaveBeenCalledWith('/auth')
    wrapper.unmount()
  })

  test('does not open an anonymous socket on the Steam-only Auth route', async () => {
    const authStore = {
      isLoggedIn: false,
      token: null,
      username: null,
      restoreAuth: jest.fn(() => false)
    }
    const socketStore = {
      isConnected: false,
      initSocket: jest.fn(),
      cleanupSocket: jest.fn(),
      on: jest.fn(),
      off: jest.fn()
    }
    const route = reactive({ path: '/auth', params: {}, meta: { guest: true } })
    const emptyStore = { reset: jest.fn(), leaveLobby: jest.fn() }
    const rootStore = { clearError: jest.fn() }
    const queueStore = { matchAccept: { players: [], active: false, cancelled: false } }
    const groupStore = { handleUpdate: jest.fn() }
    const router = { push: jest.fn(), replace: jest.fn() }
    const Host = defineComponent({
      setup() {
        useAppSession({ router, route, authStore, socketStore, rootStore,
          lobbyStore: emptyStore, queueStore, groupStore })
        return () => h('div')
      }
    })

    const wrapper = mount(Host)
    await flushPromises()

    expect(socketStore.initSocket).not.toHaveBeenCalled()
    expect(router.replace).not.toHaveBeenCalledWith('/auth')
    wrapper.unmount()
  })
})
