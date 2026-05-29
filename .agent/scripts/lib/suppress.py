"""Centralized exception suppression with structured logging.

Provides lightweight utilities for replacing bare `except: pass`
with observable, level-appropriate logging.

Usage:
    with suppress("ctx.description", level=logging.WARNING):
        risky_operation()

    @silent(level=logging.DEBUG, fallback=[])
    def discovery_fn():
        ...
"""

import logging
from contextlib import contextmanager
from functools import wraps
from typing import Optional, Type


@contextmanager
def suppress(
    context: str,
    level: int = logging.WARNING,
    logger_obj: Optional[logging.Logger] = None,
    raise_on: Optional[Type[BaseException]] = None,
):
    """Catch exceptions, log them at the specified level, and continue.

    Args:
        context: Human-readable label for the operation being suppressed.
        level: Logging level (logging.DEBUG / WARNING / ERROR).
        logger_obj: Logger to use (defaults to __name__).
        raise_on: If set, re-raise exceptions of this type (e.g. MemoryError).
    """
    log = logger_obj or logging.getLogger(__name__)
    try:
        yield
    except raise_on:
        raise
    except Exception as e:
        log.log(level, "[suppress] %s: %s", context, e)


def silent(
    level: int = logging.WARNING,
    context: Optional[str] = None,
    fallback=None,
):
    """Decorator: catch exceptions from a function, log, return fallback."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            ctx = context or func.__qualname__
            with suppress(ctx, level=level):
                return func(*args, **kwargs)
            return fallback
        return wrapper
    return decorator
