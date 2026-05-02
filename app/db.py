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
        # Core jobs table
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
        
        # Application tracking table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS apply_attempts (
                id TEXT PRIMARY KEY,
                job_id TEXT,
                job_url TEXT,
                status TEXT, -- queued, running, success, failed, manual_required
                platform TEXT,
                started_at REAL,
                finished_at REAL,
                error_msg TEXT,
                screenshot_path TEXT,
                FOREIGN KEY(job_id) REFERENCES jobs(id)
            )
        ''')
        
        conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_apply_job_id ON apply_attempts(job_id)')


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
    return hashlib.md5(raw_key.encode()).hexdigest()


def save_jobs(jobs: list[dict]):
    """Save/update jobs in SQLite."""
    with get_connection() as conn:
        for job in jobs:
            job_id = build_job_id(job)
            conn.execute('''
                INSERT INTO jobs (id, title, company, location, url, date_posted, salary, description, site, tags, fetched_at, score, verdict, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    score = excluded.score,
                    verdict = excluded.verdict,
                    reason = excluded.reason
            ''', (
                job_id,
                job.get("title"),
                job.get("company"),
                job.get("location"),
                job.get("url"),
                job.get("date_posted"),
                job.get("salary"),
                job.get("description"),
                job.get("site"),
                json.dumps(job.get("tags", [])),
                time.time(),
                job.get("score"),
                job.get("verdict"),
                job.get("reason")
            ))


def get_all_scored_jobs() -> list[dict]:
    """Return all jobs with score >= 0, sorted by score DESC."""
    with get_connection() as conn:
        cursor = conn.execute('SELECT * FROM jobs WHERE score IS NOT NULL ORDER BY score DESC')
        return [dict(row) for row in cursor.fetchall()]


def get_unscored_jobs() -> list[dict]:
    """Return jobs that haven't been scored yet."""
    with get_connection() as conn:
        cursor = conn.execute('SELECT * FROM jobs WHERE score IS NULL')
        return [dict(row) for row in cursor.fetchall()]


def save_score(job_id: str, score: int, verdict: str, reason: str):
    """Update a job's score and verdict."""
    with get_connection() as conn:
        conn.execute('''
            UPDATE jobs 
            SET score = ?, verdict = ?, reason = ? 
            WHERE id = ?
        ''', (score, verdict, reason, job_id))


def save_job_description(job_id: str, description: str):
    """Update a job's description (e.g. after enrichment)."""
    with get_connection() as conn:
        conn.execute('UPDATE jobs SET description = ? WHERE id = ?', (description, job_id))


def should_fetch_jobs() -> bool:
    """Check if we need to fetch new jobs based on TTL."""
    with get_connection() as conn:
        cursor = conn.execute('SELECT MAX(fetched_at) as last_fetch FROM jobs')
        row = cursor.fetchone()
        if not row or not row['last_fetch']:
            return True
        return (time.time() - row['last_fetch']) > JOBS_CACHE_TTL_SEC


# ── Application Tracking ──────────────────────────────────────────────────────

def queue_apply(job_id: str, job_url: str) -> str:
    """Record a new application attempt in the queue."""
    attempt_id = f"{job_id[:8]}_{int(time.time())}"
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO apply_attempts (id, job_id, job_url, status, started_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (attempt_id, job_id, job_url, "queued", time.time()))
    return attempt_id


def update_apply_status(attempt_id: str, status: str, platform: str = None, error_msg: str = None, screenshot_path: str = None):
    """Update status of an application attempt."""
    with get_connection() as conn:
        query = "UPDATE apply_attempts SET status = ?, platform = ?, error_msg = ?, screenshot_path = ?"
        params = [status, platform, error_msg, screenshot_path]
        
        if status in ["success", "failed", "manual_required"]:
            query += ", finished_at = ?"
            params.append(time.time())
            
        query += " WHERE id = ?"
        params.append(attempt_id)
        
        conn.execute(query, params)


def get_apply_status(job_id: str) -> dict:
    """Get the latest application status for a job."""
    with get_connection() as conn:
        cursor = conn.execute('''
            SELECT * FROM apply_attempts 
            WHERE job_id = ? 
            ORDER BY started_at DESC LIMIT 1
        ''', (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else {"status": "idle"}
