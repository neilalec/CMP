import { createRouter, createWebHistory } from 'vue-router';
import Play from '../views/Play.vue';
import Matches from '../views/Matches.vue';
import Auth from '../views/Auth.vue';
import WardogsPrototype from '../features/wardogs/WardogsPrototype.vue';
import { useAuthStore } from '@/stores/authStore';
import { useRootStore } from '@/stores/rootStore';

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
    path: '/matches',
    name: 'matches',
    component: Matches,
    meta: { requiresAuth: true }
  },
  { 
    path: '/queue', 
    redirect: '/play'
  },
  { 
    path: '/lobbies', 
    name: 'lobbies', 
    component: () => import('../views/LegacyLobbies.vue'),
    meta: { requiresAuth: true, legacySquad: true, legacyStyles: true }
  },
  {
    path: '/results',
    name: 'results',
    component: () => import('../views/Results.vue'),
    meta: { requiresAuth: true, legacySquad: true, legacyStyles: true }
  },
  {
    path: '/leaderboard',
    name: 'leaderboard',
    component: () => import('../views/Leaderboard.vue'),
    meta: { requiresAuth: true, legacySquad: true, legacyStyles: true }
  },
  {
    path: '/discord',
    name: 'discord',
    component: () => import('../views/Discord.vue'),
    meta: { requiresAuth: true, legacyStyles: true }
  },
  {
    path: '/about',
    name: 'about',
    component: () => import('../views/About.vue'),
    meta: { requiresAuth: true, legacyStyles: true }
  },
  {
    path: '/terms',
    name: 'terms',
    component: () => import('../views/Terms.vue'),
    meta: { legacyStyles: true }
  },
  {
    path: '/privacy',
    name: 'privacy',
    component: () => import('../views/Privacy.vue'),
    meta: { legacyStyles: true }
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
    component: () => import('../views/SteamAuthCallback.vue'),
    meta: { steamCallback: true, legacyStyles: true }
  },
  { 
    path: '/lobby/:lobbyId', 
    name: 'lobby', 
    component: () => import('../views/Lobby.vue'),
    props: true, 
    meta: { requiresAuth: true, legacySquad: true, legacyStyles: true }
  },
  { 
    path: '/profile', 
    name: 'profile', 
    component: () => import('../views/Profile.vue'),
    meta: { requiresAuth: true, legacyStyles: true }
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('../views/Admin.vue'),
    meta: { requiresAuth: true, requiresAdmin: true, legacyStyles: true }
  },
  {
    path: '/servers/add',
    redirect: '/admin',
    meta: { requiresAuth: true, requiresAdmin: true }
  },
  { 
    path: '/group', 
    name: 'group', 
    component: () => import('../views/Group.vue'),
    meta: { requiresAuth: true, legacyStyles: true }
  },
  {
    path: '/prototype/wardogs',
    name: 'wardogs-prototype',
    component: WardogsPrototype,
    meta: { prototype: true }
  },
  {
    path: '/wardogs/lobby/:lobbyId',
    name: 'wardogs-lobby',
    component: WardogsPrototype,
    meta: { requiresAuth: true }
  },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition;
    return { top: 0, left: 0 };
  }
});

// Navigation guard
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore();
  const rootStore = useRootStore();
  const isAuthenticated = authStore.isLoggedIn;

  // Clear any existing errors when changing routes
  rootStore.clearError();

  // Handle authentication redirects
  if (to.meta.steamCallback) {
    next();
  } else if (to.meta.requiresAuth && !isAuthenticated) {
    next('/auth');
  } else if (to.meta.requiresAdmin && !authStore.isAdmin && !authStore.canToggleAdmin) {
    next('/play');
  } else if (to.meta.legacySquad && !authStore.isAdmin && !authStore.canToggleAdmin) {
    next('/matches');
  } else if (to.meta.guest && isAuthenticated) {
    next('/play');
  } else {
    next();
  }
});

export default router;
