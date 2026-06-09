from services.rate_limit import check_rate_limit, reset_rate_limits


def setup_function():
    reset_rate_limits()


def test_rate_limit_allows_until_threshold():
    first = check_rate_limit('login:127.0.0.1:neil', max_attempts=2, window_seconds=60, now=100)
    second = check_rate_limit('login:127.0.0.1:neil', max_attempts=2, window_seconds=60, now=101)

    assert first['allowed'] is True
    assert second['allowed'] is True
    assert second['remaining'] == 0


def test_rate_limit_blocks_after_threshold():
    check_rate_limit('login:127.0.0.1:neil', max_attempts=2, window_seconds=60, now=100)
    check_rate_limit('login:127.0.0.1:neil', max_attempts=2, window_seconds=60, now=101)
    blocked = check_rate_limit('login:127.0.0.1:neil', max_attempts=2, window_seconds=60, now=102)

    assert blocked['allowed'] is False
    assert blocked['retry_after'] == 58


def test_rate_limit_expires_old_attempts():
    check_rate_limit('login:127.0.0.1:neil', max_attempts=1, window_seconds=60, now=100)
    allowed = check_rate_limit('login:127.0.0.1:neil', max_attempts=1, window_seconds=60, now=161)

    assert allowed['allowed'] is True
