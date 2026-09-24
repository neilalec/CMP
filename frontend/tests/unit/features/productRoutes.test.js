import { createPinia, setActivePinia } from 'pinia'
import router from '../../../src/router'
import { useAuthStore } from '../../../src/stores/authStore'

test('participant routes stay eager while legacy routes load their styling lazily', () => {
  const routeComponent = (name) => router.getRoutes().find((route) => route.name === name)?.components?.default
  expect(typeof routeComponent('play')).not.toBe('function')
  expect(typeof routeComponent('matches')).not.toBe('function')
  expect(typeof routeComponent('wardogs-lobby')).not.toBe('function')
  expect(typeof routeComponent('lobbies')).toBe('function')
  expect(typeof routeComponent('admin')).toBe('function')
  expect(typeof routeComponent('results')).toBe('function')
})

test('only routes that import the legacy bundle enable document-level legacy styling', () => {
  const legacyRoutes = [
    'lobbies', 'results', 'leaderboard', 'discord', 'about', 'terms',
    'privacy', 'steam-auth-callback', 'lobby', 'profile', 'admin', 'group'
  ]
  for (const name of legacyRoutes) {
    expect(router.getRoutes().find((route) => route.name === name)?.meta.legacyStyles).toBe(true)
  }
  for (const name of ['auth', 'play', 'matches', 'wardogs-prototype', 'wardogs-lobby']) {
    expect(router.getRoutes().find((route) => route.name === name)?.meta.legacyStyles).toBeUndefined()
  }
})

test('WARDOGS product routes work while participant legacy routes lead to Matches', async () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.isLoggedIn = true
  auth.token = 'test-token'
  auth.isAdmin = false
  auth.canToggleAdmin = false

  await router.push('/play')
  expect(router.currentRoute.value.path).toBe('/play')
  await router.push('/matches')
  expect(router.currentRoute.value.path).toBe('/matches')
  await router.push('/wardogs/lobby/test-lobby')
  expect(router.currentRoute.value.name).toBe('wardogs-lobby')
  await router.push('/profile')
  expect(router.currentRoute.value.path).toBe('/profile')
  await router.push('/results')
  expect(router.currentRoute.value.path).toBe('/matches')
  await router.push('/lobby/legacy-squad-lobby')
  expect(router.currentRoute.value.path).toBe('/matches')
  await router.push('/admin')
  expect(router.currentRoute.value.path).toBe('/play')

  auth.isAdmin = true
  await router.push('/admin')
  expect(router.currentRoute.value.path).toBe('/admin')

  auth.isLoggedIn = false
  await router.push('/profile')
  expect(router.currentRoute.value.path).toBe('/auth')
})

test('guest auth route stays visible and authenticated users are redirected to Play', async () => {
  localStorage.clear()
  setActivePinia(createPinia())
  const auth = useAuthStore()

  auth.isLoggedIn = false
  await router.push('/terms')
  await router.push('/auth')
  expect(router.currentRoute.value.path).toBe('/auth')

  auth.token = 'test-token'
  auth.username = 'testuser'
  auth.isLoggedIn = true
  await router.push('/terms')
  await router.push('/auth')
  expect(router.currentRoute.value.path).toBe('/play')
  expect(router.currentRoute.value.name).toBe('play')
})
