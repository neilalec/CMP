import { createPinia, setActivePinia } from 'pinia';
import { mockWardogsDataSource } from '../../../src/features/wardogs/mock/mockDataSource';
import { factionSummary, resultRows } from '../../../src/features/wardogs/models/match';
import { useWardogsMatchStore } from '../../../src/features/wardogs/stores/matchStore';

describe('WARDOGS frontend domain', () => {
  beforeEach(() => setActivePinia(createPinia()));

  test('keeps groups and separates active from reserve counts', async () => {
    const store = useWardogsMatchStore();
    await store.selectScenario('reserves');
    expect(store.match.factions).toHaveLength(3);
    const faction = store.match.factions[0];
    expect(faction.groups.some((group) => group.type === 'clan' && group.leaderId)).toBe(true);
    expect(factionSummary(faction)).toMatchObject({ active: 8, reserves: 2, connected: 8, ready: 8 });
    expect(store.totals.reserves).toBe(2);
  });

  test('readiness and connection are independent observations', async () => {
    const match = await mockWardogsDataSource.loadScenario('disconnected');
    const summary = factionSummary(match.factions[1]);
    expect(summary).toMatchObject({ active: 9, connected: 8, ready: 9, missing: 1, aligned: 8 });
  });

  test('withholds rank for live and incomplete results, and shares tied ranks', async () => {
    expect(resultRows(await mockWardogsDataSource.loadScenario('live'))).toEqual([]);
    expect(resultRows(await mockWardogsDataSource.loadScenario('incompleteResult'))).toEqual([]);
    const ranks = resultRows(await mockWardogsDataSource.loadScenario('tie'));
    expect(ranks.map((row) => row.rank)).toEqual([1, 1, 3]);
    expect(ranks[0].tied).toBe(true);
  });

  test('loading a scenario returns an independent match object', async () => {
    const first = await mockWardogsDataSource.loadScenario('ready');
    first.factions[0].groups[0].players[0].ready = false;
    const second = await mockWardogsDataSource.loadScenario('ready');
    expect(second.factions[0].groups[0].players[0].ready).toBe(true);
  });

  test('thirty-player faction remains grouped with unique player identities', async () => {
    const match = await mockWardogsDataSource.loadScenario('largeRoster');
    const faction = match.factions[0];
    const ids = faction.groups.flatMap((group) => group.players.map((player) => player.id));
    expect(factionSummary(faction).active).toBe(30);
    expect(new Set(ids).size).toBe(30);
    expect(faction.groups).toHaveLength(7);
  });
});
