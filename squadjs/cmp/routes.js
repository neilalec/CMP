import { sendJson, isAuthorized, readJsonBody } from './http.js';
import { buildServerPayload, listLayers } from './layers.js';
import { normalizePlayer } from './players.js';
import {
  executeBroadcastCommand,
  executeLayerCommand,
  getCommandDiagnostics
} from './commands.js';
import {
  ensureRconConnected,
  refreshPlayerList,
  refreshServerInfo
} from './rcon.js';

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

      if (req.method === 'POST' && url.pathname === '/broadcast') {
        const payload = await readJsonBody(req);
        const result = await executeBroadcastCommand(server, state, payload.message);
        sendJson(res, 200, result);
        return;
      }

      sendJson(res, 404, { error: 'Not found' });
    } catch (error) {
      sendJson(res, error.statusCode || 400, { error: error.message });
    }
  };
}
