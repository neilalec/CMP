import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
const SteamUser = require('steam-user');
const SteamTotp = require('steam-totp');
const Schema = require('steam-user/protobufs/generated/_load.js');

const APP_ID = 393380;
const LOBBY_TYPE_PUBLIC = 2;
const LOBBY_FLAGS_DEFAULT = 0;
const LOBBY_TTL_MS = 10 * 60 * 1000;

function asTrimmed(value) {
  return String(value || '').trim();
}

function getEnv(name, fallback = '') {
  return asTrimmed(process.env[name] || fallback);
}

export function getSyntheticLobbyBuildId() {
  return getEnv('SYNTHETIC_LOBBY_BUILD_ID');
}

export function getSyntheticLobbyOwningName() {
  return getEnv('SYNTHETIC_LOBBY_OWNING_NAME', 'CMP');
}

function isSyntheticLobbyEnabled() {
  return getEnv('SYNTHETIC_LOBBY_ENABLED', '0') === '1';
}

function getSteamCredentials() {
  return {
    username: getEnv('STEAM_USERNAME'),
    password: getEnv('STEAM_PASSWORD'),
    sharedSecret: getEnv('STEAM_SHARED_SECRET'),
    guardCode: getEnv('STEAM_GUARD_CODE'),
  };
}

function ensureSyntheticLobbyConfig(buildId) {
  if (!isSyntheticLobbyEnabled()) {
    throw new Error('Synthetic lobby creation is disabled');
  }
  const credentials = getSteamCredentials();
  if (!credentials.username || !credentials.password) {
    throw new Error('Steam credentials are not configured for synthetic lobby creation');
  }
  if (!asTrimmed(buildId)) {
    throw new Error('Synthetic lobby build ID is not configured');
  }
  return credentials;
}

function encodeBinaryKv(rootKey, data) {
  const chunks = [Buffer.from([0]), Buffer.from(`${rootKey}\0`, 'utf8')];
  for (const [key, value] of Object.entries(data || {})) {
    chunks.push(Buffer.from([1]));
    chunks.push(Buffer.from(`${key}\0`, 'utf8'));
    chunks.push(Buffer.from(`${String(value)}\0`, 'utf8'));
  }
  chunks.push(Buffer.from([8, 8]));
  return Buffer.concat(chunks);
}

function buildLobbyMetadata({ sessionId, buildId, owningName }) {
  return {
    buildid: String(buildId),
    CONMETHOD: 'P2P',
    SESSIONFLAGS: '227',
    OWNINGNAME: owningName,
    RedpointEOSRoomId_s: `Session:${sessionId}`,
    RedpointEOSRoomNamespace_s: 'Synthetic',
  };
}

function createProtobufRequest(client, emsg, RequestProto, ResponseProto, body) {
  return new Promise((resolve, reject) => {
    try {
      const payload = RequestProto.encode(body).finish();
      client._send({ msg: emsg, proto: {} }, payload, (responseBody) => {
        try {
          const raw = Buffer.isBuffer(responseBody)
            ? responseBody
            : Buffer.from(responseBody?.toBuffer?.() || responseBody);
          resolve(ResponseProto.decode(raw));
        } catch (error) {
          reject(error);
        }
      });
    } catch (error) {
      reject(error);
    }
  });
}

