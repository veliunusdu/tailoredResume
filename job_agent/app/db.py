"""Simple JSON-backed persistence helpers for caching."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

from app.config import JOBS_CACHE_FILE, JOBS_CACHE_TTL_SEC, LLM_CACHE_FILE
from app.logger import get_logger

_logger = get_logger(__name__)


def _read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        _logger.warning("Failed to read cache %s: %s", path, exc)
        return default


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def get_cached_jobs(*, allow_stale: bool = False) -> list[dict] | None:
    """Return cached jobs when cache exists and is fresh (or stale is allowed)."""
    payload = _read_json(Path(JOBS_CACHE_FILE), default={})
    jobs = payload.get("jobs")
    fetched_at = payload.get("fetched_at")

    if not isinstance(jobs, list) or not isinstance(fetched_at, (int, float)):
        return None

    age_sec = time.time() - float(fetched_at)
    if allow_stale or age_sec <= JOBS_CACHE_TTL_SEC:
        return jobs
    return None


def set_cached_jobs(jobs: list[dict]) -> None:
    """Persist raw jobs payload with fetch timestamp."""
    payload = {"fetched_at": time.time(), "jobs": jobs}
    _write_json(Path(JOBS_CACHE_FILE), payload)


def build_llm_cache_key(job: dict) -> str:
    """Stable cache key for a job score result."""
    raw_key = (
        job.get("url")
        or f"{job.get('title', '')}|{job.get('company', '')}|{job.get('location', '')}"
    )
    return hashlib.sha256(raw_key.strip().lower().encode("utf-8")).hexdigest()


def get_cached_llm_score(cache_key: str) -> dict | None:
    """Return cached LLM score result for a cache key, if available."""
    payload = _read_json(Path(LLM_CACHE_FILE), default={})
    result = payload.get(cache_key)
    if isinstance(result, dict):
        return result
    return None


def set_cached_llm_score(cache_key: str, result: dict) -> None:
    """Persist one LLM score result by cache key."""
    payload = _read_json(Path(LLM_CACHE_FILE), default={})
    payload[cache_key] = result
    _write_json(Path(LLM_CACHE_FILE), payload)
