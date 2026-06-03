import time


def _app():
    import app as backend_app
    return backend_app


def is_countdown_paused():
    app = _app()
    with app.countdown_pause_lock:
        return app.countdown_paused


def set_countdown_paused(value):
    app = _app()
    with app.countdown_pause_lock:
        app.countdown_paused = bool(value)
        return app.countdown_paused


def pause_aware_sleep(seconds):
    app = _app()
    remaining = seconds
    while remaining > 0:
        if is_countdown_paused():
            app.eventlet.sleep(0.2)
            continue
        step = 0.2 if remaining > 0.2 else remaining
        app.eventlet.sleep(step)
        remaining -= step


def with_retry(max_attempts=3):
    def decorator(func):
        def wrapper(*args, **kwargs):
            app = _app()
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    app.logger.error(f"Attempt {attempts} failed: {str(e)}")
                    if attempts == max_attempts:
                        raise
                    time.sleep(0.5)
            return None
        return wrapper
    return decorator
