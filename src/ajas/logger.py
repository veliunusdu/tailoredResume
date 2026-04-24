import logging
import re
import sys
import uuid

import structlog
from structlog.contextvars import bind_contextvars, merge_contextvars

PII_PATTERNS = {
    "[[EMAIL]]": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "[[PHONE]]": r"\+?[\d][\d\s().-]{7,}[\d]",
}


def redact_pii(logger, method_name, event_dict):
    """Processor to strip PII from the 'event' (message) string."""
    event = event_dict.get("event")
    if isinstance(event, str):
        for placeholder, pat in PII_PATTERNS.items():
            event = re.sub(pat, placeholder, event)
        event_dict["event"] = event
    return event_dict


def setup_logging():
    """Initialise structlog with trace_ids and JSON formatting for production."""
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    structlog.configure(
        processors=[
            merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            redact_pii,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()


log = setup_logging()


def set_trace_id(trace_id: str = None):
    """Set a trace_id for the current async context/thread."""
    if not trace_id:
        trace_id = str(uuid.uuid4())
    bind_contextvars(trace_id=trace_id)
    return trace_id
