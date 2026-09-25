import { computed, nextTick, reactive, ref } from 'vue';
import { mount } from '@vue/test-utils';
import WardogsGroup from '@/views/WardogsGroup.vue';
import { useGroupView } from '@/features/group/composables/useGroupView';
import { useQueueStore } from '@/stores/queueStore';

jest.mock('@/features/group/composables/useGroupView', () => ({ useGroupView: jest.fn() }));
jest.mock('@/stores/queueStore', () => ({ useQueueStore: jest.fn() }));

let groupStore;
let queueStore;
let authStore;
let actions;
const mountPage = () => mount(WardogsGroup);

beforeEach(() => {
  authStore = reactive({ username: 'alice', isAdmin: false });
  groupStore = reactive({ code: null, leader: null, members: [], playerProfiles: {}, loading: false, error: null,
    get inGroup() { return !!this.code; } });
  queueStore = reactive({ inQueue: false });
  actions = { handleCreate: jest.fn(), handleJoin: jest.fn(), handleLeave: jest.fn(),
    handleKickMember: jest.fn(), handleTransferOwnership: jest.fn(), handleSeedGroup: jest.fn() };
  useQueueStore.mockReturnValue(queueStore);
  useGroupView.mockReturnValue({ authStore, groupStore, ...actions,
    getMemberDisplayName: (id) => groupStore.playerProfiles[id]?.display_name || id,
    isGroupLeader: computed(() => groupStore.leader === authStore.username), joinCode: ref(''), seedCount: ref(1) });
});

test('no-group state is minimal and explains queue restrictions', async () => {
  const page = mountPage();
  expect(page.findAll('.cmp-surface')).toHaveLength(0);
  expect(page.get('h1').text()).toBe('Group');
  expect(page.get('button').text()).toBe('Create group');
  await page.get('button').trigger('click');
  expect(actions.handleCreate).toHaveBeenCalledTimes(1);
  await page.get('#wardogs-group-code').setValue('ABCD');
  await page.get('form').trigger('submit');
  expect(actions.handleJoin).toHaveBeenCalledTimes(1);
  queueStore.inQueue = true;
  await nextTick();
  expect(page.text()).toContain('Leave the queue from Play before creating or joining a group.');
  expect(page.get('button').attributes('disabled')).toBeDefined();
});

test('leader sees members, contextual controls, code copy, and leave', async () => {
  Object.assign(groupStore, { code: 'ABCD', leader: 'alice', members: ['alice', 'bob'],
    playerProfiles: { bob: { display_name: 'Bob Player' } } });
  const writeText = jest.fn().mockResolvedValue(undefined);
  Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  const page = mountPage();
  expect(page.text()).toContain('You control queueing.');
  expect(page.text()).toContain('Bob Player');
  expect(page.text()).toContain('Leader');
  await page.get('.group-code button').trigger('click');
  expect(writeText).toHaveBeenCalledWith('ABCD');
  expect(page.text()).toContain('Group code copied.');
  expect(page.get('.group-copy-feedback').attributes('role')).toBe('status');
  expect(page.get('.group-copy-feedback').classes()).toContain('cmp-status--success');
  await page.get('.group-member-actions button').trigger('click');
  expect(actions.handleTransferOwnership).toHaveBeenCalledWith('bob');
  await page.get('.group-member-actions .cmp-button--danger').trigger('click');
  expect(actions.handleKickMember).toHaveBeenCalledWith('bob');
  await page.get('.group-footer button').trigger('click');
  expect(actions.handleLeave).toHaveBeenCalledTimes(1);
});

test('group-code copy failures are announced as errors', async () => {
  Object.assign(groupStore, { code: 'ABCD', leader: 'alice', members: ['alice'] });
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: jest.fn().mockRejectedValue(new Error('denied')) }, configurable: true
  });
  const page = mountPage();
  await page.get('.group-code button').trigger('click');
  expect(page.get('.group-copy-feedback').attributes('role')).toBe('alert');
  expect(page.get('.group-copy-feedback').classes()).toContain('cmp-status--danger');
});

test('non-leader sees authority but cannot manage members', () => {
  Object.assign(groupStore, { code: 'ABCD', leader: 'bob', members: ['alice', 'bob'] });
  const page = mountPage();
  expect(page.text()).toContain('Leader controls queueing.');
  expect(page.text()).toContain('Member');
  expect(page.find('.group-member-actions').exists()).toBe(false);
  expect(page.find('.group-footer button').exists()).toBe(true);
});

test('queued group shows one matchmaking note and disables membership changes', async () => {
  Object.assign(groupStore, { code: 'ABCD', leader: 'alice', members: ['alice', 'bob'] });
  queueStore.inQueue = true;
  const page = mountPage();
  expect(page.text()).toContain('Group is queued. Manage matchmaking from Play.');
  expect(page.text()).not.toContain('You are in queue.');
  expect(page.find('.group-member-actions').exists()).toBe(true);
  expect(page.findAll('.group-member-actions button').every((button) => button.attributes('disabled') !== undefined)).toBe(true);
  expect(page.get('.group-footer button').attributes('disabled')).toBeUndefined();
  expect(page.text()).not.toContain('4/9');
});
