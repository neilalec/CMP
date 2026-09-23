"""One bounded Eventlet-compatible worker for allocated WARDOGS lobby reads."""

from __future__ import annotations

from datetime import datetime, timezone

from services.game_server_adapter import AdapterError
from services.wardogs_lobby import (
    clear_wardogs_observation, get_wardogs_lobby, mark_wardogs_observation_error,
    observe_wardogs_lobby, prune_wardogs_observations,
    wardogs_observation_signature,
)


POLL_INTERVAL_SECONDS = 20
FRESHNESS_EMIT_SECONDS = 60
WARDOGS_LOBBY_UPDATE_EVENT = 'wardogs_lobby_update'


def wardogs_lobby_room(lobby_id):
    return f'wardogs:{lobby_id}'


class WardogsLivePoller:
    """Scan durable allocation state each cycle; never create a task per lobby."""

    def __init__(self, *, socketio, get_db_connection, get_server_by_id,
                 adapter_factory, logger, interval=POLL_INTERVAL_SECONDS,
                 now=None):
        self.socketio = socketio
        self.get_db_connection = get_db_connection
        self.get_server_by_id = get_server_by_id
        self.adapter_factory = adapter_factory
        self.logger = logger
        self.interval = interval
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._running = False
        self._last_emitted = {}

    def _allocated(self):
        with self.get_db_connection() as conn:
            rows = conn.execute("""
                SELECT l.lobby_id, s.id AS server_id
                FROM wardogs_lobbies AS l
                JOIN servers AS s ON s.current_lobby_id=l.lobby_id
                WHERE s.game_type='wardogs'
                ORDER BY l.lobby_id
            """).fetchall()
        return [(row['lobby_id'], row['server_id']) for row in rows]

    def _eligible(self, lobby_id, server_id):
        try:
            lobby = get_wardogs_lobby(self.get_db_connection, lobby_id)
            server = self.get_server_by_id(server_id)
        except (ValueError, KeyError):
            return None
        if (not lobby or lobby.get('serverId') != server_id or not server
                or server.get('game_type') != 'wardogs'
                or server.get('current_lobby_id') != lobby_id):
            return None
        return lobby, server

    def poll_once(self):
        """Read only status/players, then notify subscribed viewers of changes."""
        allocated = self._allocated()
        eligible_keys = set()
        for lobby_id, server_id in allocated:
            association = self._eligible(lobby_id, server_id)
            if association is None:
                continue
            lobby, server = association
            key = (lobby_id, server_id)
            eligible_keys.add(key)
            before = wardogs_observation_signature(lobby)
            now = self.now()
            try:
                adapter = self.adapter_factory(server)
                observe_wardogs_lobby(lobby, adapter, now=now)
            except AdapterError:
                mark_wardogs_observation_error(lobby, now=now)
            except Exception:
                # Do not log remote exception text: it may contain an admin URL.
                self.logger.warning('WARDOGS observation failed for lobby %s', lobby_id)
                mark_wardogs_observation_error(lobby, now=now)
            if self._eligible(lobby_id, server_id) is None:
                clear_wardogs_observation(lobby_id, server_id)
                continue
            after = wardogs_observation_signature(lobby)
            last_emit = self._last_emitted.get(key)
            if after != before or last_emit is None or (now - last_emit).total_seconds() >= FRESHNESS_EMIT_SECONDS:
                self.socketio.emit(WARDOGS_LOBBY_UPDATE_EVENT, {'lobbyId': lobby_id},
                                   room=wardogs_lobby_room(lobby_id))
                self._last_emitted[key] = now
        prune_wardogs_observations(eligible_keys)
        for key in tuple(self._last_emitted):
            if key not in eligible_keys:
                self._last_emitted.pop(key, None)

    def run(self):
        """Called once from the existing startup task manager."""
        if self._running:
            return
        self._running = True
        try:
            while True:
                try:
                    self.poll_once()
                except Exception:
                    self.logger.warning('WARDOGS observation cycle failed')
                self.socketio.sleep(self.interval)
        finally:
            self._running = False
