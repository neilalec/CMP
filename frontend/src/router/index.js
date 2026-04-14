import { createRouter, createWebHistory } from 'vue-router';
import Home from '../views/Home.vue';
import Auth from '../components/Auth.vue';
import Lobby from '../components/Lobby.vue';
import Profile from '../views/Profile.vue';
import Group from '../views/Group.vue';
import { useAuthStore } from '@/stores/authStore';
import { useRootStore } from '@/stores/rootStore';

const routes = [
  { 
    path: '/', 
    name: 'home', 
    component: Home, 
    meta: { requiresAuth: true } 
  },
  { 
    path: '/queue', 
    name: 'queue', 
    component: Home, 
    meta: { requiresAuth: true } 
  },
  { 
    path: '/lobbies', 
    name: 'lobbies', 
    component: Home, 
    meta: { requiresAuth: true } 
  },
  { 
    path: '/auth', 
    name: 'auth', 
    component: Auth, 
    meta: { guest: true } 
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
  const currentLobby = localStorage.getItem('currentLobby');

  // Clear any existing errors when changing routes
  rootStore.clearError();

  // Handle authentication redirects
  if (to.meta.requiresAuth && !isAuthenticated) {
    next('/auth');
  } else if (to.path === '/queue' && currentLobby) {
    next(`/lobby/${currentLobby}`);
  } else if (to.meta.guest && isAuthenticated) {
    next('/');
  } else {
    next();
  }
});

export default router;
