import http from 'http';

import { createBridgeHandler } from './cmp/routes.js';
import { createBridgeState } from './cmp/state.js';

export function startBridgeServer(server, bridgeConfig = {}) {
  if (bridgeConfig.enabled === false) {
    return null;
  }

  const host = bridgeConfig.host || '127.0.0.1';
  const port = bridgeConfig.port || 3001;
  const token = bridgeConfig.token || '';
  const state = createBridgeState(server);

  const bridge = http.createServer(createBridgeHandler(server, {
    host,
    port,
    token,
    state
  }));

  bridge.on('close', () => {
    state.dispose();
  });

  bridge.listen(port, host, () => {
    console.log(`[CmpBridge] Listening on http://${host}:${port}`);
  });

  return bridge;
}
