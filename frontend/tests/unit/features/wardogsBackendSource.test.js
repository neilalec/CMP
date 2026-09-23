import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';
import { createBackendWardogsDataSource, normalizeBackendMatch } from '../../../src/features/wardogs/api/backendDataSource';
import { mockWardogsDataSource } from '../../../src/features/wardogs/mock/mockDataSource';
import { useWardogsMatchStore } from '../../../src/features/wardogs/stores/matchStore';
import FactionRoster from '../../../src/features/wardogs/components/FactionRoster.vue';
import { factionSummary, resultRows } from '../../../src/features/wardogs/models/match';

const backendPayload = () => ({
  success: true,
  match: {
    id: 'wd-api', phase: 'assembling', label: 'Practice',
    server: { state: 'fresh', label: 'Server observed' },
    observation: { state: 'fresh', observedAt: '2026-09-23T12:00:00Z' },
    configuration: { map: 'Bakurani' },
    factions: ['valkyra', 'lonestar', 'manticore'].map((id, index) => ({
      id, name: id, color: '#123456', commanderId: index === 0 ? 'alice' : null,
      groups: index === 0 ? [{
        id: 'group-a', name: 'A Team', type: 'squad', leaderId: 'alice',
        players: [
          { id: 'alice', displayName: 'Alice', steamId: '76561198000000001',
            rosterStatus: 'active', registered: true, ready: false, connected: true,
            observedFactionId: 'lonestar', alignmentState: 'mismatch' },
          { id: 'bob', displayName: 'Bob', steamId: '76561198000000002',
            rosterStatus: 'reserve', registered: true, ready: true, connected: null,
            observedFactionId: null, alignmentState: 'unknown' }
        ]
      }] : []
    })),
    scores: { valkyra: 999, lonestar: 1, manticore: 0 },
    unexpectedPlayers: [{ displayName: 'Stranger', steamId: '76561198000000099' }]
  }
});

describe('WARDOGS backend data source', () => {
  beforeEach(() => setActivePinia(createPinia()));

  test('normalizes backend payload into the existing grouped domain without result inference', () => {
    const match = normalizeBackendMatch(backendPayload());
    expect(match.serverId).toBeNull();
    expect(match.factions).toHaveLength(3);
    expect(match.factions[0].commanderId).toBe('alice');
    expect(match.factions[0].groups[0]).toMatchObject({ type: 'squad', leaderId: 'alice' });
    expect(match.factions[0].groups[0].players[0]).toMatchObject({
      connected: true, ready: false, observedFactionId: 'lonestar', rosterStatus: 'active'
    });
    expect(match.factions[0].groups[0].players[1]).toMatchObject({
      connected: null, ready: true, rosterStatus: 'reserve'
    });
    expect(match.unexpectedPlayers).toHaveLength(1);
    expect(resultRows(match)).toEqual([]);
    expect(factionSummary(match.factions[0])).toMatchObject({ active: 1, reserves: 1, connected: 1, ready: 0, aligned: 0 });
  });

  test('preserves an unclassified premade group without relabeling it', () => {
    const payload = backendPayload();
    payload.match.factions[0].groups[0].type = 'premade';
    payload.match.factions[0].groups[0].name = 'Premade';
    const match = normalizeBackendMatch(payload);
    expect(match.factions[0].groups[0].type).toBe('premade');
    const faction = match.factions[0];
    const wrapper = mount(FactionRoster, { props: { faction, summary: factionSummary(faction) } });
    expect(wrapper.text()).toContain('premade');
  });

  test('store loads backend with bearer auth and mock scenarios remain available', async () => {
    const request = jest.fn().mockResolvedValue({ ok: true, json: async () => backendPayload() });
    const source = createBackendWardogsDataSource({
      fetchImpl: request, apiBaseUrl: 'https://cmp.test/api', getToken: () => 'offline-token'
    });
    const store = useWardogsMatchStore();
    await store.loadBackendLobby('wd-api', source);
    expect(store.mode).toBe('backend');
    expect(store.match.id).toBe('wd-api');
    expect(request).toHaveBeenCalledWith('https://cmp.test/api/wardogs/lobbies/wd-api', {
      headers: { Authorization: 'Bearer offline-token' }
    });
    await store.selectScenario('reserves', mockWardogsDataSource);
    expect(store.mode).toBe('mock');
    expect(store.match.source).toBe('local-mock');
  });

  test('faction display distinguishes mismatch, unknown presence, and explicit waiting', () => {
    const match = normalizeBackendMatch(backendPayload());
    const faction = match.factions[0];
    const wrapper = mount(FactionRoster, { props: { faction, summary: factionSummary(faction) } });
    expect(wrapper.text()).toContain('Faction mismatch');
    expect(wrapper.text()).toContain('Connection unknown');
    expect(wrapper.text()).toContain('Waiting');
    expect(wrapper.text()).toContain('Group leader');
  });

  test('rejects malformed payload and missing token before network access', async () => {
    expect(() => normalizeBackendMatch({ success: true, match: { factions: [] } })).toThrow();
    const request = jest.fn();
    const source = createBackendWardogsDataSource({ fetchImpl: request, getToken: () => null });
    await expect(source.loadMatch('wd-api')).rejects.toThrow('Sign in');
    expect(request).not.toHaveBeenCalled();
  });
});
