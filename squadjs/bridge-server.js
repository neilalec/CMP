import http from 'http';
import { Layers } from './squad-server/layers/index.js';

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body)
  });
  res.end(body);
}

function normalizePlayer(player) {
  return {
    name: player.name || null,
    steamID: player.steamID || null,
    eosID: player.eosID || null,
    playerID: player.playerID ?? null,
    teamID: player.teamID ?? null,
    squadID: player.squadID ?? null,
    role: player.role || null,
    isLeader: player.isLeader ?? null
  };
}

function buildLayerCommand(prefix, payload) {
  const layer = typeof payload.layer === 'string' ? payload.layer.trim() : '';
  const faction1 = typeof payload.faction1 === 'string' ? payload.faction1.trim() : '';
  const faction2 = typeof payload.faction2 === 'string' ? payload.faction2.trim() : '';

  if (!layer) {
    throw new Error('layer is required');
  }

  return [prefix, layer, faction1, faction2].filter(Boolean).join(' ');
}

async function readJsonBody(req) {
  const chunks = [];

  for await (const chunk of req) {
    chunks.push(chunk);
  }

  if (chunks.length === 0) {
    return {};
  }

  const raw = Buffer.concat(chunks).toString('utf8').trim();
  if (!raw) {
    return {};
  }

  try {
    return JSON.parse(raw);
  } catch {
    throw new Error('invalid JSON body');
  }
}

function isAuthorized(req, token) {
  if (!token) {
    return true;
  }

  const header = req.headers.authorization || '';
  return header === `Bearer ${token}`;
}

export function startBridgeServer(server, bridgeConfig = {}) {
  if (bridgeConfig.enabled === false) {
    return null;
  }

  const host = bridgeConfig.host || '127.0.0.1';
  const port = bridgeConfig.port || 3001;
  const token = bridgeConfig.token || '';

  const bridge = http.createServer(async (req, res) => {
    try {
      if (!isAuthorized(req, token)) {
        sendJson(res, 401, { error: 'Unauthorized' });
        return;
      }

      const url = new URL(req.url, `http://${req.headers.host || `${host}:${port}`}`);

      if (req.method === 'GET' && url.pathname === '/health') {
        sendJson(res, 200, {
          ok: true,
          serverName: server.serverName || null,
          currentLayer: server.currentLayer?.layerClassname || server.currentLayer?.name || null,
          nextLayer: server.nextLayer?.layerClassname || server.nextLayer?.name || null,
          playerCount: server.players.length
        });
        return;
      }

      if (req.method === 'GET' && url.pathname === '/players') {
        sendJson(res, 200, {
          players: server.players.map(normalizePlayer)
        });
        return;
      }

      if (req.method === 'GET' && url.pathname === '/layers') {
        await Layers.pull();
        const nameQuery = (url.searchParams.get('name') || '').trim().toLowerCase();
        const layers = Layers.layers
          .filter((layer) => !nameQuery || (layer.name || '').toLowerCase() === nameQuery)
          .map((layer) => ({
            name: layer.name || null,
            layerId: layer.layerid || null,
            classname: layer.classname || null
          }));
        sendJson(res, 200, { layers });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/layer/change') {
        const payload = await readJsonBody(req);
        const command = buildLayerCommand('AdminChangeLayer', payload);
        const response = await server.rcon.execute(command);

        sendJson(res, 200, {
          ok: true,
          command,
          response: response || null
        });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/layer/next') {
        const payload = await readJsonBody(req);
        const command = buildLayerCommand('AdminSetNextLayer', payload);
        const response = await server.rcon.execute(command);

        sendJson(res, 200, {
          ok: true,
          command,
          response: response || null
        });
        return;
      }

      if (req.method === 'POST' && url.pathname === '/broadcast') {
        const payload = await readJsonBody(req);
        const message = typeof payload.message === 'string' ? payload.message.trim() : '';
        if (!message) {
          throw new Error('message is required');
        }

        await server.rcon.broadcast(message);
        sendJson(res, 200, {
          ok: true,
          message
        });
        return;
      }

      sendJson(res, 404, { error: 'Not found' });
    } catch (error) {
      sendJson(res, 400, { error: error.message });
    }
  });

  bridge.listen(port, host, () => {
    console.log(`[CmpBridge] Listening on http://${host}:${port}`);
  });

  return bridge;
}
