"""SQLite-backed persistence for jobs, settings, secrets, and browser sessions."""
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
        # Jobs table partitioned by user_id
        conn.execute('''
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT,
                user_id TEXT,
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
                reason TEXT,
                PRIMARY KEY (id, user_id)
            )
        ''')
        # Apply attempts partitioned by user_id
        conn.execute('''
            CREATE TABLE IF NOT EXISTS apply_attempts (
                id          TEXT PRIMARY KEY,
                user_id     TEXT,
                job_id      TEXT,
                status      TEXT CHECK(status IN ('queued','running','success','failed','manual_required')),
                job_board   TEXT,
                dry_run     INTEGER DEFAULT 1,
                error_msg   TEXT,
                screenshot  TEXT,
                ai_patch_suggestion TEXT,
                applied_at  REAL,
                created_at  REAL
            )
        ''')
        # User settings partitioned by user_id
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id      TEXT PRIMARY KEY,
                target_roles TEXT, -- JSON array of strings
                locations    TEXT, -- JSON array of strings
                discovery_status TEXT DEFAULT 'idle',
                discovery_progress TEXT DEFAULT ''
            )
        ''')
        # Check and add columns dynamically if table already exists
        try:
            conn.execute("ALTER TABLE user_settings ADD COLUMN discovery_status TEXT DEFAULT 'idle'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE user_settings ADD COLUMN discovery_progress TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE user_settings ADD COLUMN last_discovery_stats TEXT")
        except sqlite3.OperationalError:
            pass
        # User secrets partitioned by user_id
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_secrets (
                user_id         TEXT,
                secret_type     TEXT,
                encrypted_value TEXT,
                PRIMARY KEY (user_id, secret_type)
            )
        ''')
        # User browser sessions partitioned by user_id
        conn.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id   TEXT,
                platform  TEXT,
                cookies   TEXT, -- JSON string
                PRIMARY KEY (user_id, platform)
            )
        ''')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC)')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_fetched_at ON jobs(fetched_at DESC)')
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN user_id TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE apply_attempts ADD COLUMN user_id TEXT")
        except sqlite3.OperationalError:
            pass


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


def save_jobs(user_id: str, jobs: list[dict]) -> int:
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
                        id, user_id, title, company, location, url, date_posted, 
                        salary, description, site, tags, fetched_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    job_id,
                    user_id,
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
                # Job already exists for this user_id
                pass
        conn.commit()
    return inserted


def get_unscored_jobs(user_id: str) -> list[dict]:
    """Retrieve jobs for a user that haven't been scored yet."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM jobs WHERE user_id = ? AND score IS NULL", (user_id,))
        jobs = []
        for row in cursor:
            d = dict(row)
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            jobs.append(d)
        return jobs


def save_score(user_id: str, job_id: str, result_dict: dict) -> None:
    """Update a job with its LLM score for a specific user."""
    with get_connection() as conn:
        conn.execute('''
            UPDATE jobs 
            SET score = ?, verdict = ?, reason = ?
            WHERE user_id = ? AND id = ?
        ''', (
            result_dict.get("score"),
            result_dict.get("verdict"),
            result_dict.get("reason"),
            user_id,
            job_id
        ))
        conn.commit()


def save_job_description(user_id: str, job_id: str, description: str) -> None:
    """Update a job's description after enrichment."""
    with get_connection() as conn:
        conn.execute('''
            UPDATE jobs 
            SET description = ?
            WHERE user_id = ? AND id = ?
        ''', (description, user_id, job_id))
        conn.commit()


def get_all_scored_jobs(user_id: str) -> list[dict]:
    """Retrieve all scored jobs for a specific user."""
    with get_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? AND score IS NOT NULL ORDER BY score DESC",
            (user_id,)
        )
        jobs = []
        for row in cursor:
            d = dict(row)
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            jobs.append(d)
        return jobs


def get_job_by_id(user_id: str, job_id: str) -> dict | None:
    """Retrieve a single job by its ID and user."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM jobs WHERE user_id = ? AND id = ?", (user_id, job_id))
        row = cursor.fetchone()
        if row:
            d = dict(row)
            d["tags"] = json.loads(d["tags"]) if d["tags"] else []
            return d
        return None


def should_fetch_jobs(user_id: str) -> bool:
    """Check if we need to fetch new jobs based on TTL."""
    with get_connection() as conn:
        row = conn.execute("SELECT MAX(fetched_at) as last_fetch FROM jobs WHERE user_id = ?", (user_id,)).fetchone()
        if not row or not row['last_fetch']:
            return True
        age_sec = time.time() - row['last_fetch']
        return age_sec > JOBS_CACHE_TTL_SEC


# ── Apply Queue Functions ─────────────────────────────────────────────────────

def queue_apply(user_id: str, job_id: str, dry_run: bool = True) -> str:
    """Insert a new apply attempt with status='queued'. Returns the attempt ID."""
    import uuid
    attempt_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO apply_attempts (id, user_id, job_id, status, dry_run, created_at)
            VALUES (?, ?, ?, 'queued', ?, ?)
        ''', (attempt_id, user_id, job_id, 1 if dry_run else 0, now))
        conn.commit()
    return attempt_id


