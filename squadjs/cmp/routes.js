import { sendJson, isAuthorized, readJsonBody } from './http.js';
import { buildServerPayload, listLayers } from './layers.js';
import { normalizePlayer } from './players.js';
import {
  executeBroadcastCommand,
  executeLayerCommand,
  executeSlomoCommand,
  getCommandDiagnostics
} from './commands.js';
import {
  ensureRconConnected,
  refreshPlayerList,
  refreshServerInfo
} from './rcon.js';
import { getSyntheticLobbyBuildId, getSyntheticLobbyOwningName } from './synthetic-lobby.js';

function buildDiagnosticPayload(server, state) {
  return {
    ...buildServerPayload(server, state),
    commandDiagnostics: getCommandDiagnostics(state)
  };
}

export function createBridgeHandler(server, { host, port, token, state }) {
  return async function handleBridgeRequest(req, res) {
    try {
      if (!isAuthorized(req, token)) {
        sendJson(res, 401, { error: 'Unauthorized' });
        return;
      }

      const url = new URL(req.url, `http://${req.headers.host || `${host}:${port}`}`);

      if (req.method === 'GET' && url.pathname === '/health') {
        sendJson(res, 200, buildDiagnosticPayload(server, state));
        return;
      }

      if (req.method === 'GET' && url.pathname === '/server') {
        await refreshServerInfo(server, state);
        sendJson(res, 200, buildDiagnosticPayload(server, state));
        return;
      }

      if (req.method === 'GET' && url.pathname === '/commands') {
        sendJson(res, 200, getCommandDiagnostics(state));
        return;
      }

      if (req.method === 'GET' && url.pathname === '/round/latest') {
        sendJson(res, 200, {
          round: state.latestScoreboard || state.latestRoundEnded
        });
        return;
      }

      if (req.method === 'GET' && url.pathname === '/round/best') {
        sendJson(res, 200, state.roundResults.getBestForContext({
          lobbyId: url.searchParams.get('lobbyId') || '',
          selectedLayer: url.searchParams.get('selectedLayer') || '',
          liveStartedAt: url.searchParams.get('liveStartedAt') || '',
          serverDetailsProvidedAt: url.searchParams.get('serverDetailsProvidedAt') || ''
        }));
        return;
      }

      if (req.method === 'POST' && url.pathname === '/match/context') {
        const payload = await readJsonBody(req);
        const context = state.roundResults.registerContext(payload);
        sendJson(res, 200, {
          ok: true,
          context
        });
        return;
      }

      if (req.method === 'GET' && url.pathname === '/round/scoreboard/latest') {
        sendJson(res, 200, {
          scoreboard: state.latestScoreboard
        });
        return;
      }

      if (req.method === 'GET' && url.pathname === '/players') {
        await refreshPlayerList(server, state);
        sendJson(res, 200, {
          players: server.players.map(normalizePlayer)
        });
        return;
      }

      if (req.method === 'GET' && url.pathname === '/layers') {
        sendJson(res, 200, {
          layers: await listLayers(url.searchParams.get('name') || '')
        });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/layer/change') {
        const payload = await readJsonBody(req);
        const result = await executeLayerCommand(server, state, {
          action: 'change',
          payload
        });
        sendJson(res, 200, result);
        return;
      }

      if (req.method === 'POST' && url.pathname === '/layer/next') {
        const payload = await readJsonBody(req);
        const result = await executeLayerCommand(server, state, {
          action: 'next',
          payload
        });
        sendJson(res, 200, result);
        return;
      }

      if (req.method === 'POST' && url.pathname === '/players/force-team-change') {
        const payload = await readJsonBody(req);
        const player = typeof payload.player === 'string' ? payload.player.trim() : '';
        if (!player) {
          throw new Error('player is required');
        }

        await ensureRconConnected(server, state);
        await server.rcon.switchTeam(player);
        await refreshPlayerList(server, state);

        sendJson(res, 200, {
          ok: true,
          player
        });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/players/kick') {
        const payload = await readJsonBody(req);
        const player = typeof payload.player === 'string' ? payload.player.trim() : '';
        const reason = typeof payload.reason === 'string' && payload.reason.trim()
          ? payload.reason.trim()
          : 'Match complete.';
        if (!player) {
          throw new Error('player is required');
        }

        await ensureRconConnected(server, state);
        await server.rcon.kick(player, reason);
        await refreshPlayerList(server, state);

        sendJson(res, 200, {
          ok: true,
          player,
          reason
        });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/match/end') {
        await ensureRconConnected(server, state);
        await server.rcon.endMatch();

        sendJson(res, 200, {
          ok: true,
          command: 'AdminEndMatch'
        });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/broadcast') {
        const payload = await readJsonBody(req);
        const result = await executeBroadcastCommand(server, state, payload.message);
        sendJson(res, 200, result);
        return;
      }

      if (req.method === 'POST' && url.pathname === '/rcon/slomo') {
        const payload = await readJsonBody(req);
        const result = await executeSlomoCommand(server, state, payload.value);
        sendJson(res, 200, result);
        return;
      }

      if (req.method === 'POST' && url.pathname === '/join/synthetic-lobby') {
        const payload = await readJsonBody(req);
        const sessionId = typeof payload.sessionId === 'string' ? payload.sessionId.trim() : '';
        if (!/^[0-9a-f]{32}$/i.test(sessionId)) {
          throw new Error('sessionId must be a 32-character hex string');
        }

        const result = await state.syntheticLobby.createJoinLink({
          sessionId: sessionId.toLowerCase(),
          buildId: typeof payload.buildId === 'string' ? payload.buildId.trim() : getSyntheticLobbyBuildId(),
          owningName: typeof payload.owningName === 'string' ? payload.owningName.trim() : getSyntheticLobbyOwningName(),
        });
        sendJson(res, 200, result);
        return;
      }

      sendJson(res, 404, { error: 'Not found' });
    } catch (error) {
      sendJson(res, error.statusCode || 400, { error: error.message });
    }
  };
}
