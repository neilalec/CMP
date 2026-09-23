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

  test('admin history and correction source use authenticated endpoints and surface stale conflicts', async () => {
    const request = jest.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ success: true, revisions: [{ revisionId: 'r1' }] }) })
      .mockResolvedValueOnce({ ok: false, json: async () => ({ success: false, code: 'stale_revision', currentRevisionId: 'r2', message: 'Reload history' }) });
    const source = createBackendWardogsDataSource({
      fetchImpl: request, apiBaseUrl: 'https://cmp.test/api', getToken: () => 'admin-token'
    });
    await expect(source.loadResultHistory('wd/a')).resolves.toEqual([{ revisionId: 'r1' }]);
    const correction = { expectedRevisionId: 'r1', correctionReason: 'Review',
      result: { status: 'void', scores: null, winnerFaction: null } };
    await expect(source.correctResult('wd/a', correction)).rejects.toMatchObject({
      code: 'stale_revision', currentRevisionId: 'r2', message: 'Reload history'
    });
    expect(request.mock.calls[0][0]).toBe('https://cmp.test/api/admin/wardogs/lobbies/wd%2Fa/result/history');
    expect(request.mock.calls[1][1]).toMatchObject({
      method: 'POST', headers: { Authorization: 'Bearer admin-token', 'Content-Type': 'application/json' },
      body: JSON.stringify(correction)
    });
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

  test('confirmation form is admin-only and requires explicit placement separate from observations', async () => {
    const match = normalizeBackendMatch(backendPayload());
    const hidden = mount(WardogsResultConfirmation, { props: { match, canConfirm: false } });
    expect(hidden.find('[aria-label="Confirm WARDOGS result"]').exists()).toBe(false);
    const wrapper = mount(WardogsResultConfirmation, { props: { match, canConfirm: true } });
    expect(wrapper.text()).toContain('Live scores are evidence only');
    expect(wrapper.findAll('input[type="number"]').map((input) => input.element.value)).toEqual(['999', '1', '0']);
    const placement = wrapper.findAll('select[required]');
    expect(placement).toHaveLength(3);
    await placement[0].setValue('1');
    await placement[1].setValue('2');
    await placement[2].setValue('3');
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('confirm')[0][0]).toMatchObject({
      status: 'completed_win', winnerFaction: 'valkyra',
      placementGroups: [['valkyra'], ['lonestar'], ['manticore']],
      scores: { valkyra: 999, lonestar: 1, manticore: 0 }
    });
  });

  test('tie, incomplete, and void confirmations are explicit and never select a winner', async () => {
    const match = normalizeBackendMatch(backendPayload());
    const wrapper = mount(WardogsResultConfirmation, { props: { match, canConfirm: true } });
    const scores = wrapper.findAll('input[type="number"]');
    await scores[1].setValue('999');
    await wrapper.find('select').setValue('tie');
    const placement = wrapper.findAll('select[required]');
    await placement[0].setValue('1');
    await placement[1].setValue('1');
    await placement[2].setValue('2');
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('confirm')[0][0]).toMatchObject({
      status: 'tie', winnerFaction: null,
      placementGroups: [['valkyra', 'lonestar'], ['manticore']]
    });
    await wrapper.find('select').setValue('incomplete');
    expect(wrapper.findAll('input[type="number"]')).toHaveLength(0);
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('confirm')[1][0]).toMatchObject({ status: 'incomplete', scores: null, winnerFaction: null });
    await wrapper.find('select').setValue('void');
    await wrapper.find('button').trigger('click');
    expect(wrapper.emitted('confirm')[2][0]).toMatchObject({ status: 'void', scores: null, winnerFaction: null });
  });

  test('confirmation accepts normal, tied-first, tied-second, and three-way-tied placements', async () => {
    const cases = [
      { status: 'completed_win', scores: ['10', '1', '5'], ranks: ['1', '3', '2'],
        groups: [['valkyra'], ['manticore'], ['lonestar']] },
      { status: 'tie', scores: ['10', '1', '10'], ranks: ['1', '2', '1'],
        groups: [['valkyra', 'manticore'], ['lonestar']] },
      { status: 'completed_win', scores: ['10', '5', '5'], ranks: ['1', '2', '2'],
        groups: [['valkyra'], ['lonestar', 'manticore']] },
      { status: 'tie', scores: ['10', '10', '10'], ranks: ['1', '1', '1'],
        groups: [['valkyra', 'lonestar', 'manticore']] }
    ];
    for (const item of cases) {
      const match = normalizeBackendMatch(backendPayload());
      const wrapper = mount(WardogsResultConfirmation, { props: { match, canConfirm: true } });
      await wrapper.find('select').setValue(item.status);
      for (const [index, score] of item.scores.entries()) {
        await wrapper.findAll('input[type="number"]')[index].setValue(score);
      }
      for (const [index, rank] of item.ranks.entries()) {
        await wrapper.findAll('select[required]')[index].setValue(rank);
      }
      await wrapper.findAll('button').find((button) => button.text().includes('Confirm authoritative result')).trigger('click');
      expect(wrapper.emitted('confirm')[0][0].placementGroups).toEqual(item.groups);
    }
  });

  test('divergent final scores warn and participants see a referee-confirmed result', async () => {
    const match = normalizeBackendMatch(backendPayload());
    const form = mount(WardogsResultConfirmation, { props: { match, canConfirm: true } });
    const scores = form.findAll('input[type="number"]');
    await scores[0].setValue('998');
    expect(form.text()).toContain('Submitted final scores differ from the latest observed server scores.');
    match.result = {
      status: 'tie', tied: true,
      placementGroups: [['valkyra', 'lonestar'], ['manticore']],
      scores: { valkyra: 8, lonestar: 8, manticore: 8 },
      confirmedAt: '2026-09-23T12:00:00Z'
    };
    const display = mount(WardogsResultConfirmation, { props: { match, canConfirm: false } });
    expect(display.text()).toContain('Referee confirmed result');
    expect(display.text()).toContain('AUTHORITATIVE');
    expect(display.text()).toContain('1st valkyra / lonestar');
    expect(display.text()).toContain('3rd manticore');
    expect(display.text()).toContain('valkyra: 8');
    expect(display.text()).not.toContain('confirmedBy');
  });

  test('participants see every authoritative placement and tied group', () => {
    const match = normalizeBackendMatch(backendPayload());
    const cases = [
      { status: 'completed_win', placementGroups: [['valkyra'], ['manticore'], ['lonestar']],
        expected: ['1st valkyra', '2nd manticore', '3rd lonestar'] },
      { status: 'tie', placementGroups: [['valkyra', 'manticore'], ['lonestar']],
        expected: ['1st valkyra / manticore', '3rd lonestar'] },
      { status: 'completed_win', placementGroups: [['valkyra'], ['manticore', 'lonestar']],
        expected: ['1st valkyra', '2nd manticore / lonestar'] },
      { status: 'tie', placementGroups: [['valkyra', 'lonestar', 'manticore']],
        expected: ['1st valkyra / lonestar / manticore'] }
    ];
    for (const { status, placementGroups, expected } of cases) {
      match.result = { status, placementGroups, scores: { valkyra: 9, lonestar: 4, manticore: 4 } };
      const display = mount(WardogsResultConfirmation, { props: { match, canConfirm: false } });
      for (const row of expected) expect(display.text()).toContain(row);
    }
  });

  test('admin can load revision history and correct the current revision with a reason', async () => {
    const match = normalizeBackendMatch(backendPayload());
    match.result = {
      status: 'completed_win', winnerFaction: 'valkyra', revisionNumber: 1,
      placementGroups: [['valkyra'], ['lonestar'], ['manticore']],
      scores: { valkyra: 90, lonestar: 20, manticore: 5 }, confirmedAt: '2026-09-23T12:00:00Z'
    };
    const history = [{ revisionId: 'wd:1', revisionNumber: 1, revisionType: 'confirmation',
      status: 'completed_win', actorId: 'admin', authoritative: true, scores: match.result.scores,
      placementGroups: match.result.placementGroups,
      observation: { available: true, observedAt: '2026-09-23T11:59:00Z', differsFromObservation: false } }];
    const wrapper = mount(WardogsResultConfirmation, { props: {
      match, canConfirm: true, resultHistory: history
    } });
    expect(wrapper.text()).toContain('Result revision history');
    expect(wrapper.text()).toContain('Original confirmation');
    expect(wrapper.text()).toContain('CURRENT AUTHORITATIVE');
    expect(wrapper.find('button').text()).toBe('Correct result');
    await wrapper.find('button').trigger('click');
    expect(wrapper.text()).toContain('A new immutable revision will supersede the current result.');
    expect(wrapper.findAll('input[type="number"]').map((input) => input.element.value)).toEqual(['90', '20', '5']);
    expect(wrapper.findAll('select[required]').map((select) => select.element.value)).toEqual(['1', '2', '3']);
    expect(wrapper.text()).toContain('valkyra: 999');
    await wrapper.findAll('button').find((button) => button.text().includes('Use latest observed scores')).trigger('click');
    expect(wrapper.findAll('input[type="number"]').map((input) => input.element.value)).toEqual(['999', '1', '0']);
    await wrapper.find('textarea[required]').setValue('Referee entered the wrong score.');
    await wrapper.findAll('input[type="number"]')[0].setValue('80');
    await wrapper.findAll('button').find((button) => button.text().includes('Confirm new revision')).trigger('click');
    expect(wrapper.emitted('correct')[0][0]).toMatchObject({
      expectedRevisionId: 'wd:1', correctionReason: 'Referee entered the wrong score.',
      result: { status: 'completed_win', winnerFaction: 'valkyra',
        placementGroups: [['valkyra'], ['lonestar'], ['manticore']],
        scores: { valkyra: 80, lonestar: 1, manticore: 0 } }
    });
  });

  test('admin sees a stale history warning and correction reason is mandatory', async () => {
    const match = normalizeBackendMatch(backendPayload());
    match.result = { status: 'tie', revisionNumber: 2, scores: { valkyra: 8, lonestar: 8, manticore: 3 } };
    const wrapper = mount(WardogsResultConfirmation, { props: {
      match, canConfirm: true, historyError: 'The result changed while this form was open.',
      resultHistory: [{ revisionId: 'wd:2', revisionNumber: 2, authoritative: true }]
    } });
    expect(wrapper.text()).toContain('The result changed while this form was open.');
    await wrapper.find('button').trigger('click');
    const submit = wrapper.findAll('button').find((button) => button.text().includes('Confirm new revision'));
    expect(submit.element.disabled).toBe(true);
    expect(wrapper.find('textarea[required]').exists()).toBe(true);
  });

  test('rejects malformed payload and missing token before network access', async () => {
    expect(() => normalizeBackendMatch({ success: true, match: { factions: [] } })).toThrow();
    const request = jest.fn();
    const source = createBackendWardogsDataSource({ fetchImpl: request, getToken: () => null });
    await expect(source.loadMatch('wd-api')).rejects.toThrow('Sign in');
    expect(request).not.toHaveBeenCalled();
  });
});
