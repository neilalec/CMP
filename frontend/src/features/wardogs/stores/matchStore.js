import { defineStore } from 'pinia';
import { mockWardogsDataSource } from '../mock/mockDataSource';
import { factionSummary, matchSummary, resultRows } from '../models/match';

export const useWardogsMatchStore = defineStore('wardogs-match', {
  state: () => ({ scenarioKey: 'partial', mode: 'mock', match: null, loading: false, error: null }),
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
    }
  }
});
