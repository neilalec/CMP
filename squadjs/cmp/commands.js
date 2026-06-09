import {
  buildLayerCommand,
  ensureRconConnected,
  refreshServerInfo
} from './rcon.js';

const MAX_COMMAND_HISTORY = 25;

function compactLayerStatus(layerStatus) {
  if (!layerStatus) return null;
  return {
    currentLevel: layerStatus.currentLevel || null,
    currentLayer: layerStatus.currentLayer || null,
    nextLevel: layerStatus.nextLevel || null,
    nextLayer: layerStatus.nextLayer || null
  };
}

function recordCommand(state, entry) {
  const now = Date.now() / 1000;
  const commandEntry = {
    id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    observedAt: now,
    ...entry
  };

  state.lastCommand = commandEntry;
  state.commandHistory = [
    commandEntry,
    ...(state.commandHistory || [])
  ].slice(0, MAX_COMMAND_HISTORY);

  return commandEntry;
}

function getLayerPayload(payload) {
  return {
    layer: typeof payload.layer === 'string' ? payload.layer.trim() : '',
    faction1: typeof payload.faction1 === 'string' ? payload.faction1.trim() : '',
    faction2: typeof payload.faction2 === 'string' ? payload.faction2.trim() : ''
  };
}

export function getCommandDiagnostics(state) {
  return {
    lastCommand: state.lastCommand || null,
    commandHistory: state.commandHistory || []
  };
}

export async function executeLayerCommand(server, state, { action, payload }) {
  const prefix = action === 'next' ? 'AdminSetNextLayer' : 'AdminChangeLayer';
  const layerPayload = getLayerPayload(payload);
  const command = buildLayerCommand(prefix, layerPayload);
  const startedAt = Date.now() / 1000;

  const auditBase = {
    type: 'layer',
    action,
    command,
    layer: layerPayload.layer,
    faction1: layerPayload.faction1 || null,
    faction2: layerPayload.faction2 || null,
    startedAt,
    layerStatusBefore: compactLayerStatus(state.layerStatus)
  };

  try {
    await ensureRconConnected(server, state);
    const response = await server.rcon.execute(command);
    await refreshServerInfo(server, state);

    const audit = recordCommand(state, {
      ...auditBase,
      ok: true,
      response: response || null,
      completedAt: Date.now() / 1000,
      layerStatusAfter: compactLayerStatus(state.layerStatus)
    });

    return {
      ok: true,
      command,
      response: response || null,
      audit
    };
  } catch (error) {
    const audit = recordCommand(state, {
      ...auditBase,
      ok: false,
      error: error.message,
      completedAt: Date.now() / 1000,
      layerStatusAfter: compactLayerStatus(state.layerStatus)
    });

    error.audit = audit;
    throw error;
  }
}

export async function executeBroadcastCommand(server, state, message) {
  const cleanMessage = typeof message === 'string' ? message.trim() : '';
  if (!cleanMessage) {
    throw new Error('message is required');
  }

  const auditBase = {
    type: 'broadcast',
    action: 'broadcast',
    command: `AdminBroadcast ${cleanMessage}`,
    message: cleanMessage,
    startedAt: Date.now() / 1000,
    layerStatusBefore: compactLayerStatus(state.layerStatus)
  };

  try {
    await ensureRconConnected(server, state);
    const response = await server.rcon.broadcast(cleanMessage);

    const audit = recordCommand(state, {
      ...auditBase,
      ok: true,
      response: response || null,
      completedAt: Date.now() / 1000,
      layerStatusAfter: compactLayerStatus(state.layerStatus)
    });

    return {
      ok: true,
      message: cleanMessage,
      response: response || null,
      audit
    };
  } catch (error) {
    const audit = recordCommand(state, {
      ...auditBase,
      ok: false,
      error: error.message,
      completedAt: Date.now() / 1000,
      layerStatusAfter: compactLayerStatus(state.layerStatus)
    });

    error.audit = audit;
    throw error;
  }
}
