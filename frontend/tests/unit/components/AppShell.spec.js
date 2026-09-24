import { mount, flushPromises } from '@vue/test-utils'
import { reactive, nextTick } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import App from '@/App.vue'
import { useAuthStore } from '@/stores/authStore'
import { useSocketStore } from '@/stores/socketStore'
import { useRootStore } from '@/stores/rootStore'
import { useLobbyStore } from '@/stores/lobbyStore'
import { useQueueStore } from '@/stores/queueStore'
import { useGroupStore } from '@/stores/groupStore'

jest.mock('@/stores/authStore', () => ({ useAuthStore: jest.fn() }))
jest.mock('@/stores/socketStore', () => ({ useSocketStore: jest.fn() }))
jest.mock('@/stores/rootStore', () => ({ useRootStore: jest.fn() }))
jest.mock('@/stores/lobbyStore', () => ({ useLobbyStore: jest.fn() }))
jest.mock('@/stores/queueStore', () => ({ useQueueStore: jest.fn() }))
jest.mock('@/stores/groupStore', () => ({ useGroupStore: jest.fn() }))
jest.mock('@/features/app/composables/useAppSession', () => ({
  useAppSession: jest.fn(() => ({
    isMatchAcceptParticipant: false,
    isMatchAcceptCancelled: false,
    handleAcceptMatch: jest.fn(),
    handleCloseMatchAccept: jest.fn(),
    handleDismissMatchAccept: jest.fn()
  }))
}))
jest.mock('@/features/app/composables/useMatchAcceptChime', () => ({
  useMatchAcceptChime: jest.fn()
}))

const makeRouter = async () => {
  const screen = { template: '<div>Screen</div>' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      ...['/play', '/matches', '/profile', '/admin', '/group', '/about', '/discord', '/terms', '/privacy', '/auth']
        .map((path) => ({ path, component: screen })),
      { path: '/wardogs/lobby/:lobbyId', component: screen }
    ]
  })
  await router.push('/play')
  await router.isReady()
  return router
}

describe('CMP product shell', () => {
  let auth

  beforeEach(() => {
    auth = reactive({ isLoggedIn: true, isAdmin: false, canToggleAdmin: false, playerName: 'Neil', username: 'neil' })
    useAuthStore.mockReturnValue(auth)
    useSocketStore.mockReturnValue({})
    useRootStore.mockReturnValue({ globalError: null, globalErrorDetails: null })
    useLobbyStore.mockReturnValue({})
    useQueueStore.mockReturnValue({
      matchAccept: { acceptedPlayers: [], players: [], acceptedCount: 0, requiredCount: 0, countdown: 0, hasAccepted: false },
      loading: false
    })
    useGroupStore.mockReturnValue({})
  })

  test('shows CMP navigation and a reachable mobile menu without Squad branding', async () => {
    const router = await makeRouter()
    const wrapper = mount(App, { global: { plugins: [router], stubs: { MatchAcceptModal: true } } })
    await flushPromises()

    expect(wrapper.get('.brand').attributes('aria-label')).toBe('CMP home')
    expect(wrapper.get('.brand-product').text()).toBe('WARDOGS')
    expect(wrapper.get('.app-shell').classes()).toContain('cmp-page')
    expect(wrapper.find('.primary-nav').text()).toContain('Play')
    expect(wrapper.find('.primary-nav').text()).toContain('Matches')
    expect(wrapper.find('.primary-nav').text()).toContain('Group')
    expect(wrapper.find('.primary-nav').text()).toContain('Profile')
    expect(wrapper.find('.primary-nav').text()).not.toContain('Admin')
    expect(wrapper.text()).not.toContain('Squad')
    expect(wrapper.find('.account-menu-items').text()).toContain('Profile')
    expect(wrapper.find('.app-left').exists()).toBe(false)
    expect(wrapper.find('.app-right').exists()).toBe(false)

    const menuButton = wrapper.find('.mobile-nav-toggle')
    expect(menuButton.attributes('aria-expanded')).toBe('false')
    await menuButton.trigger('click')
    expect(menuButton.attributes('aria-expanded')).toBe('true')
    expect(wrapper.find('.primary-nav').classes()).toContain('is-open')
    wrapper.unmount()
  })

  test('Admin appears only when the account is permitted', async () => {
    const router = await makeRouter()
    const wrapper = mount(App, { global: { plugins: [router], stubs: { MatchAcceptModal: true } } })
    expect(wrapper.find('.primary-nav').text()).not.toContain('Admin')

    auth.canToggleAdmin = true
    await nextTick()
    expect(wrapper.find('.primary-nav').text()).toContain('Admin')
    wrapper.unmount()
  })

  test('current match remains directly reachable when one is assigned', async () => {
    const queue = reactive({
      wardogsLobbyId: 'match-123',
      matchAccept: { acceptedPlayers: [], players: [], acceptedCount: 0, requiredCount: 0, countdown: 0, hasAccepted: false },
      loading: false
    })
    useQueueStore.mockReturnValue(queue)
    const router = await makeRouter()
    const wrapper = mount(App, { global: { plugins: [router], stubs: { MatchAcceptModal: true } } })

    expect(wrapper.get('.current-match-link').attributes('href')).toBe('/wardogs/lobby/match-123')
    queue.wardogsLobbyId = null
    await nextTick()
    expect(wrapper.find('.current-match-link').exists()).toBe(false)
    wrapper.unmount()
  })

  test('guest state keeps the Auth RouterView mounted inside the guest shell', async () => {
    auth.isLoggedIn = false
    const router = await makeRouter()
    await router.push('/auth')
    const wrapper = mount(App, { global: { plugins: [router], stubs: { MatchAcceptModal: true } } })
    await flushPromises()

    expect(wrapper.find('.auth-shell').exists()).toBe(true)
    expect(wrapper.find('.auth-shell').classes()).toContain('is-auth-view')
    expect(wrapper.find('.auth-shell').text()).toContain('Screen')
    wrapper.unmount()
  })

  test('other guest routes do not inherit the Auth artwork', async () => {
    auth.isLoggedIn = false
    const router = await makeRouter()
    await router.push('/terms')
    const wrapper = mount(App, { global: { plugins: [router], stubs: { MatchAcceptModal: true } } })

    expect(wrapper.get('.auth-shell').classes()).not.toContain('is-auth-view')
    wrapper.unmount()
  })
})
