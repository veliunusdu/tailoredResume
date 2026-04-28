"""SQLite-backed persistence for jobs and scoring."""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

from app.config import DATA_DIR, JOBS_CACHE_TTL_SEC
from app.logger import get_logger

_logger = get_logger(__name__)

DB_PATH = DATA_DIR / "app.db"


def init_db():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                title TEXT,
                company TEXT,
                location TEXT,
                url TEXT,
                date_posted TEXT,
                salary TEXT,
                description TEXT,
                site TEXT,
                tags TEXT,
                fetched_at REAL,
                score INTEGER,
                verdict TEXT,
                reason TEXT
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_fetched_at ON jobs(fetched_at DESC)')


@contextmanager
def get_connection():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def build_job_id(job: dict) -> str:
    """Stable unique ID for a job."""
    raw_key = (
        job.get("url")
        or f"{job.get('title', '')}|{job.get('company', '')}|{job.get('location', '')}"
    )
    return hashlib.sha256(raw_key.strip().lower().encode("utf-8")).hexdigest()


def save_jobs(jobs: list[dict]) -> int:
    """Insert or ignore normalized jobs into the database."""
    inserted = 0
    now = time.time()
    with get_connection() as conn:
        for job in jobs:
            job_id = build_job_id(job)
            tags_json = json.dumps(job.get("tags", []))
            try:
                conn.execute('''
                    INSERT INTO jobs (
                        id, title, company, location, url, date_posted, 
                        salary, description, site, tags, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_id,
                    job.get("title", ""),
                    job.get("company", ""),
                    job.get("location", ""),
                    job.get("url", ""),
                    job.get("date_posted", ""),
                    job.get("salary", ""),
                    job.get("description", ""),
                    job.get("site", "Web"),
                    tags_json,
                    now
                ))
                inserted += 1
            except sqlite3.IntegrityError:
                # Job already exists (deduplication)
                pass
        conn.commit()
    return inserted


def get_unscored_jobs() -> list[dict]:
    """Retrieve jobs that haven't been scored yet."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM jobs WHERE score IS NULL")
        jobs = []
        for row in cursor:
            d = dict(row)
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            jobs.append(d)
        return jobs


def save_score(job_id: str, result: dict) -> None:
    """Update a job with its LLM score."""
    with get_connection() as conn:
        conn.execute('''
            UPDATE jobs 
            SET score = ?, verdict = ?, reason = ?
            WHERE id = ?
        ''', (
            result.get("score"),
            result.get("verdict"),
            result.get("reason"),
            job_id
        ))
        conn.commit()


def save_job_description(job_id: str, description: str) -> None:
    """Update a job's description after enrichment."""
    with get_connection() as conn:
        conn.execute('''
            UPDATE jobs 
            SET description = ?
            WHERE id = ?
        ''', (description, job_id))
        conn.commit()


def get_all_scored_jobs() -> list[dict]:

    """Retrieve all scored jobs from the database."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM jobs WHERE score IS NOT NULL ORDER BY score DESC")
        jobs = []
        for row in cursor:
            d = dict(row)
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            jobs.append(d)
        return jobs

def should_fetch_jobs() -> bool:
    """Check if we need to fetch new jobs based on TTL."""
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(fetched_at) as last_fetch FROM jobs").fetchone()
        if not row or not row['last_fetch']:
            return True
        age_sec = time.time() - row['last_fetch']
        return age_sec > JOBS_CACHE_TTL_SEC

# ── Deprecated Cache Functions (to be removed once jobs.py and agent.py are updated) ──


def get_cached_jobs(*, allow_stale: bool = False) -> list[dict] | None:
    return None

def set_cached_jobs(jobs: list[dict]) -> None:
    pass

def build_llm_cache_key(job: dict) -> str:
    return build_job_id(job)

def get_cached_llm_score(cache_key: str) -> dict | None:
    return None

def set_cached_llm_score(cache_key: str, result: dict) -> None:
    pass
