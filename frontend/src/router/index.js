import { createRouter, createWebHistory } from 'vue-router';
import Play from '../views/Play.vue';
import Matches from '../views/Matches.vue';
import Auth from '../views/Auth.vue';
import SquadPlay from '../views/SquadPlay.vue';
import SquadAuth from '../views/SquadAuth.vue';
import SquadProfile from '../views/SquadProfile.vue';
import SquadAdmin from '../views/SquadAdmin.vue';
import SquadAbout from '../views/SquadAbout.vue';
import SquadTerms from '../views/SquadTerms.vue';
import SquadPrivacy from '../views/SquadPrivacy.vue';
import WardogsPrototype from '../features/wardogs/WardogsPrototype.vue';
import { useAuthStore } from '@/stores/authStore';
import { useRootStore } from '@/stores/rootStore';
import { getCurrentLobbyId } from '../utils/lobbyPersistence';
import { developmentTarget } from '../devTarget';

export const buildRoutes = (target = developmentTarget) => {
  const squad = target === 'squad';
  const legacyMeta = (meta = {}) => squad ? meta : { ...meta, legacyStyles: true };

  return [
    { path: '/', redirect: '/play' },
    { path: '/play', name: 'play', component: squad ? SquadPlay : Play, meta: { requiresAuth: true } },
    ...(!squad ? [
      { path: '/matches', name: 'matches', component: Matches, meta: { requiresAuth: true } }
    ] : []),
    { path: '/queue', redirect: '/play' },
    {
      path: '/lobbies', name: 'lobbies',
      component: squad ? SquadPlay : () => import('../views/LegacyLobbies.vue'),
      meta: legacyMeta({ requiresAuth: true, ...(!squad && { legacySquad: true }) })
    },
    {
      path: '/results', name: 'results',
      component: () => import('../views/Results.vue'),
      meta: legacyMeta({ requiresAuth: true, ...(!squad && { legacySquad: true }) })
    },
    {
      path: '/leaderboard', name: 'leaderboard',
      component: () => import('../views/Leaderboard.vue'),
      meta: legacyMeta({ requiresAuth: true, ...(!squad && { legacySquad: true }) })
    },
    {
      path: '/discord', name: 'discord',
      component: () => import('../views/Discord.vue'),
      meta: legacyMeta({ requiresAuth: true })
    },
    {
      path: '/about', name: 'about',
      component: squad ? SquadAbout : () => import('../views/About.vue'),
      meta: legacyMeta({ requiresAuth: true })
    },
    {
      path: '/terms', name: 'terms',
      component: squad ? SquadTerms : () => import('../views/Terms.vue'),
      meta: legacyMeta()
    },
    {
      path: '/privacy', name: 'privacy',
      component: squad ? SquadPrivacy : () => import('../views/Privacy.vue'),
      meta: legacyMeta()
    },
    { path: '/auth', name: 'auth', component: squad ? SquadAuth : Auth, meta: { guest: true } },
    {
      path: '/auth/steam/callback', name: 'steam-auth-callback',
      component: () => import('../views/SteamAuthCallback.vue'),
      meta: legacyMeta({ steamCallback: true })
    },
    {
      path: '/lobby/:lobbyId', name: 'lobby',
      component: () => import('../views/Lobby.vue'), props: true,
      meta: legacyMeta({ requiresAuth: true, ...(!squad && { legacySquad: true }) })
    },
    {
      path: '/profile', name: 'profile',
      component: squad ? SquadProfile : () => import('../views/Profile.vue'),
      meta: legacyMeta({ requiresAuth: true })
    },
    {
      path: '/admin', name: 'admin',
      component: squad ? SquadAdmin : () => import('../views/Admin.vue'),
      meta: legacyMeta({ requiresAuth: true, requiresAdmin: true })
    },
    { path: '/servers/add', redirect: '/admin', meta: { requiresAuth: true, requiresAdmin: true } },
    {
      path: '/group', name: 'group',
      component: () => import('../views/Group.vue'),
      meta: legacyMeta({ requiresAuth: true })
    },
    ...(!squad ? [
      { path: '/prototype/wardogs', name: 'wardogs-prototype', component: WardogsPrototype, meta: { prototype: true } },
      { path: '/wardogs/lobby/:lobbyId', name: 'wardogs-lobby', component: WardogsPrototype, meta: { requiresAuth: true } }
    ] : [])
  ];
};

export const createProductRouter = (target = developmentTarget) => {
  const squad = target === 'squad';
  const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes: buildRoutes(target),
    scrollBehavior(to, from, savedPosition) {
      if (savedPosition) return savedPosition;
      return { top: 0, left: 0 };
    }
  });

  router.beforeEach((to, from, next) => {
    const authStore = useAuthStore();
    const rootStore = useRootStore();
    const isAuthenticated = authStore.isLoggedIn;

    rootStore.clearError();

    if (to.meta.steamCallback) {
      next();
    } else if (to.meta.requiresAuth && !isAuthenticated) {
      next('/auth');
    } else if (to.meta.requiresAdmin && !authStore.isAdmin && !authStore.canToggleAdmin) {
      next('/play');
    } else if (!squad && to.meta.legacySquad && !authStore.isAdmin && !authStore.canToggleAdmin) {
      next('/matches');
    } else if (squad && (to.path === '/queue' || to.path === '/play') && getCurrentLobbyId()) {
      next(`/lobby/${getCurrentLobbyId()}`);
    } else if (to.meta.guest && isAuthenticated) {
      next('/play');
    } else {
      next();
    }
  });

  return router;
};

export default createProductRouter();
