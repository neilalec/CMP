import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Auth from '@/views/Auth.vue'

jest.mock('@/stores/authStore', () => ({ useAuthStore: jest.fn(() => ({})) }))
jest.mock('@/stores/lobbyStore', () => ({ useLobbyStore: jest.fn(() => ({})) }))
jest.mock('@/stores/rootStore', () => ({ useRootStore: jest.fn(() => ({})) }))
jest.mock('@/stores/socketStore', () => ({ useSocketStore: jest.fn(() => ({})) }))
jest.mock('@/features/auth/composables/useAuthView', () => ({
  useAuthView: jest.fn(() => ({
    formType: 'login',
    username: '',
    password: '',
    loading: false,
    handleSubmit: jest.fn(),
    toggleForm: jest.fn(),
    handleSteamSignIn: jest.fn()
  }))
}))

test('auth page shows CMP and WARDOGS branding with Steam sign-in', async () => {
  const screen = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ['/auth', '/terms', '/privacy'].map((path) => ({ path, component: screen }))
  })
  await router.push('/auth')
  await router.isReady()
  const wrapper = mount(Auth, { global: { plugins: [router] } })

  expect(wrapper.find('.auth-brand strong').text()).toBe('CMP')
  expect(wrapper.text()).toContain('WARDOGS matchmaking')
  expect(wrapper.text()).toContain('Continue with Steam')
  expect(wrapper.text()).not.toContain('Squad Comp Matchmaking')
  wrapper.unmount()
})
