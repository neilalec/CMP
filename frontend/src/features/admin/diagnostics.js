export const formatQueueModeCapacity = (mode = {}) => {
  if (mode.gameType === 'wardogs') {
    const parts = [`${mode.requiredPlayers ?? mode.maxPlayers ?? 0} total players`]
    if (mode.factionCount != null) parts.push(`${mode.factionCount} factions`)
    if (mode.activePerFaction != null) parts.push(`${mode.activePerFaction} active/faction`)
    if (mode.reservePerFaction != null) parts.push(`${mode.reservePerFaction} reserve/faction`)
    return parts.join(' · ')
  }
  return mode.teamSize != null
    ? `${mode.teamSize}v${mode.teamSize} · ${mode.maxPlayers ?? mode.requiredPlayers ?? 0} total players`
    : `${mode.maxPlayers ?? mode.requiredPlayers ?? 0} total players`
}
