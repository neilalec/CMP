import { createRouter, createWebHistory } from 'vue-router';
import Play from '../views/Play.vue';
import Auth from '../views/Auth.vue';
import Lobby from '../views/Lobby.vue';
import Profile from '../views/Profile.vue';
import Group from '../views/Group.vue';
import Results from '../views/Results.vue';
import Admin from '../views/Admin.vue';
import About from '../views/About.vue';
import Discord from '../views/Discord.vue';
import Terms from '../views/Terms.vue';
import Privacy from '../views/Privacy.vue';
import SteamAuthCallback from '../views/SteamAuthCallback.vue';
import { useAuthStore } from '@/stores/authStore';
import { useRootStore } from '@/stores/rootStore';
import { getCurrentLobbyId } from '../utils/lobbyPersistence';

const routes = [
  {
    path: '/',
    redirect: '/play'
  },
  { 
    path: '/play', 
    name: 'play', 
    component: Play, 
    meta: { requiresAuth: true } 
  },
  { 
    path: '/queue', 
    redirect: '/play'
  },
  { 
    path: '/lobbies', 
    name: 'lobbies', 
    component: Play, 
    meta: { requiresAuth: true } 
  },
  {
    path: '/results',
    name: 'results',
    component: Results,
    meta: { requiresAuth: true }
  },
  {
    path: '/discord',
    name: 'discord',
    component: Discord,
    meta: { requiresAuth: true }
  },
  {
    path: '/about',
    name: 'about',
    component: About,
    meta: { requiresAuth: true }
  },
  {
    path: '/terms',
    name: 'terms',
    component: Terms
  },
  {
    path: '/privacy',
    name: 'privacy',
    component: Privacy
  },
  { 
    path: '/auth', 
    name: 'auth', 
    component: Auth, 
    meta: { guest: true } 
  },
  {
    path: '/auth/steam/callback',
    name: 'steam-auth-callback',
    component: SteamAuthCallback,
    meta: { steamCallback: true }
  },
  { 
    path: '/lobby/:lobbyId', 
    name: 'lobby', 
    component: Lobby, 
    props: true, 
    meta: { requiresAuth: true } 
  },
  { 
    path: '/profile', 
    name: 'profile', 
    component: Profile, 
    meta: { requiresAuth: true } 
  },
  {
    path: '/admin',
    name: 'admin',
    component: Admin,
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  {
    path: '/servers/add',
    redirect: '/admin',
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  { 
    path: '/group', 
    name: 'group', 
    component: Group, 
    meta: { requiresAuth: true } 
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
});

// Navigation guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  const rootStore = useRootStore();
  const isAuthenticated = authStore.isLoggedIn;
  const currentLobby = getCurrentLobbyId();

  // Clear any existing errors when changing routes
  rootStore.clearError();

  // Handle authentication redirects
  if (to.meta.steamCallback) {
    next();
  } else if (to.meta.requiresAuth && !isAuthenticated) {
    next('/auth');
  } else if (to.meta.requiresAdmin && !authStore.isAdmin && !authStore.canToggleAdmin) {
    next('/play');
  } else if ((to.path === '/queue' || to.path === '/play') && currentLobby) {
    next(`/lobby/${currentLobby}`);
  } else if (to.meta.guest && isAuthenticated) {
    next('/play');
  } else {
    next();
  }
});

export default router;
