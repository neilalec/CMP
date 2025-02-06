import { createRouter, createWebHistory } from 'vue-router';
import Home from '../views/Home.vue';
import Register from '../components/Register.vue';
import Login from '../components/Login.vue';
import Lobby from '../components/Lobby.vue';
import { authState } from '@/stores/auth';

const routes = [
  { path: '/', name: 'home', component: Home,  
  beforeEnter: (to, from, next) => {
      if (!authState.isLoggedIn) {
        next('/login');  // Redirect to login if not logged in
      } else {
        next();
      }
    }
  },
  { path: '/login', name: 'login', component: Login },
  { path: '/register', name: 'register', component: Register },
  { path: '/lobby/:lobbyId', name: 'lobby', component: Lobby, props:true },
  // { path: '/match/:id', name: 'match', component: MatchPage }
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,  // Single 'routes' array
});

router.beforeEach((to, from, next) => {
  const isAuthenticated = authState.isLoggedIn;
  if (!isAuthenticated && to.name !== 'login' && to.name !== 'register') {
    next({ name: 'login' }); // Redirect to login only if unauthenticated
  } else {
    next();
  }
});


export default router;
