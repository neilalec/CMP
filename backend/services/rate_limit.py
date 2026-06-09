import time
from threading import RLock


_rate_limit_buckets = {}
_rate_limit_lock = RLock()


def check_rate_limit(key, *, max_attempts, window_seconds, now=None):
    now = now or time.time()
    window_start = now - window_seconds

    with _rate_limit_lock:
        attempts = [
            timestamp
            for timestamp in _rate_limit_buckets.get(key, [])
            if timestamp > window_start
        ]

        if len(attempts) >= max_attempts:
            retry_after = max(1, int(window_seconds - (now - attempts[0])))
            _rate_limit_buckets[key] = attempts
            return {
                'allowed': False,
                'retry_after': retry_after,
                'remaining': 0
            }

        attempts.append(now)
        _rate_limit_buckets[key] = attempts
        return {
            'allowed': True,
            'retry_after': 0,
            'remaining': max(0, max_attempts - len(attempts))
        }


def clear_rate_limit(key):
    with _rate_limit_lock:
        _rate_limit_buckets.pop(key, None)


def reset_rate_limits():
    with _rate_limit_lock:
        _rate_limit_buckets.clear()
