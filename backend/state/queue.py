from services.queue import build_queue_payload as build_queue_payload_service
from app_state import QUEUE_MODES


def _app():
    import app as backend_app
    return backend_app


def build_queue_payload(username=None, countdown=None, queue_mode=None):
    app = _app()
    from state.lobby import get_match_accept_payload

    return build_queue_payload_service(
        app.matchmaking_queue,
        app.user_has_steam_id,
        get_match_accept_payload,
        QUEUE_MODES,
        disabled_queue_modes=app.disabled_queue_modes,
        lobbies=app.lobbies,
        pending_match=app.pending_match,
        server_capacity=1,
        username=username,
        countdown=countdown,
        queue_mode=queue_mode
    )
