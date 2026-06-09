import { startBridgeServer } from '../../bridge-server.js';

import BasePlugin from './base-plugin.js';

export default class CmpBridge extends BasePlugin {
  static get description() {
    return 'Provides the CMP HTTP bridge for player presence, layer control, server status, and round results.';
  }

  static get defaultEnabled() {
    return false;
  }

  static get optionsSpecification() {
    return {
      host: {
        required: false,
        description: 'Host/interface for the CMP bridge HTTP server.',
        default: '127.0.0.1'
      },
      port: {
        required: false,
        description: 'Port for the CMP bridge HTTP server.',
        default: 3001
      },
      token: {
        required: false,
        description: 'Optional bearer token required by CMP backend bridge requests.',
        default: ''
      }
    };
  }

  async mount() {
    this.bridgeServer = startBridgeServer(this.server, {
      enabled: true,
      host: this.options.host,
      port: this.options.port,
      token: this.options.token
    });
  }

  async unmount() {
    if (!this.bridgeServer) return;

    await new Promise((resolve, reject) => {
      this.bridgeServer.close((error) => {
        if (error) {
          reject(error);
          return;
        }
        resolve();
      });
    });

    this.bridgeServer = null;
  }
}
