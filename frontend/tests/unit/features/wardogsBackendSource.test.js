import { createPinia, setActivePinia } from 'pinia';
import { mount } from '@vue/test-utils';
import { createBackendWardogsDataSource, normalizeBackendMatch } from '../../../src/features/wardogs/api/backendDataSource';
import { mockWardogsDataSource } from '../../../src/features/wardogs/mock/mockDataSource';
import { useWardogsMatchStore } from '../../../src/features/wardogs/stores/matchStore';
import FactionRoster from '../../../src/features/wardogs/components/FactionRoster.vue';
import MatchOverview from '../../../src/features/wardogs/components/MatchOverview.vue';
import ScoreAndResults from '../../../src/features/wardogs/components/ScoreAndResults.vue';
import WardogsResultConfirmation from '../../../src/features/wardogs/components/WardogsResultConfirmation.vue';
import { factionSummary, matchSummary, resultRows } from '../../../src/features/wardogs/models/match';

const backendPayload = () => ({
  success: true,
  match: {
    id: 'wd-api', phase: 'assembling', label: 'Practice',
    server: { state: 'fresh', name: 'Observed WARDOGS server', label: 'Server observed' },
    observation: { state: 'fresh', pollState: 'ok', observedAt: '2026-09-23T12:00:00Z' },
    configuration: { map: 'Bakurani' },
    serverStatus: { currentPlayers: 3, maxPlayers: 100 },
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
    expect(match.join.state).toBe('waiting_for_server');
    expect(match.join.directJoinUrl).toBeNull();
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

  test('normalizes only the manual Join By ID fields', () => {
    const payload = backendPayload();
    payload.match.serverId = 7;
    payload.match.join = {
      state: 'manual_join_available', serverName: 'Observed server',
      joinId: 'dynamic-id-for-test',
      instructions: ['Open WARDOGS.', 'Choose Join By ID.', 'Enter the Join ID.',
        'Select Lookup.', 'Join the resolved server.'],
      directJoinUrl: null, adminMetadata: 'must not reach the component'
    };
    const match = normalizeBackendMatch(payload);
    expect(match.join).toEqual({
      state: 'manual_join_available', serverName: 'Observed server',
      joinId: 'dynamic-id-for-test',
      instructions: ['Open WARDOGS.', 'Choose Join By ID.', 'Enter the Join ID.',
        'Select Lookup.', 'Join the resolved server.'],
      directJoinUrl: null
    });
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

  test('live backend view shows server, planned mismatch, scores and unexpected players', () => {
    const match = normalizeBackendMatch(backendPayload());
    const overview = mount(MatchOverview, { props: { match, totals: matchSummary(match) } });
    expect(overview.text()).toContain('Observed WARDOGS server');
    expect(overview.text()).toContain('Bakurani');
    expect(overview.text()).toContain('3/100');
    const faction = match.factions[0];
    const roster = mount(FactionRoster, { props: {
      faction, summary: factionSummary(faction), observationState: match.observation.state
    } });
    expect(roster.text()).toContain('Faction mismatch');
    expect(roster.text()).toContain('Connected');
    const scores = mount(ScoreAndResults, { props: {
      match, summaries: Object.fromEntries(match.factions.map((item) =>
        [item.id, factionSummary(item)])), rankedResults: resultRows(match)
    } });
    expect(scores.text()).toContain('Live server scores');
    expect(scores.text()).toContain('999');
    expect(scores.text()).toContain('Unexpected server players');
    expect(scores.text()).toContain('Stranger');
    expect(scores.text()).toContain('not official results');
    expect(scores.text()).not.toContain('Sample player statistics');
  });

  test('stale read keeps last known view with an explicit warning', () => {
    const payload = backendPayload();
    payload.match.server.state = 'stale';
    payload.match.server.label = 'Last server observation may be stale';
    payload.match.observation.state = 'stale';
    payload.match.observation.pollState = 'error';
    const match = normalizeBackendMatch(payload);
    const overview = mount(MatchOverview, { props: { match, totals: matchSummary(match) } });
    expect(overview.text()).toContain('Latest read unavailable');
    const faction = match.factions[0];
    const roster = mount(FactionRoster, { props: {
      faction, summary: factionSummary(faction), observationState: 'stale'
    } });
    expect(roster.text()).toContain('Last seen connected');
    const scores = mount(ScoreAndResults, { props: {
      match, summaries: Object.fromEntries(match.factions.map((item) =>
        [item.id, factionSummary(item)])), rankedResults: []
    } });
    expect(scores.text()).toContain('Last known server scores');
    expect(scores.text()).toContain('999');
  });

  test('socket-triggered refresh replaces the match and keeps last state on HTTP failure', async () => {
    const store = useWardogsMatchStore();
    const payload = backendPayload();
    let fail = false;
    const source = { loadMatch: jest.fn(async () => {
      if (fail) throw new Error('offline-secret');
      return normalizeBackendMatch(payload);
    }) };
    await store.loadBackendLobby('wd-api', source);
    payload.match.configuration.map = 'Next map';
    await store.refreshBackendLobby('wd-api', source);
    expect(store.match.configuration.map).toBe('Next map');
    fail = true;
    await store.refreshBackendLobby('wd-api', source);
    expect(store.match.configuration.map).toBe('Next map');
    expect(store.error).toContain('last loaded lobby state');
    expect(store.error).not.toContain('offline-secret');
  });

  test('confirmation form is admin-only and prefills observed values with explicit winner choice', async () => {
    const match = normalizeBackendMatch(backendPayload());
    const hidden = mount(WardogsResultConfirmation, { props: { match, canConfirm: false } });
    expect(hidden.find('[aria-label="Confirm WARDOGS result"]').exists()).toBe(false);
    const wrapper = mount(WardogsResultConfirmation, { props: { match, canConfirm: true } });
    expect(wrapper.text()).toContain('Live scores are evidence only');
    expect(wrapper.findAll('input[type="number"]').map((input) => input.element.value)).toEqual(['999', '1', '0']);
    expect(wrapper.find('select[required]').exists()).toBe(true);
    await wrapper.find('select[required]').setValue('valkyra');
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('confirm')[0][0]).toMatchObject({
      status: 'completed_win', winnerFaction: 'valkyra',
      scores: { valkyra: 999, lonestar: 1, manticore: 0 }
    });
  });

  test('tie, incomplete, and void confirmations are explicit and never select a winner', async () => {
    const match = normalizeBackendMatch(backendPayload());
    const wrapper = mount(WardogsResultConfirmation, { props: { match, canConfirm: true } });
    const scores = wrapper.findAll('input[type="number"]');
    await scores[1].setValue('999');
    await wrapper.find('select').setValue('tie');
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('confirm')[0][0]).toMatchObject({ status: 'tie', winnerFaction: null });
    await wrapper.find('select').setValue('incomplete');
    expect(wrapper.findAll('input[type="number"]')).toHaveLength(0);
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('confirm')[1][0]).toMatchObject({ status: 'incomplete', scores: null, winnerFaction: null });
    await wrapper.find('select').setValue('void');
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('confirm')[2][0]).toMatchObject({ status: 'void', scores: null, winnerFaction: null });
  });

  test('divergent final scores warn and participants see a referee-confirmed result', async () => {
    const match = normalizeBackendMatch(backendPayload());
    const form = mount(WardogsResultConfirmation, { props: { match, canConfirm: true } });
    const scores = form.findAll('input[type="number"]');
    await scores[0].setValue('998');
    expect(form.text()).toContain('Submitted final scores differ from the latest observed server scores.');
    match.result = {
      status: 'tie', tied: true,
      scores: { valkyra: 8, lonestar: 8, manticore: 8 },
      confirmedAt: '2026-09-23T12:00:00Z'
    };
    const display = mount(WardogsResultConfirmation, { props: { match, canConfirm: false } });
    expect(display.text()).toContain('Referee confirmed result');
    expect(display.text()).toContain('AUTHORITATIVE');
    expect(display.text()).toContain('The referee confirmed a tie.');
    expect(display.text()).toContain('valkyra: 8');
    expect(display.text()).not.toContain('confirmedBy');
  });

  test('rejects malformed payload and missing token before network access', async () => {
    expect(() => normalizeBackendMatch({ success: true, match: { factions: [] } })).toThrow();
    const request = jest.fn();
    const source = createBackendWardogsDataSource({ fetchImpl: request, getToken: () => null });
    await expect(source.loadMatch('wd-api')).rejects.toThrow('Sign in');
    expect(request).not.toHaveBeenCalled();
  });
});
