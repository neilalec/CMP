import { createPinia, setActivePinia } from 'pinia'
import { buildRoutes, createProductRouter } from '@/router'
import SquadPlay from '@/views/SquadPlay.vue'
import SquadAuth from '@/views/SquadAuth.vue'
import SquadProfile from '@/views/SquadProfile.vue'
import SquadAdmin from '@/views/SquadAdmin.vue'
import Play from '@/views/Play.vue'
import Auth from '@/views/Auth.vue'
import { useAuthStore } from '@/stores/authStore'

const route = (routes, name) => routes.find((item) => item.name === name)

test('each development target selects its own entry screens and routes', () => {
  const squad = buildRoutes('squad')
  const wardogs = buildRoutes('wardogs')

  expect(route(squad, 'play').component).toBe(SquadPlay)
  expect(route(squad, 'lobbies').component).toBe(SquadPlay)
  expect(route(squad, 'auth').component).toBe(SquadAuth)
  expect(route(squad, 'profile').component).toBe(SquadProfile)
  expect(route(squad, 'group').component).not.toBe(route(wardogs, 'group').component)
  expect(route(squad, 'admin').component).toBe(SquadAdmin)
  expect(route(squad, 'results').meta.legacySquad).toBeUndefined()
  expect(route(squad, 'wardogs-lobby')).toBeUndefined()
  expect(route(squad, 'matches')).toBeUndefined()

  expect(route(wardogs, 'play').component).toBe(Play)
  expect(route(wardogs, 'auth').component).toBe(Auth)
  expect(route(wardogs, 'matches')).toBeDefined()
  expect(route(wardogs, 'results').meta.legacySquad).toBe(true)
  expect(route(wardogs, 'wardogs-lobby')).toBeDefined()
})

test('Squad participants can reach their historical results and leaderboard routes', async () => {
  setActivePinia(createPinia())
  const auth = useAuthStore()
  auth.isLoggedIn = true
  auth.token = 'test-token'
  auth.isAdmin = false
  auth.canToggleAdmin = false

  const router = createProductRouter('squad')
  await router.push('/results')
  expect(router.currentRoute.value.path).toBe('/results')
  await router.push('/leaderboard')
  expect(router.currentRoute.value.path).toBe('/leaderboard')
  await router.push('/lobbies')
  expect(router.currentRoute.value.path).toBe('/lobbies')
})
