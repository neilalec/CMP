import { createPinia, setActivePinia } from 'pinia';
import { mount, flushPromises } from '@vue/test-utils';
import { nextTick } from 'vue';
import Matches from '@/views/Matches.vue';
import { useAuthStore } from '@/stores/authStore';
import { buildRoutes } from '@/router';

const response = (body, ok = true) => ({ ok, json: async () => body });
const row = (outcome, options = {}) => ({
  lobbyId: `match-${outcome}`, factionId: 'valkyra', rosterStatus: 'active',
  matchAt: '2026-09-24T12:00:00Z', rating: null,
  result: { status: outcome === 'win' || outcome === 'loss' ? 'completed_win' : outcome,
    outcome, placement: outcome === 'win' ? 1 : outcome === 'loss' ? 3 : null,
    placementGroups: outcome === 'win' ? [['valkyra'], ['lonestar'], ['manticore']] : null,
    corrected: false, revisionNumber: 1 }, ...options
});
const mountPage = () => mount(Matches, { global: {
  stubs: { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }
} });

describe('WARDOGS Matches page', () => {
  beforeEach(() => {
    localStorage.clear();
    setActivePinia(createPinia());
    useAuthStore().token = 'test-token';
  });
  afterEach(() => { jest.restoreAllMocks(); });

  test('has compact no-current and no-confirmed-history states', async () => {
    let finishCurrent;
    let finishHistory;
    global.fetch = jest.fn((url) => new Promise((resolve) => {
      if (url.includes('/current')) finishCurrent = resolve;
      else finishHistory = resolve;
    }));
    const wrapper = mountPage();
    await nextTick();
    expect(wrapper.text()).toContain('Checking your current match');
    expect(wrapper.text()).toContain('Loading match history');
    finishCurrent(response({ success: true, match: null }));
    finishHistory(response({ success: true, matches: [] }));
    await flushPromises();
    expect(wrapper.text()).toContain('No current WARDOGS match');
    expect(wrapper.text()).toContain('No referee-confirmed WARDOGS matches yet');
    expect(wrapper.text()).not.toContain('Win');
  });

  test('shows a current match even when history fails, with a history retry', async () => {
    let historyFails = true;
    global.fetch = jest.fn((url) => url.includes('/current')
      ? Promise.resolve(response({ success: true, match: { lobbyId: 'wd-current',
        factionId: 'manticore', rosterStatus: 'reserve', state: 'waiting_for_server' } }))
      : historyFails ? Promise.reject(new Error('History unavailable'))
        : Promise.resolve(response({ success: true, matches: [] })));
    const wrapper = mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain('Waiting for server');
    expect(wrapper.text()).toContain('Manticore · Reserve');
    expect(wrapper.find('a[href="/wardogs/lobby/wd-current"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('History unavailable');
    historyFails = false;
    await wrapper.findAll('button').find((button) => button.text() === 'Retry').trigger('click');
    await flushPromises();
    expect(wrapper.text()).toContain('No referee-confirmed WARDOGS matches yet');
  });

  test('renders only supplied authoritative outcomes and replayed rating values', async () => {
    const matches = ['win', 'loss', 'tie', 'incomplete', 'void'].map((outcome) => row(outcome));
    matches[0].rating = { before: 1000, delta: 24, after: 1024 };
    matches[0].result.corrected = true;
    matches[0].result.revisionNumber = 2;
    global.fetch = jest.fn((url) => Promise.resolve(response(
      url.includes('/current') ? { success: true, match: null } : { success: true, matches }
    )));
    const wrapper = mountPage();
    await flushPromises();
    const text = wrapper.text();
    for (const label of ['Win', 'Loss', 'Tie', 'Incomplete', 'Void']) expect(text).toContain(label);
    expect(text).toContain('+24 → 1024');
    expect(text).toContain('Corrected · revision 2');
    expect(text).toContain('1st Valkyra · 2nd Lonestar · 3rd Manticore');
    expect(text).not.toContain('Observed score');
    expect(wrapper.findAll('.matches-row')).toHaveLength(5);
    expect(wrapper.find('.matches-row.is-win .matches-row-result strong').text()).toBe('Win');
    expect(wrapper.find('.matches-row.is-unrated .matches-row-rating strong').text()).toBe('No rating entry');
  });

  test('a current-match failure does not hide valid history, including a zero rating change', async () => {
    global.fetch = jest.fn((url) => url.includes('/current')
      ? Promise.reject(new Error('Current unavailable'))
      : Promise.resolve(response({ success: true, matches: [row('tie', {
        rating: { before: 1000, delta: 0, after: 1000 }
      })] })));
    const wrapper = mountPage();
    await flushPromises();
    expect(wrapper.text()).toContain('Current unavailable');
    expect(wrapper.text()).toContain('Tie');
    expect(wrapper.text()).toContain('0 → 1000');
    expect(wrapper.find('.matches-row').exists()).toBe(true);
  });

  test('Squad routes retain Results and have no WARDOGS Matches route', () => {
    const squad = buildRoutes('squad');
    expect(squad.some((route) => route.name === 'results')).toBe(true);
    expect(squad.some((route) => route.name === 'matches')).toBe(false);
  });
});
