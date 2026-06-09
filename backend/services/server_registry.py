import json
import time
from urllib.parse import quote, urlparse

from itsdangerous import BadSignature, URLSafeSerializer

from services.bridge import (
    BridgeUnavailable,
    fetch_all_layers,
    fetch_connected_server_players,
    fetch_latest_round_result,
    fetch_server_info,
    get_bridge_health,
    squadjs_bridge_request,
)


def _to_json(value):
    return json.dumps(value or {}, ensure_ascii=True, sort_keys=True)


def _from_json(value, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _token_serializer(secret_key):
    return URLSafeSerializer(str(secret_key or 'cmp-dev-secret'), salt='server-bridge-token')


def encrypt_bridge_token(token, secret_key):
    token = str(token or '').strip()
    if not token:
        return ''
    return _token_serializer(secret_key).dumps(token)


def decrypt_bridge_token(token_encrypted, secret_key):
    token_encrypted = str(token_encrypted or '').strip()
    if not token_encrypted:
        return ''
    try:
        return str(_token_serializer(secret_key).loads(token_encrypted) or '')
    except BadSignature:
        return ''


def mask_secret(value):
    value = str(value or '')
    if len(value) <= 4:
        return '****' if value else ''
    return f"{value[:2]}{'*' * max(4, len(value) - 4)}{value[-2:]}"


def validate_bridge_url(bridge_url):
    parsed = urlparse(str(bridge_url or '').strip())
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc:
        raise ValueError('Bridge URL must be a valid http or https URL')
    return parsed.geturl().rstrip('/')


def init_server_registry_tables(get_db_connection):
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS servers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                owner_label TEXT NOT NULL DEFAULT '',
                steam_lobby_id TEXT NOT NULL DEFAULT '',
                connect_address TEXT NOT NULL DEFAULT '',
                join_password TEXT NOT NULL DEFAULT '',
                bridge_url TEXT NOT NULL,
                bridge_token_encrypted TEXT NOT NULL DEFAULT '',
                submitted_by TEXT NOT NULL DEFAULT '',
                approved_by TEXT NOT NULL DEFAULT '',
                approved_at REAL,
                status TEXT NOT NULL DEFAULT 'pending',
                enabled INTEGER NOT NULL DEFAULT 0,
                current_lobby_id TEXT,
                reserved_at REAL,
                last_health_check_at REAL,
                last_health_status TEXT,
                last_health_error TEXT,
                cap_players INTEGER NOT NULL DEFAULT 0,
                cap_layer_change INTEGER NOT NULL DEFAULT 0,
                cap_broadcast INTEGER NOT NULL DEFAULT 0,
                cap_round_result INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL,
                result TEXT NOT NULL,
                error TEXT,
                health_payload_json TEXT NOT NULL DEFAULT '{}',
                checked_at REAL NOT NULL,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS server_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id INTEGER NOT NULL,
                lobby_id TEXT NOT NULL,
                state TEXT NOT NULL,
                reserved_at REAL NOT NULL,
                released_at REAL,
                release_reason TEXT,
                FOREIGN KEY (server_id) REFERENCES servers(id)
            )
            """
        )
        columns = {row['name'] for row in conn.execute("PRAGMA table_info(completed_matches)").fetchall()}
        if columns and 'server_id' not in columns:
            conn.execute("ALTER TABLE completed_matches ADD COLUMN server_id INTEGER")
        server_columns = {row['name'] for row in conn.execute("PRAGMA table_info(servers)").fetchall()}
        if 'submitted_by' not in server_columns:
            conn.execute("ALTER TABLE servers ADD COLUMN submitted_by TEXT NOT NULL DEFAULT ''")
        if 'approved_by' not in server_columns:
            conn.execute("ALTER TABLE servers ADD COLUMN approved_by TEXT NOT NULL DEFAULT ''")
        if 'approved_at' not in server_columns:
            conn.execute("ALTER TABLE servers ADD COLUMN approved_at REAL")
        if 'steam_lobby_id' not in server_columns:
            conn.execute("ALTER TABLE servers ADD COLUMN steam_lobby_id TEXT NOT NULL DEFAULT ''")
        conn.commit()


def slugify_server_name(display_name):
    text = ''.join(ch.lower() if ch.isalnum() else '-' for ch in str(display_name or '').strip())
    parts = [part for part in text.split('-') if part]
    slug = '-'.join(parts)[:80]
    return slug or f"server-{int(time.time())}"


def _row_to_server_payload(row, secret_key=None, include_secret=False):
    if not row:
        return None
    payload = {
        'id': row['id'],
        'slug': row['slug'],
        'display_name': row['display_name'],
        'owner_label': row['owner_label'],
        'steam_lobby_id': row['steam_lobby_id'],
        'connect_address': row['connect_address'],
        'join_password': row['join_password'],
        'bridge_url': row['bridge_url'],
        'bridge_token_masked': mask_secret(decrypt_bridge_token(row['bridge_token_encrypted'], secret_key)),
        'submitted_by': row['submitted_by'],
        'approved_by': row['approved_by'],
        'approved_at': row['approved_at'],
        'status': row['status'],
        'enabled': bool(row['enabled']),
        'current_lobby_id': row['current_lobby_id'],
        'reserved_at': row['reserved_at'],
        'last_health_check_at': row['last_health_check_at'],
        'last_health_status': row['last_health_status'],
        'last_health_error': row['last_health_error'],
        'capabilities': {
            'players': bool(row['cap_players']),
            'layer_change': bool(row['cap_layer_change']),
            'broadcast': bool(row['cap_broadcast']),
            'round_result': bool(row['cap_round_result']),
        },
        'metadata': _from_json(row['metadata_json'], {}),
        'created_at': row['created_at'],
        'updated_at': row['updated_at'],
    }
    if include_secret:
        payload['bridge_token'] = decrypt_bridge_token(row['bridge_token_encrypted'], secret_key)
    return payload


def list_servers(get_db_connection, secret_key):
    with get_db_connection() as conn:
        rows = conn.execute("SELECT * FROM servers ORDER BY enabled DESC, display_name ASC").fetchall()
    return [_row_to_server_payload(row, secret_key) for row in rows]


def get_server_by_id(get_db_connection, server_id, secret_key, include_secret=False):
    with get_db_connection() as conn:
        row = conn.execute("SELECT * FROM servers WHERE id = ?", (server_id,)).fetchone()
    return _row_to_server_payload(row, secret_key, include_secret=include_secret)


def create_server(get_db_connection, secret_key, payload, submitted_by=''):
    display_name = str(payload.get('display_name') or '').strip()
    if not display_name:
        raise ValueError('display_name is required')
    bridge_url = validate_bridge_url(payload.get('bridge_url'))
    now = time.time()
    slug = slugify_server_name(display_name)
    bridge_token_encrypted = encrypt_bridge_token(payload.get('bridge_token'), secret_key)

    with get_db_connection() as conn:
        existing = conn.execute("SELECT 1 FROM servers WHERE slug = ?", (slug,)).fetchone()
        if existing:
            slug = f"{slug}-{int(now)}"
        cursor = conn.execute(
            """
            INSERT INTO servers (
                slug, display_name, owner_label, connect_address, join_password,
                steam_lobby_id, bridge_url, bridge_token_encrypted, submitted_by, approved_by, approved_at,
                status, enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '', NULL, 'pending', 0, ?, ?)
            """,
            (
                slug,
                display_name,
                str(payload.get('owner_label') or '').strip(),
                str(payload.get('connect_address') or '').strip(),
                str(payload.get('join_password') or '').strip(),
                str(payload.get('steam_lobby_id') or '').strip(),
                bridge_url,
                bridge_token_encrypted,
                str(submitted_by or '').strip(),
                now,
                now,
            )
        )
        conn.commit()
        server_id = cursor.lastrowid
    return get_server_by_id(get_db_connection, server_id, secret_key)


def update_server_record(
    get_db_connection,
    secret_key,
    server_id,
    *,
    status=None,
    enabled=None,
    current_lobby_id=None,
    reserved_at=None,
    last_health_check_at=None,
    last_health_status=None,
    last_health_error=None,
    submitted_by=None,
    approved_by=None,
    approved_at=None,
    capabilities=None,
    metadata=None,
):
    updates = []
    values = []
    if status is not None:
        updates.append("status = ?")
        values.append(status)
    if enabled is not None:
        updates.append("enabled = ?")
        values.append(1 if enabled else 0)
    if current_lobby_id is not None:
        updates.append("current_lobby_id = ?")
        values.append(current_lobby_id)
    if reserved_at is not None:
        updates.append("reserved_at = ?")
        values.append(reserved_at)
    if last_health_check_at is not None:
        updates.append("last_health_check_at = ?")
        values.append(last_health_check_at)
    if last_health_status is not None:
        updates.append("last_health_status = ?")
        values.append(last_health_status)
    if last_health_error is not None:
        updates.append("last_health_error = ?")
        values.append(last_health_error)
    if submitted_by is not None:
        updates.append("submitted_by = ?")
        values.append(submitted_by)
    if approved_by is not None:
        updates.append("approved_by = ?")
        values.append(approved_by)
    if approved_at is not None:
        updates.append("approved_at = ?")
        values.append(approved_at)
    if capabilities is not None:
        updates.extend([
            "cap_players = ?",
            "cap_layer_change = ?",
            "cap_broadcast = ?",
            "cap_round_result = ?",
        ])
        values.extend([
            1 if capabilities.get('players') else 0,
            1 if capabilities.get('layer_change') else 0,
            1 if capabilities.get('broadcast') else 0,
            1 if capabilities.get('round_result') else 0,
        ])
    if metadata is not None:
        updates.append("metadata_json = ?")
        values.append(_to_json(metadata))
    updates.append("updated_at = ?")
    values.append(time.time())
    values.append(server_id)
    with get_db_connection() as conn:
        conn.execute(f"UPDATE servers SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
    return get_server_by_id(get_db_connection, server_id, secret_key)


def record_server_health_check(get_db_connection, server_id, result, error_message, health_payload):
    checked_at = time.time()
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO server_health_checks (server_id, result, error, health_payload_json, checked_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (server_id, result, error_message, _to_json(health_payload), checked_at)
        )
        conn.commit()
    return checked_at


def build_bridge_request_for_server(server_record):
    bridge_url = validate_bridge_url(server_record.get('bridge_url'))
    bridge_token = str(server_record.get('bridge_token') or '').strip()

    def request(path, method='GET', payload=None, timeout=5):
        return squadjs_bridge_request(
            path=path,
            bridge_url=bridge_url,
            bridge_token=bridge_token,
            payload=payload,
            method=method,
            timeout=timeout,
        )

    return request


def test_server_connection(server_payload):
    bridge_url = validate_bridge_url(server_payload.get('bridge_url'))
    bridge_token = str(server_payload.get('bridge_token') or '').strip()

    def bridge_request(path, method='GET', payload=None, timeout=5):
        return squadjs_bridge_request(
            path=path,
            bridge_url=bridge_url,
            bridge_token=bridge_token,
            payload=payload,
            method=method,
            timeout=timeout,
        )

    warnings = []
    bridge_health = get_bridge_health(bridge_request, bridge_url)
    if not bridge_health.get('ok'):
        raise BridgeUnavailable(bridge_health.get('error') or 'Bridge health check failed')

    server_info = fetch_server_info(bridge_request)
    players = fetch_connected_server_players(bridge_request)
    capabilities = {
        'players': isinstance(players, list),
        'layer_change': False,
        'broadcast': True,
        'round_result': False,
    }

    try:
        layers = fetch_all_layers(bridge_request)
        capabilities['layer_change'] = isinstance(layers, list)
        if not capabilities['layer_change']:
            warnings.append('Layer listing is unavailable.')
    except Exception as error:
        layers = []
        warnings.append(str(error))

    try:
        round_result = fetch_latest_round_result(bridge_request)
        capabilities['round_result'] = True
    except Exception as error:
        round_result = None
        warnings.append(f'Round result unavailable: {error}')

    result = {
        'bridgeReachable': True,
        'bridge': bridge_health,
        'serverInfo': server_info,
        'playerCount': len(players),
        'capabilities': capabilities,
        'warnings': warnings,
        'roundResult': round_result,
    }
    return result


def run_server_health_check(get_db_connection, secret_key, server_id):
    server = get_server_by_id(get_db_connection, server_id, secret_key, include_secret=True)
    if not server:
        raise ValueError('Server not found')

    error_message = None
    try:
        result = test_server_connection(server)
        status = 'healthy' if all(result['capabilities'].values()) else 'degraded'
    except Exception as error:
        result = {
            'bridgeReachable': False,
            'capabilities': {
                'players': False,
                'layer_change': False,
                'broadcast': False,
                'round_result': False,
            },
            'warnings': [],
        }
        status = 'offline'
        error_message = str(error)

    checked_at = record_server_health_check(get_db_connection, server_id, status, error_message, result)
    updated = update_server_record(
        get_db_connection,
        secret_key,
        server_id,
        status=status,
        last_health_check_at=checked_at,
        last_health_status=status,
        last_health_error=error_message,
        capabilities=result.get('capabilities') or {},
        metadata=result,
    )
    return updated, result


def set_server_enabled(get_db_connection, secret_key, server_id, enabled):
    server = get_server_by_id(get_db_connection, server_id, secret_key)
    if not server:
        raise ValueError('Server not found')
    if enabled and server.get('status') == 'pending':
        raise ValueError('Server must be approved before it can be enabled')
    if enabled and server.get('last_health_status') not in {'healthy', 'degraded'}:
        raise ValueError('Run a successful health check before enabling this server')
    status = server.get('status')
    if enabled and status == 'offline':
        raise ValueError('Offline servers cannot be enabled')
    if not enabled and server.get('current_lobby_id'):
        raise ValueError('Cannot disable a server that is currently allocated to a lobby')
    return update_server_record(
        get_db_connection,
        secret_key,
        server_id,
        enabled=enabled,
        status=('disabled' if not enabled else server.get('last_health_status') or 'healthy')
    )


def approve_server(get_db_connection, secret_key, server_id, approved_by):
    server = get_server_by_id(get_db_connection, server_id, secret_key)
    if not server:
        raise ValueError('Server not found')
    if server.get('current_lobby_id'):
        raise ValueError('Cannot change approval while server is allocated')
    return update_server_record(
        get_db_connection,
        secret_key,
        server_id,
        status='approved',
        approved_by=str(approved_by or '').strip(),
        approved_at=time.time(),
    )


def list_available_servers(get_db_connection, secret_key):
    return [
        server for server in list_servers(get_db_connection, secret_key)
        if server.get('enabled') and server.get('status') in {'healthy', 'degraded', 'approved'} and not server.get('current_lobby_id')
    ]


def get_server_pool_capacity(get_db_connection, secret_key):
    servers = list_servers(get_db_connection, secret_key)
    if not servers:
        return 1
    capacity = len([
        server for server in servers
        if server.get('enabled') and server.get('status') in {'healthy', 'degraded', 'approved', 'reserved'}
    ])
    return max(0, capacity)


def allocate_server_for_lobby(get_db_connection, secret_key, lobby_id):
    available = list_available_servers(get_db_connection, secret_key)
    if not available:
        return None
    server = available[0]
    reserved_at = time.time()
    updated = update_server_record(
        get_db_connection,
        secret_key,
        server['id'],
        status='reserved',
        current_lobby_id=lobby_id,
        reserved_at=reserved_at,
    )
    with get_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO server_allocations (server_id, lobby_id, state, reserved_at)
            VALUES (?, ?, 'reserved', ?)
            """,
            (server['id'], lobby_id, reserved_at)
        )
        conn.commit()
    return updated


