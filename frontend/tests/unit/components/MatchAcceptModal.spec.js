import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
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

    expect(wrapper.text()).toContain('Match found')
    expect(wrapper.text()).toContain('18s left')
    expect(wrapper.text()).toContain('2 of 9 accepted')
    expect(wrapper.get('[role="dialog"]').attributes('aria-modal')).toBe('true')
    expect(wrapper.get('#match-accept-title').text()).toBe('Accept this match')
    expect(wrapper.get('button.match-accept-button').text()).toBe('Accept Match')
    expect(wrapper.text()).toContain('Accepted')
    expect(wrapper.text()).toContain('Waiting')
  })

  test('replaces the dominant action with accepted and waiting status', () => {
    const wrapper = mount(MatchAcceptModal, {
      props: { ...defaults, hasAccepted: true, acceptedCount: 8, waitingPlayers: ['charlie'] }
    })

    expect(wrapper.text()).toContain('Waiting for 1 player')
    expect(wrapper.get('.match-accept-confirmed').text()).toBe('Accepted · waiting for others')
    expect(wrapper.find('button.match-accept-button').exists()).toBe(false)
    expect(wrapper.text()).toContain('18s left')
    expect(wrapper.get('#match-accept-title').text()).toBe('You accepted')
  })

  test('shows stable finalization without a repeated action or expired timer', async () => {
    const wrapper = mount(MatchAcceptModal, {
      props: { ...defaults, hasAccepted: true, finalizingLobby: true }
    })
    expect(wrapper.text()).toContain('Preparing match…')
    expect(wrapper.text()).toContain('Opening the match when it is ready.')
    expect(wrapper.find('button.match-accept-button').exists()).toBe(false)
    expect(wrapper.find('.match-accept-countdown').exists()).toBe(false)
    expect(wrapper.get('.match-accept-confirmed').text()).toBe('Accepted · preparing match')
    await wrapper.setProps({ isCancelled: true, cancelReason: 'Lobby could not be formed.' })
    expect(wrapper.text()).toContain('Lobby could not be formed.')
    expect(wrapper.get('button.match-accept-button').text()).toBe('Dismiss')
    await wrapper.get('button.match-accept-button').trigger('click')
    expect(wrapper.emitted('dismiss')).toHaveLength(1)
  })

  test('disables the initial decision while an acceptance request is in flight', () => {
    const wrapper = mount(MatchAcceptModal, { props: { ...defaults, loading: true, countdown: 4 } })
    expect(wrapper.get('button.match-accept-button').text()).toBe('Accepting…')
    expect(wrapper.get('button.match-accept-button').attributes('disabled')).toBeDefined()
    expect(wrapper.get('.match-accept-countdown').classes()).toContain('is-urgent')
  })

  test('preserves the close event for active cancellation', async () => {
    const wrapper = mount(MatchAcceptModal, { props: defaults })
    await wrapper.get('.match-accept-close').trigger('click')
    expect(wrapper.emitted('close')).toHaveLength(1)
  })

  test('focuses the decision then moves focus to the accepted state', async () => {
    const opener = document.createElement('button')
    document.body.append(opener)
    opener.focus()
    const wrapper = mount(MatchAcceptModal, { props: defaults, attachTo: document.body })
    await nextTick()
    expect(document.activeElement).toBe(wrapper.get('.match-accept-button').element)
    await wrapper.get('.match-accept-button').trigger('keydown', { key: 'Tab' })
    expect(document.activeElement).toBe(wrapper.get('.match-accept-close').element)
    await wrapper.setProps({ hasAccepted: true })
    await nextTick()
    expect(document.activeElement).toBe(wrapper.get('#match-accept-title').element)
    await wrapper.setProps({ active: false })
    expect(document.activeElement).toBe(opener)
    wrapper.unmount()
    opener.remove()
  })

  test('focuses the heading when the initial action is disabled', async () => {
    const wrapper = mount(MatchAcceptModal, { props: { ...defaults, loading: true }, attachTo: document.body })
    await nextTick()
    expect(document.activeElement).toBe(wrapper.get('#match-accept-title').element)
    wrapper.unmount()
  })
})
