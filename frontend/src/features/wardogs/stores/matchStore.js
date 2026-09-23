import { defineStore } from 'pinia';
import { mockWardogsDataSource } from '../mock/mockDataSource';
import { factionSummary, matchSummary, resultRows } from '../models/match';

export const useWardogsMatchStore = defineStore('wardogs-match', {
  state: () => ({ scenarioKey: 'partial', mode: 'mock', match: null, loading: false,
    refreshing: false, error: null }),
  getters: {
    scenarioOptions: () => mockWardogsDataSource.listScenarios(),
    totals: (state) => state.match ? matchSummary(state.match) : null,
    factionSummaries: (state) => state.match ? Object.fromEntries(
      state.match.factions.map((faction) => [faction.id, factionSummary(faction)])
    ) : {},
    rankedResults: (state) => state.match ? resultRows(state.match) : []
  },
  actions: {
    async selectScenario(key, source = mockWardogsDataSource) {
      this.loading = true;
      this.error = null;
      try {
        this.match = await source.loadScenario(key);
        this.scenarioKey = key;
        this.mode = 'mock';
      } catch (error) {
        this.error = error.message;
      } finally {
        this.loading = false;
      }
    },
    async loadBackendLobby(lobbyId, source) {
      this.loading = true;
      this.error = null;
      this.match = null;
      this.mode = 'backend';
      try {
        this.match = await source.loadMatch(lobbyId);
      } catch (error) {
        this.error = error.message;
      } finally {
        this.loading = false;
      }
    },
    async refreshBackendLobby(lobbyId, source) {
      if (this.mode !== 'backend' || this.match?.id !== lobbyId || this.refreshing) return;
      this.refreshing = true;
      try {
        this.match = await source.loadMatch(lobbyId);
        this.error = null;
      } catch {
        // Keep the last useful read visible through a temporary HTTP failure.
        this.error = 'Live update unavailable. Showing the last loaded lobby state.';
      } finally {
        this.refreshing = false;
      }
    },
    async confirmBackendResult(lobbyId, submission, source) {
      if (this.mode !== 'backend' || this.match?.id !== lobbyId) return false;
      this.error = null;
      try {
        await source.confirmResult(lobbyId, submission);
        await this.refreshBackendLobby(lobbyId, source);
        return true;
      } catch (error) {
        this.error = error.message || 'Result confirmation failed';
        return false;
      }
    }
  }
});
