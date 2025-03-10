import { defineStore } from 'pinia';
import { useSocketStore } from './socketStore';
import { useRootStore } from './rootStore';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
    isLoggedIn: !!localStorage.getItem('token')
  }),

  actions: {
    restoreAuth() {
      const token = localStorage.getItem('token');
      const username = localStorage.getItem('username');
      
      if (token && username) {
        this.token = token;
        this.username = username;
        this.isLoggedIn = true;
        return true;
      }
      
      return false;
    },

    async setAuth(token, username) {
      this.token = token;
      this.username = username;
      this.isLoggedIn = true;
      
      localStorage.setItem('token', token);
      localStorage.setItem('username', username);
    },

    async register(token, username) {
      try {
        await this.setAuth(token, username);
        return true;
      } catch (error) {
        const rootStore = useRootStore();
        rootStore.setError({
          message: 'Registration failed',
          details: error.message,
          context: 'auth-register'
        });
        this.logout();
        throw error;
      }
    },

    async login(token, username) {
      try {
        await this.setAuth(token, username);
        return true;
      } catch (error) {
        const rootStore = useRootStore();
        rootStore.setError({
          message: 'Login failed',
          details: error.message,
          context: 'auth-login'
        });
        this.logout();
        throw error;
      }
    },

    logout() {
      // Clear auth state
      this.token = null;
      this.username = null;
      this.isLoggedIn = false;

      // Clear localStorage auth data only
      localStorage.removeItem('token');
      localStorage.removeItem('username');
      
      // Don't cleanup socket or lobby state
      // const socketStore = useSocketStore();
      // socketStore.cleanupSocket();

      // Clear any errors
      const rootStore = useRootStore();
      rootStore.clearError();
    },

    checkAuth() {
      return this.isLoggedIn && !!this.token && !!this.username;
    }
  }
});
