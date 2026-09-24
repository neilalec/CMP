import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@pinia/testing'
import { useGroupStore } from '@/stores/groupStore'
import WardogsQueueCard from '@/features/home/components/WardogsQueueCard.vue'

const mode = (overrides = {}) => ({
  id: 'wardogs_beta9',
  gameType: 'wardogs',
  shortLabel: 'WARDOGS Beta 9',
  maxPlayers: 9,
  playersInQueue: 4,
  factionCount: 3,
  matchmakingAvailable: true,
  ...overrides
})

const mountCard = (overrides = {}, initialState = {}) => {
  const pinia = createTestingPinia({
    createSpy: jest.fn,
    initialState: {
      auth: { username: 'player1' },
      group: { code: null, leader: null, members: [], playerProfiles: {} },
      ...initialState
    }
  })
  const wrapper = mount(WardogsQueueCard, {
    props: {
      mode: mode(),
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
      getQueueProgressPercent: jest.fn(() => 44),
      isModeQueueFull: jest.fn(() => false),
      ...overrides
    },
    global: { plugins: [pinia], stubs: { RouterLink: { template: '<a :href="to"><slot /></a>', props: ['to'] } } }
  })
  return { wrapper, pinia }
}

describe('WARDOGS Play queue card', () => {
  test('shows the queue, format, population, accessible progress and one primary action', () => {
    const { wrapper } = mountCard()

    expect(wrapper.find('h2').text()).toBe('Beta 9 queue')
    expect(wrapper.text()).toContain('3 factions · 9 players')
    expect(wrapper.find('.wardogs-queue-count').text()).toBe('4 / 9')
    expect(wrapper.find('[role="progressbar"]').attributes()).toMatchObject({
      'aria-label': 'Queue population',
      'aria-valuemax': '9',
      'aria-valuenow': '4',
      'aria-valuetext': '4 of 9 players queued'
    })
    expect(wrapper.findAll('button.wardogs-queue-action')).toHaveLength(1)
    expect(wrapper.get('.wardogs-queue-card').classes()).toContain('cmp-surface')
    expect(wrapper.get('.wardogs-queue-action').classes()).toContain('cmp-button--primary')
    expect(wrapper.find('.wardogs-queue-action').text()).toBe('Join Queue')
    expect(wrapper.get('.wardogs-queue-card').classes()).not.toContain('is-queued')
    expect(wrapper.find('.wardogs-queue-status').text()).toBe('Queue open.')
    expect(wrapper.find('.window-titlebar').exists()).toBe(false)
    expect(wrapper.find('.queue-admin-tools').exists()).toBe(false)
    expect(wrapper.text().toLowerCase()).not.toContain('squad')
  })

  test('emits join and leave actions for the WARDOGS queue', async () => {
    const { wrapper } = mountCard()
    await wrapper.find('.wardogs-queue-action').trigger('click')
    expect(wrapper.emitted('join-queue')).toEqual([['wardogs_beta9']])

    await wrapper.setProps({ inQueue: true, currentQueueMode: 'wardogs_beta9' })
    expect(wrapper.get('.wardogs-queue-card').classes()).toContain('is-queued')
    expect(wrapper.find('.wardogs-queue-state').text()).toBe('Queued')
    expect(wrapper.find('.wardogs-queue-status').text()).toBe('You’re in the queue.')
    expect(wrapper.find('.wardogs-queue-action').text()).toBe('Leave Queue')
    expect(wrapper.get('.wardogs-queue-action').classes()).toContain('cmp-button--secondary')
    await wrapper.find('.wardogs-queue-action').trigger('click')
    expect(wrapper.emitted('leave-queue')).toEqual([['wardogs_beta9']])
  })

  test.each([
    ['queue disabled', { mode: mode({ enabled: false }) }, 'Queue unavailable', 'This queue is currently unavailable.'],
    ['match unavailable', { mode: mode({ matchmakingAvailable: false }) }, 'Match forming', 'A match is being prepared.'],
    ['Steam identity missing', { hasSteamId: false }, 'Steam account required', 'A Steam-linked account is required to join.'],
    ['group non-leader', { isInGroup: true, isGroupLeader: false }, 'Group leader only', 'Ask your group leader to join the queue.'],
    ['full queue', { isModeQueueFull: jest.fn(() => true) }, 'Queue full', 'The queue is full.']
  ])('explains the blocking state when %s', (name, props, action, status) => {
    const { wrapper } = mountCard(props)
    expect(wrapper.find('.wardogs-queue-action').text()).toBe(action)
    expect(wrapper.find('.wardogs-queue-action').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.wardogs-queue-status').text()).toBe(status)
  })

  test('uses a restrained match-forming state while acceptance is active', () => {
    const { wrapper } = mountCard({ matchAcceptActive: true })
    expect(wrapper.find('.wardogs-queue-action').text()).toBe('Match forming')
    expect(wrapper.find('.wardogs-queue-action').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.wardogs-queue-status').text()).toBe('Match forming.')
  })

  test('keeps Leave Queue available when matchmaking becomes unavailable', () => {
    const { wrapper } = mountCard({
      inQueue: true,
      currentQueueMode: 'wardogs_beta9',
      mode: mode({ matchmakingAvailable: false })
    })
    expect(wrapper.find('.wardogs-queue-action').text()).toBe('Leave Queue')
    expect(wrapper.find('.wardogs-queue-action').attributes('disabled')).toBeUndefined()
  })

  test('shows group queue context only when relevant', () => {
    const { wrapper } = mountCard(
      { isInGroup: true, isGroupLeader: true, groupMemberCount: 3 },
      { group: { code: 'ABCD', leader: 'player1', members: ['player1', 'player2', 'player3'], playerProfiles: {} } }
    )
    expect(wrapper.find('.wardogs-queue-action').text()).toBe('Join Queue')
    expect(wrapper.find('.wardogs-queue-status').text()).toBe('Ready to queue your group of 3.')
    expect(wrapper.get('.wardogs-play-group').text()).toContain('3 players')
    expect(wrapper.get('.wardogs-play-group').text()).toContain('Leader: player1')
    expect(wrapper.get('.wardogs-play-group').text()).toContain('You control queueing for this group.')
    expect(wrapper.get('.wardogs-play-manage').attributes('href')).toBe('/group')
  })

  test('explains that only the group leader can leave a queued group', () => {
    const { wrapper } = mountCard({
      inQueue: true,
      currentQueueMode: 'wardogs_beta9',
      isInGroup: true,
      isGroupLeader: false,
      groupMemberCount: 3
    }, { group: { code: 'ABCD', leader: 'player2', members: ['player1', 'player2', 'player3'], playerProfiles: {} } })
    expect(wrapper.find('.wardogs-queue-action').text()).toBe('Group leader only')
    expect(wrapper.find('.wardogs-queue-action').attributes('disabled')).toBeDefined()
    expect(wrapper.find('.wardogs-queue-status').text()).toBe('Your group leader manages this queue.')
    expect(wrapper.get('.wardogs-play-group').text()).toContain('Leader: player2')
    expect(wrapper.get('.wardogs-play-group').text()).toContain('Only the group leader controls queueing.')
  })

  test('shows the queued group state for its leader', () => {
    const { wrapper } = mountCard({
      inQueue: true,
      currentQueueMode: 'wardogs_beta9',
      isInGroup: true,
      isGroupLeader: true,
      groupMemberCount: 3
    }, { group: { code: 'ABCD', leader: 'player1', members: ['player1', 'player2', 'player3'], playerProfiles: {} } })
    expect(wrapper.find('.wardogs-queue-status').text()).toBe('Your group of 3 is queued.')
    expect(wrapper.find('.wardogs-queue-action').text()).toBe('Leave Queue')
    expect(wrapper.find('.wardogs-queue-action').attributes('disabled')).toBeUndefined()
  })

  test('shows direct solo group actions and invokes existing group actions', async () => {
    const { wrapper, pinia } = mountCard()
    const groupStore = useGroupStore(pinia)
    expect(wrapper.get('.wardogs-play-group').text()).toContain('Solo')
    expect(wrapper.get('.wardogs-play-group').text()).toContain('Create group')
    expect(wrapper.get('.wardogs-play-group').text()).toContain('Join group')

    await wrapper.get('.wardogs-play-group-actions > button').trigger('click')
    expect(groupStore.createGroup).toHaveBeenCalledWith('player1')

    await wrapper.get('#wardogs-play-group-code').setValue('ab12')
    await wrapper.get('.wardogs-play-join').trigger('submit')
    expect(groupStore.joinGroup).toHaveBeenCalledWith('player1', 'AB12')
  })

  test('keeps solo group actions disabled while queued', () => {
    const { wrapper } = mountCard({ inQueue: true, currentQueueMode: 'wardogs_beta9' })
    expect(wrapper.get('.wardogs-play-group-actions > button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('#wardogs-play-group-code').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.wardogs-play-group').text()).toContain('Group changes are unavailable while queued or in a match.')
  })

  test('keeps queue tools separate and admin-only', async () => {
    const { wrapper: participant } = mountCard()
    expect(participant.find('.wardogs-queue-admin-tools').exists()).toBe(false)

    const { wrapper: admin } = mountCard({ canManageQueueTools: true })
    expect(admin.find('.wardogs-queue-admin-tools').exists()).toBe(true)
    await admin.find('.wardogs-queue-admin-tools summary').trigger('click')
    const buttons = admin.findAll('.queue-dev-actions button')
    await buttons[0].trigger('click')
    await buttons[1].trigger('click')
    await buttons[2].trigger('click')
    expect(admin.emitted('seed-queue')).toEqual([['wardogs_beta9']])
    expect(admin.emitted('clear-queue')).toEqual([['wardogs_beta9']])
    expect(admin.emitted('set-queue-enabled')).toEqual([['wardogs_beta9', false]])
  })

  test('replaces the queue action with the active WARDOGS match link', () => {
    const { wrapper } = mountCard({ wardogsLobbyId: 'wardogs-match-1' })
    expect(wrapper.find('a.wardogs-queue-action').text()).toBe('Open Match')
    expect(wrapper.find('a.wardogs-queue-action').attributes('href')).toBe('/wardogs/lobby/wardogs-match-1')
    expect(wrapper.find('button.wardogs-queue-action').exists()).toBe(false)
    expect(wrapper.get('.wardogs-play-group-actions > button').attributes('disabled')).toBeDefined()
  })
})
