import time
import functools


def retry(exceptions, tries=3, backoff=2, initial_delay=1):
    """
    Retry decorator with exponential backoff.

    Only retries on the specified exception types — never catches others.
    Backoff sequence: initial_delay, initial_delay*backoff, initial_delay*backoff^2, ...

    Args:
        exceptions: Exception class or tuple of classes to catch and retry.
        tries:      Maximum number of attempts (including the first).
        backoff:    Multiplier applied to delay after each failure.
        initial_delay: Seconds to wait before the first retry.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            last_exc = None
            for attempt in range(tries):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < tries - 1:
                        time.sleep(delay)
                        delay *= backoff
            raise last_exc
        return wrapper
    return decorator
