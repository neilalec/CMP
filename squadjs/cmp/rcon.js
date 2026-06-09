export async function ensureRconConnected(server, state) {
  if (!server.rcon) {
    const error = new Error('RCON is not configured.');
    error.statusCode = 503;
    throw error;
  }

  if (server.rcon.connected && server.rcon.loggedin) {
    return;
  }

  if (state.reconnectPromise) {
    await state.reconnectPromise;
    return;
  }

  state.reconnectPromise = (async () => {
    try {
      await server.rcon.connect();
    } catch (error) {
      error.statusCode = 503;
      throw error;
    }
  })();

  try {
    await state.reconnectPromise;
  } finally {
    state.reconnectPromise = null;
  }
}

export async function refreshRconLayerStatus(server, state) {
  if (!server.rcon) return null;

  await ensureRconConnected(server, state);

  const nextStatus = {
    currentLevel: null,
    currentLayer: null,
    nextLevel: null,
    nextLayer: null
  };

  if (typeof server.rcon.getCurrentMap === 'function') {
    const current = await server.rcon.getCurrentMap();
    nextStatus.currentLevel = current?.level || null;
    nextStatus.currentLayer = current?.layer || null;
  }

  if (typeof server.rcon.getNextMap === 'function') {
    const next = await server.rcon.getNextMap();
    nextStatus.nextLevel = next?.level || null;
    nextStatus.nextLayer = next?.layer || null;
  }

  state.layerStatus = nextStatus;
  return nextStatus;
}

export async function refreshServerInfo(server, state) {
  if (typeof server.updateServerInformation === 'function') {
    await ensureRconConnected(server, state);
    const updated = await server.updateServerInformation();
    if (updated === false) {
      const error = new Error('Failed to refresh server information from RCON.');
      error.statusCode = 503;
      throw error;
    }
  }
  await refreshRconLayerStatus(server, state);
}

export async function refreshPlayerList(server, state) {
  if (typeof server.updatePlayerList === 'function') {
    await ensureRconConnected(server, state);
    const updated = await server.updatePlayerList();
    if (updated === false) {
      const error = new Error('Failed to refresh player list from RCON.');
      error.statusCode = 503;
      throw error;
    }
  }
}

export function buildLayerCommand(prefix, payload) {
  const layer = typeof payload.layer === 'string' ? payload.layer.trim() : '';
  const faction1 = typeof payload.faction1 === 'string' ? payload.faction1.trim() : '';
  const faction2 = typeof payload.faction2 === 'string' ? payload.faction2.trim() : '';

  if (!layer) {
    throw new Error('layer is required');
  }

  return [prefix, layer, faction1, faction2].filter(Boolean).join(' ');
}
