import { mount } from '@vue/test-utils';
import WardogsQueueCard from '@/features/home/components/WardogsQueueCard.vue';
import MatchAcceptModal from '@/features/app/components/MatchAcceptModal.vue';

const queueProps = () => ({
  mode: { id: 'wardogs_beta9', gameType: 'wardogs', maxPlayers: 9,
    factionCount: 3, playersInQueue: 4, matchmakingAvailable: true },
  currentQueueMode: null, inQueue: false, matchAcceptActive: false,
  loading: false, isInLobby: false, isInGroup: false, isGroupLeader: false,
  hasSteamId: true, groupMemberCount: 1, wardogsLobbyId: null,
  isModeQueueFull: () => false
});
const queue = (overrides = {}) => mount(WardogsQueueCard, {
  props: { ...queueProps(), ...overrides },
  global: { stubs: { WardogsPlayGroup: true, RouterLink: true } }
});

const acceptProps = () => ({
  active: true, isCancelled: false, cancelReason: '', countdown: 38,
  acceptedCount: 2, requiredCount: 9, acceptedPlayers: ['alice', 'bob'],
  waitingPlayers: ['carol'], playerProfiles: {}, loading: false,
  hasAccepted: false, finalizingLobby: false
});
const accept = (overrides = {}) => mount(MatchAcceptModal, {
  props: { ...acceptProps(), ...overrides }, attachTo: document.body
});

describe('WARDOGS core journey presentation', () => {
  test('idle Play has one queue action and occupancy', () => {
    const view = queue();
    expect(view.text()).toContain('4 / 9');
    expect(view.get('button').text()).toBe('Join Queue');
    expect(view.text()).not.toContain('Your match is ready');
  });

  test('queued Play changes its heading and demotes leaving', () => {
    const view = queue({ inQueue: true, currentQueueMode: 'wardogs_beta9' });
    expect(view.get('h2').text()).toBe('Finding a match');
    expect(view.get('button').text()).toBe('Leave Queue');
    expect(view.get('button').classes()).toContain('cmp-button--secondary');
  });

  test('current match replaces future queue occupancy and group controls', () => {
    const view = queue({ wardogsLobbyId: 'wd-1' });
    expect(view.text()).toContain('Your match is ready');
    expect(view.text()).not.toContain('4 / 9');
    expect(view.find('.wardogs-play-group-stub').exists()).toBe(false);
    expect(view.find('button').exists()).toBe(false);
  });

  test('group member sees queue authority without a competing action', () => {
    const view = queue({ isInGroup: true, isGroupLeader: false, groupMemberCount: 3 });
    expect(view.text()).toContain('Leader controls');
    expect(view.find('button').exists()).toBe(false);
  });

  test('pending acceptance is a single decision with the real countdown', () => {
    const view = accept();
    expect(view.text()).toContain('38s left');
    expect(view.get('.match-accept-button').text()).toBe('Accept Match');
    expect(view.text()).not.toContain('alice');
    expect(view.text()).not.toContain('2 of 9 accepted');
    view.unmount();
  });

  test('accepted, finalizing, and cancelled states replace the decision', async () => {
    const view = accept({ hasAccepted: true });
    expect(view.text()).toContain('You accepted');
    expect(view.text()).toContain('2 of 9 accepted');
    expect(view.text()).toContain('alice');
    expect(view.find('.match-accept-button').exists()).toBe(false);
    await view.setProps({ finalizingLobby: true });
    expect(view.text()).toContain('Preparing match');
    expect(view.text()).not.toContain('alice');
    await view.setProps({ isCancelled: true, finalizingLobby: false });
    expect(view.text()).toContain('Match cancelled');
    expect(view.get('.match-accept-button').text()).toBe('Dismiss');
    view.unmount();
  });
});
