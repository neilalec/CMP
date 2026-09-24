import { formatQueueModeCapacity } from '../../../src/features/admin/diagnostics'

describe('formatQueueModeCapacity', () => {
  test('describes WARDOGS without relying on a two-team size', () => {
    expect(formatQueueModeCapacity({
      gameType: 'wardogs',
      requiredPlayers: 9,
      factionCount: 3,
      activePerFaction: 3,
      reservePerFaction: 0,
      teamSize: null
    })).toBe('9 total players · 3 factions · 3 active/faction · 0 reserve/faction')
  })

  test('retains Squad team-size formatting', () => {
    expect(formatQueueModeCapacity({
      gameType: 'squad',
      maxPlayers: 40,
      teamSize: 20
    })).toBe('20v20 · 40 total players')
  })
})
