export function normalizePlayer(player) {
  return {
    name: player.name || null,
    steamID: player.steamID || null,
    eosID: player.eosID || null,
    playerID: player.playerID ?? null,
    teamID: player.teamID ?? null,
    squadID: player.squadID ?? null,
    role: player.role || null,
    isLeader: player.isLeader ?? null
  };
}
