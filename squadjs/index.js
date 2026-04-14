import SquadServerFactory from 'squad-server/factory';
import printLogo from 'squad-server/logo';
import { startBridgeServer } from './bridge-server.js';

async function main() {
  await printLogo();

  const config = process.env.config;
  const configPath = process.argv[2];
  if (config && configPath) throw new Error('Cannot accept both a config and config path.');

  const rawConfig = config
    ? SquadServerFactory.parseConfig(config)
    : SquadServerFactory.parseConfig(
        SquadServerFactory.readConfigFile(configPath || './config.json')
      );

  // create a SquadServer instance
  const server = await SquadServerFactory.buildFromConfig(rawConfig);

  // watch the server
  await server.watch();

  // now mount the plugins
  await Promise.all(server.plugins.map(async (plugin) => await plugin.mount()));

  startBridgeServer(server, rawConfig.bridge || {});
}

main();
