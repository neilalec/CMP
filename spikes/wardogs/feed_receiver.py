"""Optional WARDOGS push-feed capture endpoint for a later real-server trial."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def handler_for(token: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_POST(self):
            if self.path != "/api/ingest/events":
                return self.reply(404)
            if self.headers.get("Authorization") != f"Bearer {token}":
                return self.reply(401)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 1_048_576:
                    return self.reply(413)
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict) or not isinstance(payload.get("events"), list):
                    return self.reply(400)
            except (ValueError, json.JSONDecodeError):
                return self.reply(400)
            print(json.dumps(payload, separators=(",", ":")), flush=True)
            self.reply(200)

        def reply(self, status):
            self.send_response(status)
            self.send_header("Content-Length", "0")
            self.end_headers()

    return Handler


def main():
    token = os.getenv("WD_FEED_TOKEN")
    if not token:
        raise SystemExit("Set WD_FEED_TOKEN")
    host = os.getenv("WD_FEED_BIND", "127.0.0.1")
    port = int(os.getenv("WD_FEED_PORT", "18080"))
    server = ThreadingHTTPServer((host, port), handler_for(token))
    print(f"Feed receiver listening at http://{host}:{server.server_port}/api/ingest/events", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
