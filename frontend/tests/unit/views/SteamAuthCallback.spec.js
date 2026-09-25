import { mount, flushPromises } from '@vue/test-utils'
import SteamAuthCallback from '@/views/SteamAuthCallback.vue'
import { useAuthStore } from '@/stores/authStore'
import { useLobbyStore } from '@/stores/lobbyStore'
import { useRootStore } from '@/stores/rootStore'

jest.mock('vue-router', () => ({ useRouter: () => ({ replace: global.mockRouterReplace }) }))
jest.mock('@/stores/authStore', () => ({ useAuthStore: jest.fn() }))
jest.mock('@/stores/lobbyStore', () => ({ useLobbyStore: jest.fn() }))
jest.mock('@/stores/rootStore', () => ({ useRootStore: jest.fn() }))

describe('SteamAuthCallback', () => {
  test('persists a successful callback once across callback view remounts', async () => {
    global.mockRouterReplace = jest.fn()
    const profile = {
      username: 'steam_user',
      display_name: 'Steam User',
      steam_id: '76561198124553635',
      is_admin: true,
      can_toggle_admin: true
    }
    const setAuth = jest.fn().mockResolvedValue(undefined)
    useAuthStore.mockReturnValue({ setAuth })
    useLobbyStore.mockReturnValue({ leaveLobby: jest.fn() })
    useRootStore.mockReturnValue({ setError: jest.fn() })

    const payload = btoa(JSON.stringify({
      success: true,
      access_token: 'signed-token',
      username: 'steam_user',
      profile,
      current_match: { gameType: 'wardogs', lobbyId: 'wd-callback-room' }
    }))
    window.history.replaceState({}, '', `/auth/steam/callback#payload=${payload}`)

    const first = mount(SteamAuthCallback)
    await flushPromises()
    first.unmount()
    const second = mount(SteamAuthCallback)
    await flushPromises()

    expect(setAuth).toHaveBeenCalledTimes(1)
    expect(setAuth).toHaveBeenCalledWith('signed-token', 'steam_user', profile)
    expect(global.mockRouterReplace).toHaveBeenCalledWith('/wardogs/lobby/wd-callback-room')
    expect(window.location.hash).toBe('')
    second.unmount()
  })
})
