import { defineStore } from 'pinia';
import { useRootStore } from './rootStore';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
    isLoggedIn: !!localStorage.getItem('token')
  }),

  actions: {
    setAuth(token, username) {
      this.token = token;
      this.username = username;
      this.isLoggedIn = true;
      // Persist to localStorage
      localStorage.setItem('token', token);
      localStorage.setItem('username', username);
    },

    async login(token, username) {
      try {
        this.setAuth(token, username);
        return true;
      } catch (error) {
        console.error('Login error:', error);
        this.logout();
        throw error;
      }
    },

    async logout() {
      const rootStore = useRootStore();
      
      // Clear auth state first
      this.token = null;
      this.username = null;
      this.isLoggedIn = false;

      // Clear localStorage
      localStorage.removeItem('token');
      localStorage.removeItem('username');
      
      // Clear error state
      rootStore.clearError();
    },

    restoreAuth() {
      const token = localStorage.getItem('token');
      const username = localStorage.getItem('username');
      
      if (token && username) {
        this.setAuth(token, username);
        return true;
      }
      
      return false;
    }
  }
});
