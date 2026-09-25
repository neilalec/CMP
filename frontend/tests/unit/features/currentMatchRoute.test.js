import { routeForCurrentMatch } from '@/features/app/utils/currentMatch'

describe('current match route mapping', () => {
  test('maps Squad and WARDOGS descriptors to their own rooms', () => {
    expect(routeForCurrentMatch({ gameType: 'squad', lobbyId: 'squad-room' }))
      .toBe('/lobby/squad-room')
    expect(routeForCurrentMatch({ gameType: 'wardogs', lobbyId: 'wardogs-room' }))
      .toBe('/wardogs/lobby/wardogs-room')
  })

  test('rejects absent, malformed, and unknown game descriptors', () => {
    expect(routeForCurrentMatch(null)).toBeNull()
    expect(routeForCurrentMatch({ gameType: 'squad', lobbyId: '' })).toBeNull()
    expect(routeForCurrentMatch({ gameType: 'future-game', lobbyId: 'room' })).toBeNull()
    expect(routeForCurrentMatch({ gameType: undefined, lobbyId: 'room' })).toBeNull()
  })
})
