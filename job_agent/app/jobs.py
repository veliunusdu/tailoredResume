import requests
from app.config import (
    HTTP_TIMEOUT_SEC,
    JOB_API_URL,
    JOB_CATEGORY,
    JOB_LIMIT,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_FACTOR,
    RETRY_INITIAL_DELAY_SEC,
)
from app.db import get_cached_jobs, set_cached_jobs
from app.logger import get_logger
from app.utils import retry

_logger = get_logger(__name__)


@retry(
    max_attempts=RETRY_ATTEMPTS,
    initial_delay_sec=RETRY_INITIAL_DELAY_SEC,
    backoff_factor=RETRY_BACKOFF_FACTOR,
    logger=_logger,
)
def _fetch_jobs_remote() -> list[dict]:
    params = {"limit": JOB_LIMIT, "category": JOB_CATEGORY}
    response = requests.get(JOB_API_URL, params=params, timeout=HTTP_TIMEOUT_SEC)
    response.raise_for_status()
    data = response.json().get("jobs", [])
    if not isinstance(data, list):
        raise ValueError("Unexpected jobs payload from API")
    return data


def fetch_jobs() -> list[dict]:
    """Fetch raw job listings from the Remotive API."""
    cached_jobs = get_cached_jobs()
    if cached_jobs is not None:
        _logger.info("Jobs cache hit: returning %s cached jobs", len(cached_jobs))
        return cached_jobs

    try:
        fresh_jobs = _fetch_jobs_remote()
        _logger.info("Fetched %s jobs from API", len(fresh_jobs))
        set_cached_jobs(fresh_jobs)
        return fresh_jobs
    except Exception as exc:
        _logger.error("Job API failed, attempting stale cache fallback: %s", exc)
        stale_jobs = get_cached_jobs(allow_stale=True)
        if stale_jobs is not None:
            _logger.warning("Using stale jobs cache with %s jobs", len(stale_jobs))
            return stale_jobs
        _logger.exception("No cached jobs available; propagating failure")
        raise
