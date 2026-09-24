import { visibleProductQueues } from '../../../src/features/home/utils/productQueues'

test('participant queue selection includes WARDOGS and excludes legacy Squad modes', () => {
  const squad = { id: 'skirmish', label: 'Skirmish', maxPlayers: 40 }
  const wardogs = { id: 'wardogs_beta9', gameType: 'wardogs', label: 'WARDOGS Beta', maxPlayers: 9 }
  expect(visibleProductQueues({ skirmish: squad, wardogs_beta9: wardogs })).toEqual([wardogs])
  expect(visibleProductQueues({ skirmish: squad })).toEqual([])
})

test('Squad comparison restores the three historical featured queues in order', () => {
  const modes = {
    skirmish: { id: 'skirmish' },
    s3osmall5: { id: 's3osmall5' },
    ocbt15: { id: 'ocbt15' },
    wardogs_beta9: { id: 'wardogs_beta9', gameType: 'wardogs' }
  }
  expect(visibleProductQueues(modes, 'squad').map((mode) => mode.id))
    .toEqual(['s3osmall5', 'ocbt15', 'skirmish'])
  expect(visibleProductQueues(modes).map((mode) => mode.id)).toEqual(['wardogs_beta9'])
})
