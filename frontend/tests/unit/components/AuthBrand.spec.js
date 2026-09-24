import { mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import Auth from '@/views/Auth.vue'

jest.mock('@/config', () => ({ PASSWORD_AUTH_ENABLED: true }))
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

async function mountAuth() {
  const screen = { template: '<div />' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ['/auth', '/terms', '/privacy'].map((path) => ({ path, component: screen }))
  })
  await router.push('/auth')
  await router.isReady()
  return mount(Auth, { global: { plugins: [router] } })
}

test('auth page presents CMP sign-in with Steam as the primary action', async () => {
  const wrapper = await mountAuth()

  expect(wrapper.find('.auth-mark').text()).toBe('CMP')
  expect(wrapper.text()).toContain('WARDOGS matchmaking')
  expect(wrapper.get('h1').text()).toBe('Sign in')
  expect(wrapper.get('.steam-button').text()).toContain('Continue with Steam')
  expect(wrapper.get('.steam-button').attributes('aria-label')).toBe('Continue with Steam')
  expect(wrapper.find('.auth-card').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('Squad Comp Matchmaking')
  wrapper.unmount()
})

test('Steam CTA invokes the existing Steam sign-in action', async () => {
  const wrapper = await mountAuth()
  const { handleSteamSignIn } = require('@/features/auth/composables/useAuthView').useAuthView.mock.results.at(-1).value

  await wrapper.get('.steam-button').trigger('click')

  expect(handleSteamSignIn).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})

test('local account flow remains available behind a keyboard-operable disclosure', async () => {
  const wrapper = await mountAuth()
  const { handleSubmit, toggleForm } = require('@/features/auth/composables/useAuthView').useAuthView.mock.results.at(-1).value

  expect(wrapper.get('details.auth-local-access').attributes('open')).toBeUndefined()
  expect(wrapper.get('summary').text()).toBe('Use local account')
  await wrapper.get('summary').trigger('click')
  expect(wrapper.find('form.auth-local-form').exists()).toBe(true)
  expect(wrapper.get('label[for="auth-username"]').text()).toBe('Username')
  expect(wrapper.get('label[for="auth-password"]').text()).toBe('Password')
  await wrapper.get('form').trigger('submit')
  expect(handleSubmit).toHaveBeenCalledTimes(1)
  await wrapper.get('.form-toggle').trigger('click')
  expect(toggleForm).toHaveBeenCalledTimes(1)
  wrapper.unmount()
})

test('legal links remain available on the sign-in page', async () => {
  const wrapper = await mountAuth()

  expect(wrapper.get('a[href="/terms"]').text()).toBe('Terms')
  expect(wrapper.get('a[href="/privacy"]').text()).toBe('Privacy Policy')
  wrapper.unmount()
})