def update_apply_status(
    user_id: str,
    attempt_id: str,
    status: str,
    job_board: str = None,
    error_msg: str = None,
    screenshot: str = None,
    ai_patch_suggestion: str = None,
) -> None:
    """Update the status of an apply attempt."""
    now = time.time()
    applied_at = now if status in ("success", "failed", "manual_required") else None
    with get_connection() as conn:
        conn.execute('''
            UPDATE apply_attempts
            SET status = ?, job_board = ?, error_msg = ?, screenshot = ?, ai_patch_suggestion = ?, applied_at = ?
            WHERE user_id = ? AND id = ?
        ''', (status, job_board, error_msg, screenshot, ai_patch_suggestion, applied_at, user_id, attempt_id))
        conn.commit()


def get_apply_attempts(user_id: str, job_id: str) -> list[dict]:
    """Return all apply attempts for a given job, newest first."""
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT * FROM apply_attempts WHERE user_id = ? AND job_id = ? ORDER BY created_at DESC',
            (user_id, job_id)
        )
        return [dict(row) for row in cursor]


def get_all_apply_attempts(user_id: str) -> list[dict]:
    """Return all apply attempts across all jobs for the user, newest first."""
    with get_connection() as conn:
        cursor = conn.execute(
            'SELECT * FROM apply_attempts WHERE user_id = ? ORDER BY created_at DESC LIMIT 100',
            (user_id,)
        )
        return [dict(row) for row in cursor]


# ── User Settings Functions ───────────────────────────────────────────────────

def get_user_settings(user_id: str) -> dict:
    """Retrieve search preferences for a user."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        if row:
            settings = {
                "target_roles": json.loads(row["target_roles"]) if row["target_roles"] else [],
                "locations": json.loads(row["locations"]) if row["locations"] else []
            }
        else:
            settings = {
                "target_roles": [],
                "locations": ["remote"]
            }
        
        # Mask the API key if it exists in secrets
        api_key = get_user_api_key(user_id)
        if api_key:
            settings["gemini_api_key"] = "********"
        else:
            settings["gemini_api_key"] = ""
            
        return settings


def get_user_api_key(user_id: str) -> str | None:
    """Helper to get a user's Gemini API key from encrypted secrets."""
    return get_user_secret(user_id, "gemini_api_key")


def save_user_settings(user_id: str, settings: dict) -> None:
    """Save search preferences for a user."""
    # Move sensitive keys to secrets
    if "gemini_api_key" in settings:
        key_value = settings.pop("gemini_api_key")
        # Only save if it's not the masked placeholder
        if key_value and key_value != "********":
            save_user_secret(user_id, "gemini_api_key", key_value)

    roles_json = json.dumps(settings.get("target_roles", []))
    locations_json = json.dumps(settings.get("locations", []))

    with get_connection() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO user_settings (user_id, target_roles, locations)
            VALUES (?, ?, ?)
        ''', (user_id, roles_json, locations_json))
        conn.commit()


# ── Secrets Management ────────────────────────────────────────────────────────

def save_user_secret(user_id: str, secret_type: str, secret_value: str) -> None:
    """Encrypt and save a user secret (e.g. 'gemini_api_key')."""
    from app.crypto import encrypt_value
    encrypted = encrypt_value(secret_value)
    
    with get_connection() as conn:
        conn.execute('''
            INSERT OR REPLACE INTO user_secrets (user_id, secret_type, encrypted_value)
            VALUES (?, ?, ?)
        ''', (user_id, secret_type, encrypted))
        conn.commit()


def get_user_secret(user_id: str, secret_type: str) -> str | None:
    """Retrieve and decrypt a user secret."""
    from app.crypto import decrypt_value
    with get_connection() as conn:
        row = conn.execute(
            "SELECT encrypted_value FROM user_secrets WHERE user_id = ? AND secret_type = ?",
            (user_id, secret_type)
        ).fetchone()
        if row and row["encrypted_value"]:
            try:
                return decrypt_value(row["encrypted_value"])
            except Exception:
                pass
    return None


def list_user_secrets(user_id: str) -> list[str]:
    """List the keys of all secrets stored for a user."""
    with get_connection() as conn:
        cursor = conn.execute("SELECT secret_type FROM user_secrets WHERE user_id = ?", (user_id,))
        return [r["secret_type"] for r in cursor]


def update_discovery_status(user_id: str, status: str, progress: str = "") -> None:
    """Update the current discovery status and progress message."""
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO user_settings (user_id, target_roles, locations, discovery_status, discovery_progress)
            VALUES (?, '[]', '[]', ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                discovery_status = excluded.discovery_status,
                discovery_progress = excluded.discovery_progress
        ''', (user_id, status, progress))
        conn.commit()


def save_discovery_stats(user_id: str, stats: dict) -> None:
    """Save the statistics of the last job discovery run."""
    stats_json = json.dumps(stats)
    with get_connection() as conn:
        conn.execute('''
            INSERT INTO user_settings (user_id, target_roles, locations, last_discovery_stats)
            VALUES (?, '[]', '[]', ?)
            ON CONFLICT(user_id) DO UPDATE SET
                last_discovery_stats = excluded.last_discovery_stats
        ''', (user_id, stats_json))
        conn.commit()


def get_discovery_stats(user_id: str) -> dict | None:
    """Retrieve the statistics of the last job discovery run."""
    with get_connection() as conn:
        row = conn.execute("SELECT last_discovery_stats FROM user_settings WHERE user_id = ?", (user_id,)).fetchone()
        if row and row["last_discovery_stats"]:
            try:
                return json.loads(row["last_discovery_stats"])
            except Exception:
                pass
    return None
