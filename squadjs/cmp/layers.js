import { Layers } from '../squad-server/layers/index.js';
import { isHotdropLayer, listHotdropLayers } from './hotdrop-layers.js';

function layerInfo(layer) {
  if (!layer) return null;

  return {
    name: layer.name || null,
    layerId: layer.layerId || layer.layerid || null,
    layerClassname: layer.layerClassname || layer.classname || null,
    classname: layer.classname || layer.layerClassname || null
  };
}

export function buildServerPayload(server, state) {
  const rconLayerStatus = state.layerStatus || {};
  const currentLayerInfo = layerInfo(server.currentLayer);
  const nextLayerInfo = layerInfo(server.nextLayer);

  return {
    ok: true,
    serverName: server.serverName || null,
    currentLayer: rconLayerStatus.currentLayer || currentLayerInfo?.layerClassname || currentLayerInfo?.name || null,
    currentLevel: rconLayerStatus.currentLevel || null,
    currentLayerRaw: rconLayerStatus.currentLayer || null,
    currentLayerName: currentLayerInfo?.name || null,
    currentLayerClassname: currentLayerInfo?.layerClassname || null,
    currentLayerId: currentLayerInfo?.layerId || null,
    currentLayerInfo,
    nextLayer: rconLayerStatus.nextLayer || nextLayerInfo?.layerClassname || nextLayerInfo?.name || null,
    nextLevel: rconLayerStatus.nextLevel || null,
    nextLayerRaw: rconLayerStatus.nextLayer || null,
    nextLayerName: nextLayerInfo?.name || null,
    nextLayerClassname: nextLayerInfo?.layerClassname || null,
    nextLayerId: nextLayerInfo?.layerId || null,
    nextLayerInfo,
    playerCount: server.players.length,
    maxPlayers: server.publicSlots ?? null,
    publicQueue: server.publicQueue ?? null,
    reserveQueue: server.reserveQueue ?? null
  };
}

export async function listLayers(name = '') {
  const nameQuery = String(name || '').trim().toLowerCase();
  const hotdropLayers = listHotdropLayers();

  if (nameQuery && isHotdropLayer(name)) {
    return hotdropLayers.filter((layer) => layer.layerId.toLowerCase() === nameQuery);
  }

  await Layers.pull();

  const vanillaLayers = Layers.layers
    .filter((layer) => {
      if (!nameQuery) return true;
      const candidates = [
        (layer.name || '').toLowerCase(),
        (layer.layerid || '').toLowerCase(),
        (layer.classname || '').toLowerCase()
      ];
      return candidates.includes(nameQuery);
    })
    .map((layer) => ({
      name: layer.name || null,
      layerId: layer.layerid || null,
      classname: layer.classname || null,
      source: 'squad-wiki'
    }));

  if (nameQuery) {
    const matchingHotdropLayers = hotdropLayers.filter((layer) => {
      const candidates = [
        layer.name.toLowerCase(),
        layer.layerId.toLowerCase(),
        layer.classname.toLowerCase()
      ];
      return candidates.includes(nameQuery);
    });
    return [...matchingHotdropLayers, ...vanillaLayers];
  }

  return [...hotdropLayers, ...vanillaLayers];
}
