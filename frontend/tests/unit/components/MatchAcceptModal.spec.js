import { mount } from '@vue/test-utils'
import MatchAcceptModal from '@/features/app/components/MatchAcceptModal.vue'

const defaults = {
  active: true,
  isCancelled: false,
  acceptedCount: 2,
  requiredCount: 9,
  acceptedPlayers: ['alpha', 'bravo'],
  waitingPlayers: ['charlie'],
  loading: false,
  hasAccepted: false,
  countdown: 18
}

describe('WARDOGS Match Accept modal', () => {
  test('puts Match found, countdown, and Accept Match first', () => {
    const wrapper = mount(MatchAcceptModal, { props: defaults })

    expect(wrapper.text()).toContain('Match Found')
    expect(wrapper.text()).toContain('18s left')
    expect(wrapper.text()).toContain('2/9 accepted')
    expect(wrapper.get('button.match-accept-button').text()).toBe('Accept Match')
    expect(wrapper.text()).toContain('Accepted')
    expect(wrapper.text()).toContain('Waiting')
  })

  test('replaces the dominant action with accepted and waiting status', () => {
    const wrapper = mount(MatchAcceptModal, {
      props: { ...defaults, hasAccepted: true, acceptedCount: 8, waitingPlayers: ['charlie'] }
    })

    expect(wrapper.text()).toContain('Waiting for 1 player')
    expect(wrapper.get('.match-accept-confirmed').text()).toBe('Accepted')
    expect(wrapper.find('button.match-accept-button').exists()).toBe(false)
    expect(wrapper.text()).toContain('18s left')
  })

  test('shows finalization while retaining the roster and cancellation reason', async () => {
    const wrapper = mount(MatchAcceptModal, {
      props: { ...defaults, hasAccepted: true, finalizingLobby: true }
    })
    expect(wrapper.text()).toContain('Preparing match…')
    expect(wrapper.find('button.match-accept-button').exists()).toBe(false)
    await wrapper.setProps({ isCancelled: true, cancelReason: 'Lobby could not be formed.' })
    expect(wrapper.text()).toContain('Lobby could not be formed.')
    expect(wrapper.get('button.match-accept-button').text()).toBe('OK')
  })
})
