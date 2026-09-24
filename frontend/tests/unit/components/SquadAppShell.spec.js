import { mount } from '@vue/test-utils'
import { reactive } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import SquadApp from '@/SquadApp.vue'
import { useAuthStore } from '@/stores/authStore'
import { useSocketStore } from '@/stores/socketStore'
import { useRootStore } from '@/stores/rootStore'
import { useLobbyStore } from '@/stores/lobbyStore'
import { useQueueStore } from '@/stores/queueStore'
import { useGroupStore } from '@/stores/groupStore'

jest.mock('@/assets/scm-logo.png', () => 'scm-logo.png')
jest.mock('@/stores/authStore', () => ({ useAuthStore: jest.fn() }))
jest.mock('@/stores/socketStore', () => ({ useSocketStore: jest.fn() }))
jest.mock('@/stores/rootStore', () => ({ useRootStore: jest.fn() }))
jest.mock('@/stores/lobbyStore', () => ({ useLobbyStore: jest.fn() }))
jest.mock('@/stores/queueStore', () => ({ useQueueStore: jest.fn() }))
jest.mock('@/stores/groupStore', () => ({ useGroupStore: jest.fn() }))
jest.mock('@/features/app/composables/useAppSession', () => ({
  useAppSession: jest.fn(() => {
    const { ref } = require('vue')
    return {
      isInLobby: ref(false), currentLobbyId: ref(null), playRoute: ref('/play'),
      isMatchAcceptParticipant: ref(false), isMatchAcceptCancelled: ref(false),
      handleProfile: jest.fn(), handleGroup: jest.fn(), handleAcceptMatch: jest.fn(),
      handleCloseMatchAccept: jest.fn(), handleDismissMatchAccept: jest.fn()
    }
  })
}))
jest.mock('@/features/app/composables/useThemeMode', () => ({
  useThemeMode: jest.fn(() => {
    const { ref } = require('vue')
    return { themeLabel: ref('Light Theme'), themeIcon: ref('L'), nextThemeLabel: ref('Dark Theme'), cycleTheme: jest.fn() }
  })
}))
jest.mock('@/features/app/composables/useMatchAcceptChime', () => ({ useMatchAcceptChime: jest.fn() }))

test('Squad shell restores the historical brand, sidebars, and navigation', async () => {
  useAuthStore.mockReturnValue(reactive({ isLoggedIn: true, isAdmin: false, canToggleAdmin: false, playerName: 'Neil', username: 'neil' }))
  useSocketStore.mockReturnValue({})
  useRootStore.mockReturnValue({ globalError: null, globalErrorDetails: null })
  useLobbyStore.mockReturnValue({ step: 0, lobbyId: null })
  useQueueStore.mockReturnValue({
    inQueue: false, queueMode: null, loading: false,
    matchAccept: { acceptedPlayers: [], players: [], acceptedCount: 0, requiredCount: 0, countdown: 0 }
  })
  useGroupStore.mockReturnValue({ inGroup: false })

  const screen = { template: '<div>Squad queue</div>' }
  const router = createRouter({
    history: createMemoryHistory(),
    routes: ['/play', '/lobbies', '/results', '/leaderboard', '/discord', '/about', '/profile', '/group', '/admin', '/terms', '/privacy']
      .map((path) => ({ path, component: screen }))
  })
  await router.push('/play')
  await router.isReady()

  const wrapper = mount(SquadApp, { global: { plugins: [router], stubs: { MatchAcceptModal: true, MatchPhaseTracker: true } } })
  expect(wrapper.get('.brand-name').text()).toBe('Squad Comp Matchmaking')
  expect(wrapper.find('.app-left').exists()).toBe(true)
  expect(wrapper.find('.app-right').exists()).toBe(true)
  expect(wrapper.find('.main-window-body').text()).toContain('Squad queue')
  expect(wrapper.find('.app-left').text()).toContain('Lobbies')
  expect(wrapper.find('.app-left').text()).toContain('Results')
  expect(wrapper.find('.app-left').text()).toContain('Leaderboard')
  expect(wrapper.find('.primary-nav').exists()).toBe(false)
  expect(wrapper.text()).not.toContain('WARDOGS')
  wrapper.unmount()
})
