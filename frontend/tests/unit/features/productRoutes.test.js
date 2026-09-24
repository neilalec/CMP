import { createPinia, setActivePinia } from 'pinia'
import router from '../../../src/router'
import { useAuthStore } from '../../../src/stores/authStore'

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
