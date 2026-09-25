export function routeForCurrentMatch(currentMatch) {
  if (!currentMatch || typeof currentMatch.lobbyId !== 'string' || !currentMatch.lobbyId.trim()) {
    return null
  }

  const lobbyId = encodeURIComponent(currentMatch.lobbyId)
  if (currentMatch.gameType === 'squad') return `/lobby/${lobbyId}`
  if (currentMatch.gameType === 'wardogs') return `/wardogs/lobby/${lobbyId}`
  return null
}
