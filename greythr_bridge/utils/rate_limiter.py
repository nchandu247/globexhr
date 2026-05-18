import functools
from ratelimit import limits, sleep_and_retry


def rate_limited(calls=10, period=1):
    """
    Rate-limit a function to `calls` per `period` seconds.
    Sleeps automatically when the limit is reached — never raises.
    """
    def decorator(func):
        limited = sleep_and_retry(limits(calls=calls, period=period)(func))

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return limited(*args, **kwargs)
        return wrapper
    return decorator
