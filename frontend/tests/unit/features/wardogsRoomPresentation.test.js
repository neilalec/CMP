import { mount } from '@vue/test-utils';
import { findParticipant, matchRoomState, participantObservation } from '@/features/wardogs/models/presentation';
import MatchStateHeader from '@/features/wardogs/components/MatchStateHeader.vue';
import JoinState from '@/features/wardogs/components/JoinState.vue';
import FactionRoster from '@/features/wardogs/components/FactionRoster.vue';
import { factionSummary } from '@/features/wardogs/models/match';

const makeMatch = () => {
  const player = { id: 'alice', displayName: 'Alice', rosterStatus: 'active', registered: true,
    steamId: '76561198000000001', connected: null, observedFactionId: null,
    observedFactionName: null, ready: false };
  const group = { id: 'premade-1', name: 'Premade', type: 'premade', leaderId: 'alice', players: [player] };
  return { source: 'cmp-backend', phase: 'assembling', label: 'WARDOGS lobby',
    join: { state: 'waiting_for_server', joinId: null },
    observation: { state: 'none' }, result: { status: 'unconfirmed' },
    factions: [
      { id: 'valkyra', name: 'Valkyra', color: '#8b5568', commanderId: null, groups: [group] },
      { id: 'lonestar', name: 'Lonestar', color: '#4b7186', commanderId: null, groups: [] },
      { id: 'manticore', name: 'Manticore', color: '#62754e', commanderId: null, groups: [] }
    ] };
};

describe('WARDOGS room presentation', () => {
  test('allocation waiting keeps planned role and unknown presence separate', () => {
    const match = makeMatch();
    const participant = findParticipant(match, 'alice');
    expect(matchRoomState(match, participant)).toMatchObject({ title: 'Waiting for server', joinProminent: false });
    const view = mount(MatchStateHeader, { props: { match, participant } });
    expect(view.text()).toContain('Waiting for allocation');
    expect(view.text()).toContain('Valkyra · Active');
    expect(view.text()).toContain('Server presence unknown');
  });

  test('Join ID is actionable before connection and secondary after alignment', async () => {
    const match = makeMatch();
    match.join = { state: 'manual_join_available', serverName: 'WARDOGS A', joinId: 'join-123',
      instructions: ['Open WARDOGS.', 'Choose Join By ID.'] };
    const participant = findParticipant(match, 'alice');
    expect(matchRoomState(match, participant)).toMatchObject({ title: 'Server ready', joinProminent: true });
    const join = mount(JoinState, { props: { join: match.join, prominent: true } });
    expect(join.text()).toContain('join-123');
    expect(join.get('button').text()).toBe('Copy Join ID');
    participant.player.connected = true;
    participant.player.observedFactionId = 'valkyra';
    match.observation.state = 'fresh';
    expect(matchRoomState(match, participant)).toMatchObject({ title: 'Connected on assigned faction', joinProminent: false });
    participant.player.ready = true;
    expect(matchRoomState(match, participant).title).toBe('Ready');
    await join.setProps({ prominent: false });
    expect(join.classes()).toContain('is-compact');
  });

  test('reserve, mismatch, and stale observation remain distinct', () => {
    const match = makeMatch();
    const participant = findParticipant(match, 'alice');
    match.join = { state: 'manual_join_available', joinId: 'join-123' };
    participant.player.rosterStatus = 'reserve';
    participant.player.connected = true;
    participant.player.observedFactionId = 'lonestar';
    participant.player.observedFactionName = 'Lonestar';
    match.observation.state = 'fresh';
    expect(matchRoomState(match, participant)).toMatchObject({ title: 'Reserve for Valkyra', joinProminent: false });
    participant.player.rosterStatus = 'active';
    expect(matchRoomState(match, participant)).toMatchObject({ title: 'Connected on wrong faction', action: 'Move to Valkyra' });
    participant.player.rosterStatus = 'reserve';
    const header = mount(MatchStateHeader, { props: { match, participant } });
    expect(header.text()).toContain('Valkyra · Reserve');
    expect(header.text()).toContain('Connected on Lonestar; assigned Valkyra');
    const roster = mount(FactionRoster, { props: { faction: match.factions[0],
      summary: factionSummary(match.factions[0]), observationState: 'fresh',
      myGroupId: 'premade-1', myPlayerId: 'alice' } });
    expect(roster.text()).toContain('Your group');
    expect(roster.text()).toContain('Alice · You');
    participant.player.rosterStatus = 'active';
    match.observation.state = 'stale';
    expect(participantObservation(match, participant)).toContain('current presence unknown');
    expect(matchRoomState(match, participant).title).toBe('Server observation stale');
  });

  test('observed scores cannot confirm a result; corrected, incomplete, and void are explicit', () => {
    const match = makeMatch();
    match.scores = { valkyra: 999, lonestar: 1, manticore: 0 };
    const participant = findParticipant(match, 'alice');
    expect(matchRoomState(match, participant).resultProminent).toBe(false);
    match.result = { status: 'completed_win', corrected: true, revisionNumber: 2 };
    expect(matchRoomState(match, participant)).toMatchObject({ title: 'Corrected result', resultProminent: true });
    match.result.status = 'incomplete';
    expect(matchRoomState(match, participant).title).toBe('Match incomplete');
    match.result.status = 'void';
    expect(matchRoomState(match, participant).title).toBe('Match void');
  });
});
