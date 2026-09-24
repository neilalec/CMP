export const visibleProductQueues = (queueModes) =>
  Object.values(queueModes || {}).filter((mode) => mode?.gameType === 'wardogs')
