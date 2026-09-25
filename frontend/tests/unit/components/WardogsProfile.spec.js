import { reactive, ref } from 'vue';
import { flushPromises, mount } from '@vue/test-utils';
import Profile from '@/views/Profile.vue';
import { useProfileView } from '@/features/profile/composables/useProfileView';

jest.mock('@/features/profile/composables/useProfileView', () => ({ useProfileView: jest.fn() }));

let authStore;
let displayName;
let handleLogout;
const response = (matches, ok = true) => ({ ok, json: async () => ({ success: ok, matches }) });
const mountPage = () => mount(Profile, { global: { stubs: {
  RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' }
} } });

beforeEach(() => {
  authStore = reactive({ token: 'test-token', playerName: 'Alice', isAdmin: false,
    updateDisplayName: jest.fn().mockResolvedValue({ display_name: 'New Alice' }) });
  displayName = ref('Alice');
  handleLogout = jest.fn();
  useProfileView.mockReturnValue({ authStore, displayName, handleLogout,
    hasSteamId: ref(true), steamId: ref('76561198000000001') });
});

test('shows a backend history rating as the latest rated match, not legacy Elo', async () => {
  global.fetch = jest.fn().mockResolvedValue(response([
    { rating: null }, { rating: { after: 1036, delta: 18 } }
  ]));
  const page = mountPage();
  await flushPromises();
  expect(page.text()).toContain('1036');
  expect(page.text()).toContain('After your latest rated match');
  expect(page.text()).not.toContain('Elo');
  expect(page.get('a[href="/group"]').text()).toBe('Open group');
  expect(global.fetch.mock.calls[0][1].headers.Authorization).toBe('Bearer test-token');
});

test('handles missing or unavailable rating history without inventing a rating', async () => {
  global.fetch = jest.fn().mockResolvedValue(response([]));
  const empty = mountPage();
  await flushPromises();
  expect(empty.text()).toContain('No recent rating entry.');
  empty.unmount();
  global.fetch = jest.fn().mockRejectedValue(new Error('network'));
  const failed = mountPage();
  await flushPromises();
  expect(failed.get('[role="alert"]').text()).toContain('WARDOGS rating history is unavailable.');
});

test('display-name editing reports validation, saving, success and failure', async () => {
  global.fetch = jest.fn().mockResolvedValue(response([]));
  const page = mountPage();
  await flushPromises();
  await page.get('#profile-display-name').setValue('');
  await page.get('form').trigger('submit');
  expect(page.get('[role="alert"]').text()).toBe('Enter a display name.');
  await page.get('#profile-display-name').setValue('New Alice');
  await page.get('form').trigger('submit');
  await flushPromises();
  expect(authStore.updateDisplayName).toHaveBeenCalledWith('New Alice');
  expect(page.get('[role="status"]').text()).toBe('Display name saved.');
  authStore.updateDisplayName.mockRejectedValue(new Error('Name unavailable'));
  await page.get('#profile-display-name').setValue('Another');
  await page.get('form').trigger('submit');
  await flushPromises();
  expect(page.get('[role="alert"]').text()).toBe('Name unavailable');
  await page.get('.profile-logout').trigger('click');
  expect(handleLogout).toHaveBeenCalledTimes(1);
});