def release_server_allocation(get_db_connection, secret_key, lobby_id, reason='released'):
    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT * FROM servers WHERE current_lobby_id = ?",
            (lobby_id,)
        ).fetchone()
        if not row:
            return None
        server_id = row['id']
        release_time = time.time()
        conn.execute(
            """
            UPDATE server_allocations
            SET state = 'released', released_at = ?, release_reason = ?
            WHERE server_id = ? AND lobby_id = ? AND state = 'reserved'
            """,
            (release_time, reason, server_id, lobby_id)
        )
        conn.commit()
    status = row['last_health_status'] or 'healthy'
    return update_server_record(
        get_db_connection,
        secret_key,
        server_id,
        status=status if row['enabled'] else 'disabled',
        current_lobby_id='',
        reserved_at=0,
    )


def build_squad_join_url(connect_address, join_password=''):
    connect_address = str(connect_address or '').strip()
    join_password = str(join_password or '').strip()
    if not connect_address:
        return ''
    command = f"+connect {connect_address}"
    if join_password:
        command = f"{command} +password {join_password}"
    return f"steam://run/393380//{quote(command, safe='+')}"


def build_steam_lobby_join_url(steam_lobby_id):
    steam_lobby_id = str(steam_lobby_id or '').strip()
    if not steam_lobby_id:
        return ''
    return f"steam://joinlobby/393380/{steam_lobby_id}"
