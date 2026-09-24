const SQUAD_QUEUE_ORDER = ['s3osmall5', 'ocbt15', 'skirmish']

export const visibleProductQueues = (queueModes, target = 'wardogs') => {
  if (target === 'squad') {
    return SQUAD_QUEUE_ORDER
      .map((modeId) => queueModes?.[modeId])
      .filter((mode) => mode && mode.gameType !== 'wardogs')
  }
  return Object.values(queueModes || {}).filter((mode) => mode?.gameType === 'wardogs')
}
