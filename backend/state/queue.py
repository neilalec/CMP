from services.queue import build_queue_payload as build_queue_payload_service


def _app():
    import app as backend_app
    return backend_app


def build_queue_payload(username=None, countdown=None):
    app = _app()
    from state.lobby import get_match_accept_payload

    return build_queue_payload_service(
        app.matchmaking_queue,
        app.user_has_steam_id,
        get_match_accept_payload,
        username=username,
        countdown=countdown
    )
