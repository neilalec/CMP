function normalizeCompact(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9]/g, '');
}

function s3oTournamentDisplayMatches(layerValue, selectedLayer) {
  const selectedText = String(selectedLayer || '');
  if (!selectedText.startsWith('S3O_') || !selectedText.includes('_Tournament_')) {
    return false;
  }

  const layerText = String(layerValue || '');
  if (!layerText.toLowerCase().includes('s3o')) {
    return false;
  }

  const parts = selectedText.split('_');
  const mapName = parts[1] || '';
  const version = parts[parts.length - 1] || '';
  const layerCompact = normalizeCompact(layerText);
  return normalizeCompact(mapName) && normalizeCompact(version)
    && layerCompact.includes(normalizeCompact(mapName))
    && layerCompact.includes(normalizeCompact(version));
}

function layerMatches(layerValue, selectedLayer) {
  if (!layerValue || !selectedLayer) return false;
  return normalizeCompact(layerValue) === normalizeCompact(selectedLayer)
    || s3oTournamentDisplayMatches(layerValue, selectedLayer);
}

function getSideLayer(side) {
  return side && typeof side === 'object' ? side.layer : null;
}

function resultMatchesContext(result, context) {
  if (!result || !context) return false;

  const selectedLayer = context.selectedLayer || context.selectedMap || null;
  const resultLayers = [
    result.layer,
    getSideLayer(result.winner),
    getSideLayer(result.loser)
  ].filter(Boolean);

  const layerMatchesContext = selectedLayer
    ? resultLayers.some((layer) => layerMatches(layer, selectedLayer))
    : true;
  if (!layerMatchesContext && resultLayers.length > 0) {
    return false;
  }

  const contextStartedAt = Number(context.liveStartedAt || context.serverDetailsProvidedAt || 0);
  const observedAt = Number(result.observedAt || result.capturedAt || 0);
  if (contextStartedAt && observedAt && observedAt + 1 < contextStartedAt) {
    return false;
  }

  return true;
}

function getResultScore(result) {
  if (!result) return 0;
  if (result.resultQuality === 'complete' && !result.partial) return 300;
  if (result.winner && result.loser) return 250;
  if (result.winner || result.loser) return 150;
  if (result.roundStats?.players?.length) return 90;
  if (result.roundStats?.rawEvents?.length) return 70;
  return 10;
}

function getRoundKey(result) {
  return [
    result?.time || result?.endedAt || '',
    result?.layer || result?.winner?.layer || result?.loser?.layer || '',
    result?.winner?.team || '',
    result?.winner?.tickets || '',
    result?.loser?.team || '',
    result?.loser?.tickets || ''
  ].join('|') || `observed:${result?.observedAt || Date.now()}`;
}

function mergeResult(existingResult, nextResult) {
  if (!existingResult) return nextResult;
  const existingScore = getResultScore(existingResult);
  const nextScore = getResultScore(nextResult);
  if (nextScore < existingScore) {
    return {
      ...existingResult,
      supersededCandidates: [
        ...(existingResult.supersededCandidates || []),
        {
          observedAt: nextResult.observedAt,
          resultQuality: nextResult.resultQuality,
          partial: !!nextResult.partial,
          layer: nextResult.layer || null
        }
      ].slice(-10)
    };
  }

  return {
    ...existingResult,
    ...nextResult,
    roundAudit: nextResult.roundAudit || existingResult.roundAudit || null,
    roundStats: nextResult.roundStats || existingResult.roundStats || null,
    teams: nextResult.teams?.length ? nextResult.teams : existingResult.teams || []
  };
}

export function createRoundResultRegistry() {
  const contexts = new Map();
  const results = new Map();

  function registerContext(context = {}) {
    const lobbyId = String(context.lobbyId || context.lobby_id || '').trim();
    if (!lobbyId) {
      throw new Error('lobbyId is required');
    }
    const registeredAt = Date.now() / 1000;
    const normalizedContext = {
      ...context,
      lobbyId,
      selectedLayer: context.selectedLayer || context.selectedMap || null,
      registeredAt
    };
    contexts.set(lobbyId, normalizedContext);
    return normalizedContext;
  }

  function addResult(result) {
    if (!result) return null;
    const key = getRoundKey(result);
    const merged = mergeResult(results.get(key), result);
    results.set(key, merged);

    for (const [lobbyId, context] of contexts.entries()) {
      if (resultMatchesContext(merged, context)) {
        contexts.set(lobbyId, {
          ...context,
          bestRoundKey: key,
          bestRoundScore: getResultScore(merged)
        });
      }
    }

    while (results.size > 25) {
      const oldestKey = results.keys().next().value;
      results.delete(oldestKey);
    }

    return merged;
  }

  function getBestForContext(query = {}) {
    const lobbyId = String(query.lobbyId || query.lobby_id || '').trim();
    const context = lobbyId && contexts.has(lobbyId)
      ? { ...contexts.get(lobbyId), ...query, lobbyId }
      : {
          ...query,
          selectedLayer: query.selectedLayer || query.selectedMap || null
        };

    let best = null;
    let bestScore = -1;
    for (const result of results.values()) {
      if (!resultMatchesContext(result, context)) continue;
      const score = getResultScore(result);
      const observedAt = Number(result.observedAt || result.capturedAt || 0);
      const bestObservedAt = Number(best?.observedAt || best?.capturedAt || 0);
      if (score > bestScore || (score === bestScore && observedAt > bestObservedAt)) {
        best = result;
        bestScore = score;
      }
    }

    return {
      context,
      round: best,
      score: bestScore >= 0 ? bestScore : null,
      resultCount: results.size
    };
  }

  return {
    registerContext,
    addResult,
    getBestForContext,
    get contexts() {
      return Array.from(contexts.values());
    },
    get results() {
      return Array.from(results.values());
    }
  };
}
