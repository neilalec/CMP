const isUnresolvedRound = (roundResult) => Boolean(
  roundResult
  && roundResult.partial
  && (
    !roundResult.loser
    || roundResult.winner?.inferred
  )
)

const resultLabel = (roundResult) => {
  if (!roundResult) return 'Unknown'
  if (isUnresolvedRound(roundResult)) return 'Unresolved'
  if (roundResult.winner && roundResult.loser) return 'Complete'
  return 'Complete'
}

const teamLabel = (team) => {
  if (!team) return ''
  return [team.subfaction, team.faction].filter(Boolean).join(' ')
    || (team.team ? `Team ${team.team}` : '')
    || team.winner
    || team.name
    || ''
}

const getRoundScore = (roundResult) => {
  const winnerTickets = Number(roundResult?.winner?.tickets)
  const loserTickets = Number(roundResult?.loser?.tickets)
  const hasScore = (
    !isUnresolvedRound(roundResult)
    && Number.isFinite(winnerTickets)
    && Number.isFinite(loserTickets)
  )

  return {
    hasScore,
    value: hasScore ? `${winnerTickets}-${loserTickets}` : ''
  }
}

const statValue = (player, key) => Number(player?.stats?.[key] || 0)

const getMatchRounds = (roundResult) => (
  Array.isArray(roundResult?.rounds) && roundResult.rounds.length
    ? roundResult.rounds
    : (roundResult ? [roundResult] : [])
)

const mapStatPlayer = (player) => ({
  key: player.key || player.eosID || player.steamID || player.name || '',
  name: player.name || player.steamID || player.eosID || 'Unknown player',
  steamID: player.steamID || '',
  eosID: player.eosID || '',
  teamID: player.teamID ?? null,
  squadID: player.squadID ?? null,
  kills: statValue(player, 'kills'),
  deaths: statValue(player, 'deaths'),
  wounds: statValue(player, 'wounds'),
  revives: statValue(player, 'revives'),
  teamkills: statValue(player, 'teamkills'),
  teamDeaths: statValue(player, 'teamDeaths')
})

const getLobbyTeamID = (match, playerName) => {
  const teams = match?.teams || {}
  if ((teams.team1 || []).includes(playerName)) return 1
  if ((teams.team2 || []).includes(playerName)) return 2
  return null
}

const mapLobbyPlayer = (match, playerName) => ({
  key: `lobby:${playerName}`,
  name: playerName || 'Unknown player',
  teamID: getLobbyTeamID(match, playerName),
  squadID: null,
  kills: 0,
  deaths: 0,
  wounds: 0,
  revives: 0,
  teamkills: 0,
  teamDeaths: 0,
  fromLobby: true
})

const normalizedIdentity = (value) => String(value || '').trim().toLowerCase()

const getStatPlayerIdentities = (player) => {
  const identities = new Set([
    normalizedIdentity(player.key),
    normalizedIdentity(player.name),
    normalizedIdentity(player.steamID),
    normalizedIdentity(player.eosID)
  ].filter(Boolean))

  if (player.steamID && String(player.steamID).length >= 8) {
    identities.add(`steam_${String(player.steamID).slice(-8)}`)
  }

  return identities
}

const getLobbyPlayerIdentities = (playerName) => new Set([
  normalizedIdentity(playerName)
].filter(Boolean))

const findStatPlayerForLobbyPlayer = (playersByIdentity, playerName) => {
  for (const identity of getLobbyPlayerIdentities(playerName)) {
    const player = playersByIdentity.get(identity)
    if (player) return player
  }
  return null
}

