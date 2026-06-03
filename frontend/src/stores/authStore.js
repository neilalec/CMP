import { defineStore } from 'pinia';
import { useSocketStore } from './socketStore';
import { useRootStore } from './rootStore';
import { useLobbyStore } from './lobbyStore';
import { useQueueStore } from './queueStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { clearCurrentLobby } from '../utils/lobbyPersistence';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
    steamId: localStorage.getItem('steamId') || '',
    steamIdLocked: false,
    isLoggedIn: !!localStorage.getItem('token')
  }),

  getters: {
    hasSteamId: (state) => !!state.steamId
  },

  actions: {
    restoreAuth() {
      const token = localStorage.getItem('token');
      const username = localStorage.getItem('username');
      const steamId = localStorage.getItem('steamId') || '';
      
      if (token && username) {
        this.token = token;
        this.username = username;
        this.steamId = steamId;
        this.isLoggedIn = true;
        return true;
      }
      
      return false;
    },

    updateProfile(profile = {}) {
      this.steamId = profile.steam_id || '';
      this.steamIdLocked = !!profile.steam_id_locked;
      localStorage.setItem('steamId', this.steamId);
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
      const lobbyStore = useLobbyStore();
      const queueStore = useQueueStore();

      // Clear auth state
      this.token = null;
      this.username = null;
      this.isLoggedIn = false;
      this.steamId = '';
      this.steamIdLocked = false;

      // Clear localStorage auth data only
      localStorage.removeItem('token');
      localStorage.removeItem('username');
      localStorage.removeItem('steamId');
      clearCurrentLobby();
      lobbyStore.reset();
      queueStore.resetQueue();

      // Clear any errors
      const rootStore = useRootStore();
      rootStore.clearError();
    },

    async syncProfile() {
      if (!this.username) return null;
      const socketStore = useSocketStore();
      const response = await socketStore.emit(SOCKET_EVENTS.PROFILE.STATUS, {
        username: this.username
      });
      if (response?.success && response.profile) {
        this.updateProfile(response.profile);
        return response.profile;
      }
      throw new Error(response?.message || 'Failed to load profile');
    },

    async updateSteamId(steamId) {
      if (!this.username) {
        throw new Error('Not authenticated');
      }
      const socketStore = useSocketStore();
      const response = await socketStore.emit(SOCKET_EVENTS.PROFILE.UPDATE_STEAM_ID, {
        username: this.username,
        steam_id: steamId
      });
      if (response?.success && response.profile) {
        this.updateProfile(response.profile);
        return response.profile;
      }
      throw new Error(response?.message || 'Failed to update Steam ID');
    },

    checkAuth() {
      return this.isLoggedIn && !!this.token && !!this.username;
    }
  }
});
