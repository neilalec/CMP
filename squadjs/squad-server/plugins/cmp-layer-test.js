import BasePlugin from './base-plugin.js';

export default class CmpLayerTest extends BasePlugin {
  static get description() {
    return (
      'Provides simple in-game admin chat commands for testing SquadJS RCON layer changes. ' +
      'Use !cmpchange <LayerName> [Faction1] [Faction2] for an immediate change or ' +
      '!cmpnext <LayerName> [Faction1] [Faction2] to set the next layer.'
    );
  }

  static get defaultEnabled() {
    return false;
  }

  static get optionsSpecification() {
    return {
      changeCommand: {
        required: false,
        description: 'Chat command that immediately changes the current layer.',
        default: 'cmpchange'
      },
      nextCommand: {
        required: false,
        description: 'Chat command that sets the next layer.',
        default: 'cmpnext'
      },
      infoCommand: {
        required: false,
        description: 'Chat command that reports the current server and layer information.',
        default: 'cmpserver'
      }
    };
  }

  async mount() {
    this.onChangeCommand = this.onLayerCommand.bind(this, 'AdminChangeLayer');
    this.onNextCommand = this.onLayerCommand.bind(this, 'AdminSetNextLayer');
    this.onInfoCommand = this.onInfo.bind(this);

    this.server.on(`CHAT_COMMAND:${this.options.changeCommand.toLowerCase()}`, this.onChangeCommand);
    this.server.on(`CHAT_COMMAND:${this.options.nextCommand.toLowerCase()}`, this.onNextCommand);
    this.server.on(`CHAT_COMMAND:${this.options.infoCommand.toLowerCase()}`, this.onInfoCommand);
  }

  async unmount() {
    this.server.removeEventListener(
      `CHAT_COMMAND:${this.options.changeCommand.toLowerCase()}`,
      this.onChangeCommand
    );
    this.server.removeEventListener(
      `CHAT_COMMAND:${this.options.nextCommand.toLowerCase()}`,
      this.onNextCommand
    );
    this.server.removeEventListener(
      `CHAT_COMMAND:${this.options.infoCommand.toLowerCase()}`,
      this.onInfoCommand
    );
  }

  async onLayerCommand(rconCommand, data) {
    const args = (data.message || '').trim();
    if (!args) {
      await this.server.rcon.warn(
        data.eosID,
        `Usage: !${rconCommand === 'AdminChangeLayer' ? this.options.changeCommand : this.options.nextCommand} <LayerName> [Faction1] [Faction2]`
      );
      return;
    }

    const command = `${rconCommand} ${args}`;
    this.verbose(1, `Executing layer test command: ${command}`);

    try {
      const result = await this.server.rcon.execute(command);
      await this.server.rcon.warn(
        data.eosID,
        `${rconCommand} sent. Check the server state/logs to confirm.`
      );
      if (result) {
        this.verbose(1, `RCON response: ${result}`);
      }
    } catch (error) {
      await this.server.rcon.warn(data.eosID, `Layer command failed: ${error.message}`);
      throw error;
    }
  }

  async onInfo(data) {
    const serverName = this.server.serverName || 'Unknown Server';
    const currentLayer =
      this.server.currentLayer?.layerClassname ||
      this.server.currentLayer?.name ||
      'Unknown Layer';
    const nextLayer =
      this.server.nextLayer?.layerClassname ||
      this.server.nextLayer?.name ||
      'Unknown Next Layer';

    await this.server.rcon.warn(
      data.eosID,
      `${serverName} | Current: ${currentLayer} | Next: ${nextLayer}`
    );
  }
}