export const getRoundStats = (roundResult, match) => {
  const roundStats = roundResult?.roundStats || null
  const playersByIdentity = new Map()
  const players = Array.isArray(roundStats?.players)
    ? roundStats.players.map(mapStatPlayer)
    : []

  for (const player of players) {
    for (const identity of getStatPlayerIdentities(player)) {
      playersByIdentity.set(identity, player)
    }
  }

  for (const playerName of match?.players || []) {
    const normalizedName = normalizedIdentity(playerName)
    if (!normalizedName) continue
    const statPlayer = findStatPlayerForLobbyPlayer(playersByIdentity, playerName)
    if (statPlayer) {
      statPlayer.lobbyName = playerName
      statPlayer.teamID = getLobbyTeamID(match, playerName) ?? statPlayer.teamID
      continue
    }
    players.push(mapLobbyPlayer(match, playerName))
  }

  players.sort((a, b) => (
      b.kills - a.kills
      || b.wounds - a.wounds
      || b.revives - a.revives
      || a.deaths - b.deaths
      || Number(a.fromLobby) - Number(b.fromLobby)
      || a.name.localeCompare(b.name)
    ))

  const teamOrder = (teamID) => {
    const numericTeam = Number(teamID)
    if (numericTeam === 1) return 1
    if (numericTeam === 2) return 2
    return 99
  }
  const teamGroups = Array.from(players.reduce((groups, player) => {
    const key = player.teamID ?? 'unknown'
    if (!groups.has(key)) {
      groups.set(key, {
        key: String(key),
        teamID: player.teamID ?? null,
        label: player.teamID ? `Team ${player.teamID}` : 'Unknown Team',
        players: []
      })
    }
    groups.get(key).players.push(player)
    return groups
  }, new Map()).values()).sort((a, b) => teamOrder(a.teamID) - teamOrder(b.teamID))

  return {
    hasStats: players.length > 0,
    source: roundStats?.source || '',
    eventCount: Array.isArray(roundStats?.rawEvents) ? roundStats.rawEvents.length : 0,
    players,
    teamGroups
  }
}

const getRoundTicketRows = (roundResult) => {
  if (isUnresolvedRound(roundResult)) return []
  const sides = [roundResult?.winner, roundResult?.loser].filter(Boolean)
  return sides.map((side) => {
    const tickets = Number(side?.tickets)
    return {
      team: side?.team ? String(side.team) : '',
      label: teamLabel(side),
      tickets: Number.isFinite(tickets) ? tickets : null,
      wonRound: side === roundResult?.winner
    }
  }).filter((side) => side.team && side.tickets !== null)
}

const getOverallTickets = (rounds) => {
  const totals = new Map()
  for (const round of rounds) {
    for (const side of getRoundTicketRows(round)) {
      if (!totals.has(side.team)) {
        totals.set(side.team, {
          team: side.team,
          label: `Team ${side.team}`,
          tickets: 0
        })
      }
      totals.get(side.team).tickets += side.tickets
    }
  }

  const rows = Array.from(totals.values()).sort((a, b) => Number(a.team) - Number(b.team))
  const sorted = [...rows].sort((a, b) => b.tickets - a.tickets)
  const hasWinner = sorted.length >= 2 && sorted[0].tickets !== sorted[1].tickets
  return {
    rows,
    winner: hasWinner ? sorted[0] : null,
    loser: hasWinner ? sorted[1] : null,
    score: rows.length ? rows.map((row) => `${row.label} ${row.tickets}`).join(' - ') : '',
    result: hasWinner ? `${sorted[0].label} wins by ${sorted[0].tickets - sorted[1].tickets}` : (rows.length ? 'Draw on total tickets' : '')
  }
}

export const mapMatchToHistoryRow = (match) => {
  const roundResult = match.round_result || null
  const rounds = getMatchRounds(roundResult)
  const overallTickets = getOverallTickets(rounds)
  const winner = overallTickets.winner || (isUnresolvedRound(roundResult) ? null : roundResult?.winner)
  const loser = overallTickets.loser || (isUnresolvedRound(roundResult) ? null : roundResult?.loser)
  const score = overallTickets.score ? { hasScore: true, value: overallTickets.score } : getRoundScore(roundResult)

  return {
    id: match.id,
    lobbyId: match.lobby_id || '',
    map: match.selected_map || roundResult?.layer || 'Unknown map',
    server: match.server_name || 'Unknown server',
    completedAt: match.completed_at ? new Date(match.completed_at * 1000).toLocaleString() : 'Unknown time',
    result: resultLabel(roundResult),
    winner: winner?.label || teamLabel(winner),
    loser: loser?.label || teamLabel(loser),
    score: score.value,
    hasScore: score.hasScore,
    note: isUnresolvedRound(roundResult) ? 'Winner or ticket totals unavailable' : '',
    rounds: rounds.map((round, index) => {
      const roundScore = getRoundScore(round)
      const roundWinner = isUnresolvedRound(round) ? null : round?.winner
      const stats = getRoundStats(round, match)
      return {
        key: `${round.observedAt || round.time || index}`,
        roundNumber: round.roundNumber || index + 1,
        result: resultLabel(round),
        score: roundScore.value,
        winner: teamLabel(roundWinner) || '',
        note: isUnresolvedRound(round) ? 'Unresolved' : '',
        stats
      }
    }),
    overallTickets,
    players: Array.isArray(match.players) ? match.players : []
  }
}
