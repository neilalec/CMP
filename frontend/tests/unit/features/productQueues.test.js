import { visibleProductQueues } from '../../../src/features/home/utils/productQueues'

test('participant queue selection includes WARDOGS and excludes legacy Squad modes', () => {
  const squad = { id: 'skirmish', label: 'Skirmish', maxPlayers: 40 }
  const wardogs = { id: 'wardogs_beta9', gameType: 'wardogs', label: 'WARDOGS Beta', maxPlayers: 9 }
  expect(visibleProductQueues({ skirmish: squad, wardogs_beta9: wardogs })).toEqual([wardogs])
  expect(visibleProductQueues({ skirmish: squad })).toEqual([])
})
