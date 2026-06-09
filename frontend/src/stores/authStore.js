import { defineStore } from 'pinia';
import { useRootStore } from './rootStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { runStoreSocketAction } from './helpers/storeSocketAction';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
    steamId: localStorage.getItem('steamId') || '',
    steamIdLocked: false,
    isAdmin: localStorage.getItem('isAdmin') === 'true',
    isLoggedIn: !!localStorage.getItem('token')
  }),

  getters: {
    hasSteamId: (state) => !!state.steamId
  },

  actions: {
    clearAuthState() {
      this.token = null;
      this.username = null;
      this.isLoggedIn = false;
      this.steamId = '';
      this.steamIdLocked = false;
      this.isAdmin = false;
    },

    clearPersistedAuth() {
      localStorage.removeItem('token');
      localStorage.removeItem('username');
      localStorage.removeItem('steamId');
      localStorage.removeItem('isAdmin');
    },

    restoreAuth() {
      const token = localStorage.getItem('token');
      const username = localStorage.getItem('username');
      const steamId = localStorage.getItem('steamId') || '';
      const isAdmin = localStorage.getItem('isAdmin') === 'true';
      
      if (token && username) {
        this.token = token;
        this.username = username;
        this.steamId = steamId;
        this.isAdmin = isAdmin;
        this.isLoggedIn = true;
        return true;
      }
      
      return false;
    },

    updateProfile(profile = {}) {
      this.steamId = profile.steam_id || '';
      this.steamIdLocked = !!profile.steam_id_locked;
      this.isAdmin = !!profile.is_admin;
      localStorage.setItem('steamId', this.steamId);
      localStorage.setItem('isAdmin', String(this.isAdmin));
    },

    async setAuth(token, username, profile = null) {
      this.token = token;
      this.username = username;
      this.isLoggedIn = true;
      
      localStorage.setItem('token', token);
      localStorage.setItem('username', username);
      this.updateProfile(profile || {});
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
      this.clearAuthState();
      this.clearPersistedAuth();

      // Clear any errors
      const rootStore = useRootStore();
      rootStore.clearError();
    },

    async syncProfile() {
      if (!this.username) return null;
      const response = await runStoreSocketAction(this, {
        event: SOCKET_EVENTS.PROFILE.STATUS,
        payload: { username: this.username },
        setLoading: false,
        fallbackMessage: 'Failed to load profile',
        validate: (response) => {
          if (!response?.success || !response.profile) {
            throw new Error(response?.message || 'Failed to load profile');
          }
        },
        onSuccess: (response) => {
          this.updateProfile(response.profile);
        }
      });
      return response?.profile || null;
    },

    async updateSteamId(steamId) {
      if (!this.username) {
        throw new Error('Not authenticated');
      }
      const response = await runStoreSocketAction(this, {
        event: SOCKET_EVENTS.PROFILE.UPDATE_STEAM_ID,
        payload: {
          username: this.username,
          steam_id: steamId
        },
        setLoading: false,
        fallbackMessage: 'Failed to update Steam ID',
        validate: (response) => {
          if (!response?.success || !response.profile) {
            throw new Error(response?.message || 'Failed to update Steam ID');
          }
        },
        onSuccess: (response) => {
          this.updateProfile(response.profile);
        }
      });
      return response?.profile || null;
    },

    checkAuth() {
      return this.isLoggedIn && !!this.token && !!this.username;
    }
  }
});
