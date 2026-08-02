import { defineStore } from 'pinia';
import { useRootStore } from './rootStore';
import { SOCKET_EVENTS } from '../constants/socketEvents';
import { runStoreSocketAction } from './helpers/storeSocketAction';

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || null,
    username: localStorage.getItem('username') || null,
    displayName: localStorage.getItem('displayName') || localStorage.getItem('username') || null,
    steamId: localStorage.getItem('steamId') || '',
    steamPersonaName: localStorage.getItem('steamPersonaName') || '',
    displayNameSource: localStorage.getItem('displayNameSource') || 'legacy',
    steamIdLocked: false,
    isAdmin: localStorage.getItem('isAdmin') === 'true',
    canToggleAdmin: localStorage.getItem('canToggleAdmin') === 'true',
    adminTestModeDisabled: localStorage.getItem('adminTestModeDisabled') === 'true',
    isLoggedIn: !!localStorage.getItem('token')
  }),

  getters: {
    hasSteamId: (state) => !!state.steamId,
    playerName: (state) => state.displayName || state.username
  },

  actions: {
    clearAuthState() {
      this.token = null;
      this.username = null;
      this.displayName = null;
      this.isLoggedIn = false;
      this.steamId = '';
      this.steamPersonaName = '';
      this.displayNameSource = 'legacy';
      this.steamIdLocked = false;
      this.isAdmin = false;
      this.canToggleAdmin = false;
      this.adminTestModeDisabled = false;
    },

    clearPersistedAuth() {
      localStorage.removeItem('token');
      localStorage.removeItem('username');
      localStorage.removeItem('displayName');
      localStorage.removeItem('steamId');
      localStorage.removeItem('steamPersonaName');
      localStorage.removeItem('displayNameSource');
      localStorage.removeItem('isAdmin');
      localStorage.removeItem('canToggleAdmin');
      localStorage.removeItem('adminTestModeDisabled');
    },

    restoreAuth() {
      const token = localStorage.getItem('token');
      const username = localStorage.getItem('username');
      const displayName = localStorage.getItem('displayName') || username;
      const steamId = localStorage.getItem('steamId') || '';
      const steamPersonaName = localStorage.getItem('steamPersonaName') || '';
      const displayNameSource = localStorage.getItem('displayNameSource') || 'legacy';
      const isAdmin = localStorage.getItem('isAdmin') === 'true';
      const canToggleAdmin = localStorage.getItem('canToggleAdmin') === 'true';
      const adminTestModeDisabled = localStorage.getItem('adminTestModeDisabled') === 'true';
      
      if (token && username) {
        this.token = token;
        this.username = username;
        this.displayName = displayName;
        this.steamId = steamId;
        this.steamPersonaName = steamPersonaName;
        this.displayNameSource = displayNameSource;
        this.isAdmin = isAdmin;
        this.canToggleAdmin = canToggleAdmin;
        this.adminTestModeDisabled = adminTestModeDisabled;
        this.isLoggedIn = true;
        return true;
      }
      
      return false;
    },

    updateProfile(profile = {}) {
      this.displayName = profile.display_name || this.username || '';
      this.steamPersonaName = profile.steam_persona_name || '';
      this.displayNameSource = profile.display_name_source || 'legacy';
      this.steamId = profile.steam_id || '';
      this.steamIdLocked = !!profile.steam_id_locked;
      this.isAdmin = !!profile.is_admin;
      this.canToggleAdmin = !!profile.can_toggle_admin;
      this.adminTestModeDisabled = !!profile.admin_test_mode_disabled;
      localStorage.setItem('displayName', this.displayName);
      localStorage.setItem('steamPersonaName', this.steamPersonaName);
      localStorage.setItem('displayNameSource', this.displayNameSource);
      localStorage.setItem('steamId', this.steamId);
      localStorage.setItem('isAdmin', String(this.isAdmin));
      localStorage.setItem('canToggleAdmin', String(this.canToggleAdmin));
      localStorage.setItem('adminTestModeDisabled', String(this.adminTestModeDisabled));
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

    async updateDisplayName(displayName) {
      if (!this.username) {
        throw new Error('Not authenticated');
      }
      const response = await runStoreSocketAction(this, {
        event: SOCKET_EVENTS.PROFILE.UPDATE_DISPLAY_NAME,
        payload: {
          username: this.username,
          display_name: displayName
        },
        setLoading: false,
        fallbackMessage: 'Failed to update display name',
        validate: (response) => {
          if (!response?.success || !response.profile) {
            throw new Error(response?.message || 'Failed to update display name');
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