export function createSyntheticLobbyManager() {
  let client = null;
  let loginPromise = null;
  let ready = false;
  const cache = new Map();

  async function ensureReady() {
    if (ready && client?.steamID) {
      return client;
    }
    if (loginPromise) {
      return loginPromise;
    }

    const credentials = ensureSyntheticLobbyConfig(getSyntheticLobbyBuildId());
    client = new SteamUser({
      autoRelogin: true,
      enablePicsCache: false,
      saveAppTickets: false,
      dataDirectory: null,
    });

    loginPromise = new Promise((resolve, reject) => {
      const fail = (error) => {
        ready = false;
        loginPromise = null;
        reject(error instanceof Error ? error : new Error(String(error)));
      };

      client.once('loggedOn', () => {
        ready = true;
        console.log('[CmpBridge] Synthetic lobby Steam client logged on');
        resolve(client);
      });

      client.on('error', (error) => {
        console.error('[CmpBridge] Synthetic lobby Steam client error', error?.message || String(error));
      });

      client.on('disconnected', (eresult, msg) => {
        ready = false;
        console.warn('[CmpBridge] Synthetic lobby Steam client disconnected', eresult, msg || '');
      });

      client.on('steamGuard', (domain, callback, lastCodeWrong) => {
        if (credentials.sharedSecret) {
          callback(SteamTotp.generateAuthCode(credentials.sharedSecret));
          return;
        }

        if (credentials.guardCode) {
          callback(credentials.guardCode);
          return;
        }

        fail(new Error(
          domain
            ? `Steam Guard code required for ${domain}; configure STEAM_SHARED_SECRET or STEAM_GUARD_CODE`
            : 'Steam Guard code required; configure STEAM_SHARED_SECRET or STEAM_GUARD_CODE'
        ));
      });

      try {
        client.logOn({
          accountName: credentials.username,
          password: credentials.password,
          twoFactorCode: credentials.sharedSecret ? SteamTotp.generateAuthCode(credentials.sharedSecret) : undefined,
          authCode: !credentials.sharedSecret && credentials.guardCode ? credentials.guardCode : undefined,
        });
      } catch (error) {
        fail(error);
      }
    });

    return loginPromise;
  }

  async function createJoinLink({ sessionId, buildId, owningName }) {
    const normalizedBuildId = asTrimmed(buildId);
    const normalizedOwningName = asTrimmed(owningName) || 'CMP';
    ensureSyntheticLobbyConfig(normalizedBuildId);
    const cacheKey = `${sessionId}:${normalizedBuildId}:${normalizedOwningName}`;
    const cached = cache.get(cacheKey);
    if (cached && (Date.now() - cached.createdAtMs) <= LOBBY_TTL_MS) {
      return {
        ok: true,
        cached: true,
        ...cached.payload,
      };
    }

    const activeClient = await ensureReady();
    const metadata = buildLobbyMetadata({
      sessionId,
      buildId: normalizedBuildId,
      owningName: normalizedOwningName,
    });
    const metadataBuffer = encodeBinaryKv('Lobby', metadata);

    const createResponse = await createProtobufRequest(
      activeClient,
      SteamUser.EMsg.ClientMMSCreateLobby,
      Schema.CMsgClientMMSCreateLobby,
      Schema.CMsgClientMMSCreateLobbyResponse,
      {
        app_id: APP_ID,
        max_members: 2,
        lobby_type: LOBBY_TYPE_PUBLIC,
        lobby_flags: LOBBY_FLAGS_DEFAULT,
        cell_id: activeClient.cellID || 0,
        metadata: metadataBuffer,
        persona_name_owner: normalizedOwningName,
      }
    );

    if (Number(createResponse.eresult || 0) !== SteamUser.EResult.OK) {
      throw new Error(
        `Steam lobby creation failed: ${SteamUser.EResult[createResponse.eresult] || createResponse.eresult}`
      );
    }

    const lobbyId = String(createResponse.steam_id_lobby || '').trim();
    if (!lobbyId) {
      throw new Error('Steam lobby creation did not return a lobby ID');
    }

    const setResponse = await createProtobufRequest(
      activeClient,
      SteamUser.EMsg.ClientMMSSetLobbyData,
      Schema.CMsgClientMMSSetLobbyData,
      Schema.CMsgClientMMSSetLobbyDataResponse,
      {
        app_id: APP_ID,
        steam_id_lobby: lobbyId,
        steam_id_member: '0',
        max_members: 2,
        lobby_type: LOBBY_TYPE_PUBLIC,
        lobby_flags: LOBBY_FLAGS_DEFAULT,
        metadata: metadataBuffer,
      }
    );

    if (Number(setResponse.eresult || 0) !== SteamUser.EResult.OK) {
      throw new Error(
        `Steam lobby metadata update failed: ${SteamUser.EResult[setResponse.eresult] || setResponse.eresult}`
      );
    }

    const payload = {
      lobbyId,
      joinUrl: `steam://joinlobby/${APP_ID}/${lobbyId}`,
      metadata,
      sessionId,
      buildId: normalizedBuildId,
      owningName: normalizedOwningName,
      createdAt: new Date().toISOString(),
    };
    cache.set(cacheKey, {
      createdAtMs: Date.now(),
      payload,
    });

    return {
      ok: true,
      cached: false,
      ...payload,
    };
  }

  function dispose() {
    if (!client) {
      return;
    }
    try {
      client.logOff();
    } catch {}
    client = null;
    ready = false;
    loginPromise = null;
  }

  return {
    createJoinLink,
    dispose,
  };
}
