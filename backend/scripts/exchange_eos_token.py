import json
import os
import sys
from base64 import b64encode
from pathlib import Path
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def require_env(name: str) -> str:
    value = str(os.getenv(name, "")).strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def build_basic_auth(client_id: str, client_secret: str) -> str:
    raw = f"{client_id}:{client_secret}".encode("utf-8")
    return f"Basic {b64encode(raw).decode('ascii')}"


def main() -> int:
    try:
        client_id = require_env("EOS_CLIENT_ID")
        client_secret = require_env("EOS_CLIENT_SECRET")
        steam_ticket = require_env("EOS_STEAM_SESSION_TICKET_HEX")
        deployment_id = str(
            os.getenv("EOS_DEPLOYMENT_ID", "5dee4062a90b42cd98fcad618b6636c2")
        ).strip()
        api_base_url = str(os.getenv("EOS_API_BASE_URL", "https://api.epicgames.dev")).rstrip("/")
        endpoint = f"{api_base_url}/auth/v1/oauth/token"

        body = urllib_parse.urlencode(
            {
                "grant_type": "external_auth",
                "external_auth_type": "steam_session_ticket",
                "external_auth_token": steam_ticket,
                "deployment_id": deployment_id,
            }
        ).encode("utf-8")

        request = urllib_request.Request(
            endpoint,
            data=body,
            method="POST",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": build_basic_auth(client_id, client_secret),
            },
        )

        with urllib_request.urlopen(request, timeout=15) as response:
            payload = json.loads(response.read().decode("utf-8"))

        access_token = str(payload.get("access_token") or "").strip()
        if not access_token:
            raise RuntimeError("EOS response did not include access_token")

        print("EOS_ACCESS_TOKEN=" + access_token)
        return 0
    except urllib_error.HTTPError as error:
        raw = error.read().decode("utf-8", errors="replace")
        print(raw or f"HTTP {error.code}", file=sys.stderr)
        return 1
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
