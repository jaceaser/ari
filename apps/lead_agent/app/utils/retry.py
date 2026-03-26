"""Retry utilities built on tenacity."""
from __future__ import annotations

import functools
import logging
from typing import Callable, Type, TypeVar

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)
F = TypeVar("F", bound=Callable)


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Decorator: exponential backoff retry.

        @retry_with_backoff(max_attempts=3, base_delay=2.0)
        def fetch(url): ...
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            r = retry(
                stop=stop_after_attempt(max_attempts),
                wait=wait_exponential(multiplier=base_delay, max=max_delay),
                retry=retry_if_exception_type(exceptions),
                before_sleep=before_sleep_log(logger, logging.WARNING),
                reraise=True,
            )
            return r(func)(*args, **kwargs)
        return wrapper  # type: ignore
    return decorator
