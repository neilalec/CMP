import { mount } from '@vue/test-utils';
import QueuePanel from '@/features/home/components/QueuePanel.vue';

const queueModes = [
  {
    id: 'skirmish',
    label: 'Skirmish',
    shortLabel: 'Skirmish',
    teamSize: 20,
    maxPlayers: 40,
    playersInQueue: 5
  },
  {
    id: 'hotdrop',
    label: 'Hotdrop',
    shortLabel: 'Hotdrop',
    teamSize: 30,
    maxPlayers: 60,
    playersInQueue: 0
  }
];

const mountQueuePanel = (props = {}) => mount(QueuePanel, {
  props: {
    queueModes,
    currentQueueMode: null,
    inQueue: false,
    matchAcceptActive: false,
    loading: false,
    isInLobby: false,
    isInGroup: false,
    isGroupLeader: false,
    hasSteamId: true,
    groupMemberCount: 1,
    canManageQueueTools: false,
    serverAvailable: true,
    getQueueProgressPercent: jest.fn((modeId) => modeId === 'skirmish' ? 12.5 : 0),
    isModeQueueFull: jest.fn(() => false),
    ...props
  }
});

describe('QueuePanel.vue', () => {
  test('renders the current queue modes', () => {
    const wrapper = mountQueuePanel();

    expect(wrapper.text()).toContain('Skirmish');
    expect(wrapper.text()).toContain('Hotdrop');
    expect(wrapper.text()).toContain('20v20');
    expect(wrapper.text()).toContain('30v30');
    expect(wrapper.text()).toContain('5/40');
  });

  test('emits join-queue for the selected mode', async () => {
    const wrapper = mountQueuePanel();

    await wrapper.find('.queue-action').trigger('click');

    expect(wrapper.emitted('join-queue')).toEqual([['skirmish']]);
  });

  test('emits leave-queue when already queued for the mode', async () => {
    const wrapper = mountQueuePanel({
      inQueue: true,
      currentQueueMode: 'skirmish'
    });

    await wrapper.find('.queue-action').trigger('click');

    expect(wrapper.emitted('leave-queue')).toEqual([['skirmish']]);
  });

  test('shows admin queue tools only when allowed', () => {
    const normalWrapper = mountQueuePanel();
    const adminWrapper = mountQueuePanel({ canManageQueueTools: true });

    expect(normalWrapper.find('.queue-dev-actions').exists()).toBe(false);
    expect(adminWrapper.find('.queue-dev-actions').exists()).toBe(true);
  });

  test('disables joining when the only server is busy', () => {
    const wrapper = mountQueuePanel({ serverAvailable: false });

    expect(wrapper.text()).toContain('Server busy');
    expect(wrapper.find('.queue-action').attributes('disabled')).toBeDefined();
  });
});
