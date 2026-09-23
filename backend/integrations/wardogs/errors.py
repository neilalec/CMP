"""Sanitized integration failures; never carry raw server text or credentials."""


class WDRCONError(Exception):
    def __init__(self, kind: str, *, status: int | None = None,
                 code: str | None = None, retry_after_seconds: float | None = None):
        self.kind = kind
        self.status = status
        self.code = code
        self.retry_after_seconds = retry_after_seconds
        suffix = f" (HTTP {status})" if status is not None else ""
        super().__init__(f"WDRCON {kind}{suffix}")


class WDRCONPayloadError(WDRCONError):
    def __init__(self, detail: str):
        # Detail strings are authored by the parser; never interpolate raw values.
        super().__init__(f"invalid payload: {detail}")
