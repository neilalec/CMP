import { mount } from '@vue/test-utils';
import QueuePanel from '@/features/home/components/QueuePanel.vue';

const queueModes = [
  {
    id: 'skirmish',
    label: '20v20 Skirmish Layers',
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
  },
  {
    id: 's30',
    label: 'S3O',
    shortLabel: 'S3O',
    teamSize: 36,
    maxPlayers: 72,
    playersInQueue: 0
  },
  {
    id: 'rivals36',
    label: '36v36 Squad Rivals',
    shortLabel: 'Rivals',
    teamSize: 36,
    maxPlayers: 72,
    playersInQueue: 0
  },
  {
    id: 'osi40',
    label: '40v40 Offworld Squad Invitational',
    shortLabel: 'OSI',
    teamSize: 40,
    maxPlayers: 80,
    playersInQueue: 0
  },
  {
    id: 'ocbt15',
    label: '15v15 Open Clan Battle',
    shortLabel: 'OCBT',
    teamSize: 15,
    maxPlayers: 30,
    playersInQueue: 0
  },
  {
    id: 'balt26',
    label: '26v26 Balt Layers',
    shortLabel: 'BALT',
    teamSize: 26,
    maxPlayers: 52,
    playersInQueue: 0
  },
  {
    id: 'sec26',
    label: '26v26 Squad Esports Cup',
    shortLabel: 'SEC 26',
    teamSize: 26,
    maxPlayers: 52,
    playersInQueue: 0
  },
  {
    id: 'sec36',
    label: '36v36 Squad Esports Cup',
    shortLabel: 'SEC 36',
    teamSize: 36,
    maxPlayers: 72,
    playersInQueue: 0
  },
  {
    id: 'sec46',
    label: '46v46 Squad Esports Cup',
    shortLabel: 'SEC 46',
    teamSize: 46,
    maxPlayers: 92,
    playersInQueue: 0
  }
];

const mountQueuePanel = (props = {}) => mount(QueuePanel, {
  props: {
    queueModes: ['balt26', 'ocbt15', 'sec26', 'sec36', 'sec46']
      .map((modeId) => queueModes.find((queueMode) => queueMode.id === modeId))
      .filter(Boolean),
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

    expect(wrapper.text()).not.toContain('Skirmish Layers');
    expect(wrapper.text()).not.toContain('Hotdrop');
    expect(wrapper.text()).not.toContain('S3O Layers');
    expect(wrapper.text()).not.toContain('Rivals Layers');
    expect(wrapper.text()).not.toContain('Offworld Squad Invitational Layers');
    expect(wrapper.text()).toContain('Open Clan Battle Layers');
    expect(wrapper.text()).toContain('Squad Balt Layers');
    expect(wrapper.text()).toContain('Squad Esports Cup Layers');
    expect(wrapper.text()).not.toContain('30v30');
    expect(wrapper.text()).toContain('15v15');
    expect(wrapper.text()).toContain('26v26');
  });

  test('renders visible queue cards in display order', () => {
    const wrapper = mountQueuePanel();
    const titles = wrapper.findAll('.queue-title-link').map((link) => link.text());

    expect(titles).toEqual([
      'Squad Balt Layers',
      'Open Clan Battle Layers',
      'Squad Esports Cup Layers'
    ]);
  });

  test('emits join-queue for the selected mode', async () => {
    const wrapper = mountQueuePanel();

    await wrapper.find('.queue-action').trigger('click');

    expect(wrapper.emitted('join-queue')).toEqual([['balt26']]);
  });

  test('emits leave-queue when already queued for the mode', async () => {
    const wrapper = mountQueuePanel({
      inQueue: true,
      currentQueueMode: 'balt26'
    });

    const leaveButton = wrapper.findAll('.queue-action').find((button) => button.text() === 'Leave Queue');
    await leaveButton.trigger('click');

    expect(wrapper.emitted('leave-queue')).toEqual([['balt26']]);
  });

  test('shows admin queue tools only when allowed', () => {
    const normalWrapper = mountQueuePanel();
    const adminWrapper = mountQueuePanel({ canManageQueueTools: true });

    expect(normalWrapper.find('.queue-dev-actions').exists()).toBe(false);
    expect(adminWrapper.find('.queue-dev-actions').exists()).toBe(true);
  });

  test('links the Squad Esports Cup title to the workshop page', () => {
    const wrapper = mountQueuePanel();
    const link = wrapper.findAll('a[href="https://steamcommunity.com/sharedfiles/filedetails/?id=3661196801"]')
      .find((candidate) => candidate.text() === 'Squad Esports Cup Layers');

    expect(link).toBeTruthy();
    expect(link.text()).toBe('Squad Esports Cup Layers');
    expect(link.attributes('target')).toBe('_blank');
    expect(link.attributes('rel')).toBe('noopener noreferrer');
  });

  test('links card titles to their mod pages when configured', () => {
    const wrapper = mountQueuePanel();
    const links = wrapper.findAll('.queue-title-link').map((link) => link.attributes('href'));
    const secLinks = links.filter((href) => href === 'https://steamcommunity.com/sharedfiles/filedetails/?id=3661196801');

    expect(links).not.toContain('https://steamcommunity.com/sharedfiles/filedetails/?id=3294562930');
    expect(secLinks).toHaveLength(1);
    expect(links).not.toContain('https://steamcommunity.com/sharedfiles/filedetails/?id=3735813803');
    expect(links).toContain('https://steamcommunity.com/sharedfiles/filedetails/?id=3264205573');
    expect(links).toContain('https://steamcommunity.com/sharedfiles/filedetails/?id=3686670558');
  });

  test('disables joining when the only server is busy', () => {
    const wrapper = mountQueuePanel({ serverAvailable: false });

    expect(wrapper.text()).toContain('Server unavailable');
    expect(wrapper.find('.queue-action').attributes('disabled')).toBeDefined();
  });
});
