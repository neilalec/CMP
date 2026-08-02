import { Layers } from '../squad-server/layers/index.js';
import { isHotdropLayer, listHotdropLayers } from './hotdrop-layers.js';

function layerInfo(layer) {
  if (!layer) return null;

  return {
    name: layer.name || null,
    layerId: layer.layerId || layer.layerid || null,
    layerClassname: layer.layerClassname || layer.classname || null,
    classname: layer.classname || layer.layerClassname || null,
    teams: Array.isArray(layer.teams)
      ? layer.teams.map((team, index) => ({
        key: `team${index + 1}`,
        faction: team?.faction || null,
        name: team?.name || null
      }))
      : []
  };
}

function extractSessionCandidates(rawServerInfo) {
  const raw = rawServerInfo && typeof rawServerInfo === 'object' ? rawServerInfo : {};
  const pattern = /(redpoint|eos|session|lobby)/i;

  return Object.entries(raw)
    .map(([key, value]) => ({
      key,
      value: value == null ? '' : String(value)
    }))
    .filter(({ key, value }) => pattern.test(key) || pattern.test(value) || value.includes('Session:'));
}

function cleanServerInfoValue(value) {
  if (value == null) return null;
  const text = String(value).trim();
  return text || null;
}

function extractServerInfoTeams(server) {
  const raw = server.serverInfoRaw && typeof server.serverInfoRaw === 'object'
    ? server.serverInfoRaw
    : {};

  return {
    teamOne: cleanServerInfoValue(server.teamOne),
    teamTwo: cleanServerInfoValue(server.teamTwo),
    rawTeamOne: cleanServerInfoValue(raw.TeamOne_s),
    rawTeamTwo: cleanServerInfoValue(raw.TeamTwo_s)
  };
}

function extractSquadTeamNames(server) {
  const teams = {};
  for (const squad of Array.isArray(server.squads) ? server.squads : []) {
    const teamID = Number(squad?.teamID);
    const teamName = cleanServerInfoValue(squad?.teamName);
    if ((teamID === 1 || teamID === 2) && teamName) {
      teams[`team${teamID}`] = teamName;
    }
  }
  return teams;
}

function serializeDateTime(value) {
  if (!value) return null;
  if (typeof value.toISOString === 'function') return value.toISOString();
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

export function buildServerPayload(server, state) {
  const rconLayerStatus = state.layerStatus || {};
  const currentLayerInfo = layerInfo(server.currentLayer);
  const nextLayerInfo = layerInfo(server.nextLayer);
  const rawServerInfoKeys = Array.isArray(server.serverInfoRawKeys) ? server.serverInfoRawKeys : [];
  const sessionCandidates = extractSessionCandidates(server.serverInfoRaw);
  const serverInfoTeams = extractServerInfoTeams(server);
  const squadTeamNames = extractSquadTeamNames(server);

  return {
    ok: true,
    serverId: server.id ?? server.options?.id ?? null,
    serverName: server.serverName || null,
    host: server.options?.host || null,
    queryPort: server.options?.queryPort ?? null,
    rconHost: server.options?.rconHost || server.options?.host || null,
    rconPort: server.options?.rconPort ?? null,
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
    reserveQueue: server.reserveQueue ?? null,
    gameVersion: server.gameVersion || null,
    matchTimeout: server.matchTimeout ?? null,
    matchStartTime: serializeDateTime(server.matchStartTime),
    playtimeSeconds: Number.isFinite(Number(server.serverInfoRaw?.PLAYTIME_I))
      ? Number(server.serverInfoRaw.PLAYTIME_I)
      : null,
    serverInfoTeams,
    squadTeamNames,
    rawServerInfoKeys,
    rawServerInfoKeyCount: rawServerInfoKeys.length,
    sessionCandidates
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
      teams: Array.isArray(layer.teams)
        ? layer.teams.map((team, index) => ({
          key: `team${index + 1}`,
          faction: team?.faction || null,
          name: team?.name || null
        }))
        : [],
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
