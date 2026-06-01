"""Reintentos con backoff exponencial para llamadas con rate limit (yfinance, etc.)."""
import functools
import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def with_backoff(
    max_attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 16.0,
    jitter: float = 0.3,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorador: reintenta con espera exponencial (base*2**n) + jitter aleatorio.

    Pensado para llamadas de red con rate limits. Tras agotar los intentos,
    re-lanza la última excepción.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    attempt += 1
                    if attempt >= max_attempts:
                        raise
                    delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
                    delay += random.uniform(0, jitter * delay)
                    time.sleep(delay)

        return wrapper

    return decorator
