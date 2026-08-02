export const getServerDiscovery = (value) => (
  value?.metadata?.steamLobbyDiscovery
  || value?.steamLobbyDiscovery
  || null
)

export const getServerJoinStrategy = (value) => (
  value?.metadata?.joinStrategy
  || value?.joinStrategy
  || getServerDiscovery(value)?.final
  || null
)

export const formatLookupStep = (step, emptyLabel = 'No live Steam ID found') => {
  if (!step || !step.attempted) return 'Not attempted'
  if (step.error) return step.error
  if (step.steamLobbyId) return step.steamLobbyId
  if (typeof step.matchedCount === 'number' && step.matchedCount > 0) {
    return `${step.matchedCount} candidate(s), no Steam ID`
  }
  return emptyLabel
}

export const formatJoinStrategy = (strategy) => {
  if (!strategy) return 'Unavailable'
  if (strategy.joinMethod === 'steam_lobby') {
    if (strategy.source === 'stored_cache') return 'Steam Lobby (cached)'
    if (strategy.source === 'bridge_payload') return 'Steam Lobby (bridge)'
    if (strategy.source === 'a2s_info') return 'Steam Lobby (A2S)'
    if (strategy.source === 'steam_web_api') return 'Steam Lobby (Steam web)'
    return 'Steam Lobby'
  }
  if (strategy.joinMethod === 'direct_connect') return 'Direct Connect'
  return 'Unavailable'
}
