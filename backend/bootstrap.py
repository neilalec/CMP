import signal
import sys


def signal_handler(app_state, save_queue, save_runtime_state=None):
    def _handler(sig, frame):
        print('\nShutting down server...')

        try:
            for sid in app_state.socketio.server.sockets:
                try:
                    app_state.socketio.server.disconnect(sid)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            save_queue()
        except Exception:
            pass
        try:
            if save_runtime_state:
                save_runtime_state()
        except Exception:
            pass

        print('Shutdown complete')
        sys.exit(0)

    return _handler


def start_server(
    *,
    app_state,
    cleanup_on_start,
    start_periodic_tasks,
    save_queue,
    save_runtime_state=None,
    host,
    port,
    logger
):
    cleanup_on_start()
    start_periodic_tasks()
    logger.info("Starting server...")

    handler = signal_handler(app_state, save_queue, save_runtime_state)
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    try:
        app_state.socketio.run(
            app_state.app,
            debug=False,
            host=host,
            port=port,
            use_reloader=False,
            log_output=True,
            allow_unsafe_werkzeug=True,
        )
    except KeyboardInterrupt:
        handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"Server error: {e}")
        handler(signal.SIGINT, None)
    finally:
        logger.info("Server stopped")
