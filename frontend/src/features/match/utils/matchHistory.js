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

export const mapMatchToHistoryRow = (match) => {
  const roundResult = match.round_result || null
  const winner = isUnresolvedRound(roundResult) ? null : roundResult?.winner
  const loser = isUnresolvedRound(roundResult) ? null : roundResult?.loser
  const score = getRoundScore(roundResult)

  return {
    id: match.id,
    lobbyId: match.lobby_id || '',
    map: match.selected_map || roundResult?.layer || 'Unknown map',
    server: match.server_name || 'Unknown server',
    completedAt: match.completed_at ? new Date(match.completed_at * 1000).toLocaleString() : 'Unknown time',
    result: resultLabel(roundResult),
    winner: teamLabel(winner),
    loser: teamLabel(loser),
    score: score.value,
    hasScore: score.hasScore,
    note: isUnresolvedRound(roundResult) ? 'Winner or ticket totals unavailable' : '',
    players: Array.isArray(match.players) ? match.players : []
  }
}
