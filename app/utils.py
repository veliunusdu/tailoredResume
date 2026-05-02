"""Small utility helpers shared across the app."""
from __future__ import annotations

import time
import threading
from functools import wraps
from typing import Any, Callable
from bs4 import BeautifulSoup


def minify_dom(raw_html: str) -> str:
    """
    Remove unnecessary tags and attributes from HTML to reduce token usage.
    """
    if not raw_html:
        return ""
    
    soup = BeautifulSoup(raw_html, 'html.parser')

    # Remove bloat tags completely
    for tag in soup(['script', 'style', 'svg', 'path', 'meta', 'link', 'noscript', 'iframe', 'header', 'footer', 'nav']):
        tag.decompose()

    # List of attributes to keep (essential for identifying elements)
    allowed_attrs = ['id', 'name', 'class', 'placeholder', 'aria-label', 'type', 'value', 'href']
    
    for tag in soup.find_all(True):
        # Remove all attributes except those in the allowed list
        attrs = dict(tag.attrs)
        tag.attrs = {k: v for k, v in attrs.items() if k in allowed_attrs}
        
        # Normalize class names
        if 'class' in tag.attrs and isinstance(tag.attrs['class'], list):
            tag.attrs['class'] = " ".join(tag.attrs['class'])

    return soup.prettify()


class RateLimiter:
    def __init__(self, min_interval_sec: float):
        self.min_interval_sec = min_interval_sec
        self._lock = threading.Lock()
        self._last_call = 0.0

    def wait(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call
            if elapsed < self.min_interval_sec:
                time.sleep(self.min_interval_sec - elapsed)
            self._last_call = time.time()


def is_rate_limit(exc: BaseException) -> bool:
    name = exc.__class__.__name__
    if name in ("ResourceExhausted", "TooManyRequests"):
        return True
    msg = str(exc).lower()
    return "429" in msg or "quota" in msg or "rate limit" in msg


def retry(
    *,
    max_attempts: int,
    initial_delay_sec: float,
    backoff_factor: float,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
    rate_limit_cooldown_sec: float = 60.0,
    logger: Any | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Retry a function with exponential backoff for transient failures."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            delay = initial_delay_sec
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt >= max_attempts:
                        if logger is not None:
                            logger.error(
                                "%s failed after %s attempts: %s",
                                func.__name__,
                                max_attempts,
                                exc,
                            )
                        raise

                    if is_rate_limit(exc):
                        current_delay = rate_limit_cooldown_sec
                        if logger is not None:
                            logger.warning(
                                "%s hit rate limit (attempt %s/%s). Cooling down for %.1fs.",
                                func.__name__,
                                attempt,
                                max_attempts,
                                current_delay,
                            )
                    else:
                        current_delay = delay
                        delay *= backoff_factor
                        if logger is not None:
                            logger.warning(
                                "%s failed (attempt %s/%s): %s. Retrying in %.1fs.",
                                func.__name__,
                                attempt,
                                max_attempts,
                                exc,
                                current_delay,
                            )
                    
                    time.sleep(current_delay)

        return wrapper

    return decorator
