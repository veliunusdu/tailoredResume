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
        conn.execute('''
            CREATE TABLE IF NOT EXISTS apply_attempts (
                id          TEXT PRIMARY KEY,
                job_id      TEXT REFERENCES jobs(id),
                status      TEXT CHECK(status IN ('queued','running','success','failed','manual_required')),
                job_board   TEXT,
                dry_run     INTEGER DEFAULT 1,
                error_msg   TEXT,
                screenshot  TEXT,
                applied_at  REAL,
                created_at  REAL
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_fetched_at ON jobs(fetched_at DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_apply_attempts_job_id ON apply_attempts(job_id)')


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

def get_job_by_id(job_id: str) -> dict | None:
    """Retrieve a single job by its ID."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            return d
        return None

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


# ── Apply Queue Functions ─────────────────────────────────────────────────────

def queue_apply(job_id: str, dry_run: bool = True) -> str:
    """Insert a new apply attempt with status='queued'. Returns the attempt ID."""
    import uuid
    attempt_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO apply_attempts (id, job_id, status, dry_run, created_at)
            VALUES (?, ?, 'queued', ?, ?)
        ''', (attempt_id, job_id, 1 if dry_run else 0, now))
        conn.commit()
    return attempt_id


def update_apply_status(
    attempt_id: str,
    status: str,
    job_board: str = None,
    error_msg: str = None,
    screenshot: str = None,
) -> None:
    """Update the status of an apply attempt."""
    now = time.time()
    applied_at = now if status in ("success", "failed", "manual_required") else None
    with get_connection() as conn:
        conn.execute('''
            UPDATE apply_attempts
            SET status = ?, job_board = ?, error_msg = ?, screenshot = ?, applied_at = ?
            WHERE id = ?
        ''', (status, job_board, error_msg, screenshot, applied_at, attempt_id))
        conn.commit()


def get_apply_attempts(job_id: str) -> list[dict]:
    """Return all apply attempts for a given job, newest first."""
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT * FROM apply_attempts WHERE job_id = ? ORDER BY created_at DESC',
            (job_id,)
        )
        return [dict(row) for row in cursor]


def get_all_apply_attempts() -> list[dict]:
    """Return all apply attempts across all jobs, newest first."""
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT * FROM apply_attempts ORDER BY created_at DESC LIMIT 100'
        )
        return [dict(row) for row in cursor]


def get_apply_attempt(attempt_id: str) -> dict | None:
    """Return a single apply attempt by ID."""
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM apply_attempts WHERE id = ?', (attempt_id,)
        ).fetchone()
        return dict(row) if row else None

