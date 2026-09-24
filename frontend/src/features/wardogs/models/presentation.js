export const findParticipant = (match, username) => {
  if (!username || !match) return null;
  for (const faction of match.factions || []) {
    for (const group of faction.groups || []) {
      const player = group.players?.find((member) => member.id === username);
      if (player) return { player, group, faction };
    }
  }
  return null;
};

export const participantObservation = (match, participant) => {
  if (!participant) return 'No personal roster position';
  const { player, faction } = participant;
  const freshness = match.observation?.state;
  if (freshness === 'stale') {
    return player.connected === true ? 'Last seen connected; current presence unknown'
      : player.connected === false ? 'Last seen absent; current presence unknown'
        : 'Current presence unknown';
  }
  if (freshness !== 'fresh') return 'Server presence unknown';
  if (player.connected === false) return 'Not observed on server';
  if (player.connected !== true) return 'Connection unknown';
  if (!player.observedFactionId) return 'Connected; faction unknown';
  return player.observedFactionId === faction.id
    ? `Connected on ${faction.name}`
    : `Connected on ${player.observedFactionName || player.observedFactionId}; assigned ${faction.name}`;
};

export const matchRoomState = (match, participant) => {
  const result = match.result || {};
  if (result.status !== 'unconfirmed' && result.status !== 'confirmed-demo') {
    const title = result.status === 'void' ? 'Match void'
      : result.status === 'incomplete' ? 'Match incomplete'
        : result.corrected ? 'Corrected result' : 'Result confirmed';
    return { title, action: 'Review confirmed result', joinProminent: false, resultProminent: true };
  }
  if (result.status === 'confirmed-demo') {
    return { title: 'Demo result', action: 'Review sample result', joinProminent: false, resultProminent: true };
  }
  if (match.source !== 'cmp-backend') {
    return { title: match.label, action: 'Review this sample roster', joinProminent: false, resultProminent: false };
  }
  if (match.join?.state === 'waiting_for_server') {
    return { title: 'Waiting for server', action: 'Waiting for allocation', joinProminent: false, resultProminent: false };
  }
  if (match.join?.state !== 'manual_join_available' && match.join?.state !== 'direct_join_available') {
    return { title: 'Server allocated', action: 'Join details are not available yet', joinProminent: false, resultProminent: false };
  }
  if (!participant) {
    if (match.observation?.state === 'stale') {
      return { title: 'Server observation stale', action: 'Current server presence is unknown',
        joinProminent: false, resultProminent: false };
    }
    return { title: 'Server ready', action: 'Review the planned roster', joinProminent: true, resultProminent: false };
  }
  const { player, faction } = participant;
  if (player.rosterStatus === 'reserve') {
    return { title: `Reserve for ${faction.name}`, action: 'Stay available for your faction',
      joinProminent: false, resultProminent: false };
  }
  if (match.observation?.state === 'stale') {
    return { title: 'Server observation stale', action: 'Current connection and faction are unknown',
      joinProminent: player.connected !== true, resultProminent: false };
  }
  if (match.observation?.state === 'fresh' && player.connected === true) {
    if (player.observedFactionId && player.observedFactionId !== faction.id) {
      return { title: 'Connected on wrong faction', action: `Move to ${faction.name}`, joinProminent: false, resultProminent: false };
    }
    if (!player.observedFactionId) {
      return { title: 'Connected; faction unknown', action: `Check your in-game faction: ${faction.name}`, joinProminent: false, resultProminent: false };
    }
    return { title: player.ready ? 'Ready' : 'Connected on assigned faction',
      action: player.ready ? 'You are ready' : 'Readiness not confirmed',
      joinProminent: false, resultProminent: false };
  }
  return { title: 'Server ready', action: `Join ${faction.name} using the Join ID`, joinProminent: true, resultProminent: false };
};
