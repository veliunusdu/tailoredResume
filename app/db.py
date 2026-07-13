"""
PostgreSQL-backed persistence for jobs, resumes, apply attempts, and search config.

Replaces the SQLite db.py with a multi-tenant, connection-pooled implementation.
All query functions accept a `user_id` parameter to scope data per user.

Environment Variables:
  DATABASE_URL — PostgreSQL connection string
                 e.g. postgresql://user:pass@localhost:5432/tailoredresume
                 For Supabase: postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from contextlib import contextmanager
from typing import Generator

import psycopg2
import psycopg2.extras
import psycopg2.pool

from app.config import DATABASE_URL, JOBS_CACHE_TTL_SEC
from app.logger import get_logger

_logger = get_logger(__name__)

# ── Connection Pool ───────────────────────────────────────────────────────────

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not DATABASE_URL:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to your .env file.\n"
                "Example: postgresql://user:pass@localhost:5432/tailoredresume"
            )
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
        )
        _logger.info("✅ PostgreSQL connection pool created.")
    return _pool


@contextmanager
def get_connection(user_id: str | None = None) -> Generator:
    """Yield a psycopg2 connection from the pool, return it when done."""
    pool = _get_pool()
    conn = pool.getconn()
    conn.autocommit = False
    try:
        if user_id:
            with conn.cursor() as cur:
                cur.execute("SET LOCAL app.current_user_id = %s", (user_id,))
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


# ── Schema Initialisation (called once on startup) ────────────────────────────

def init_db() -> None:
    """Create all tables if they don't exist. Safe to call multiple times."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id          TEXT NOT NULL,
                    user_id     TEXT NOT NULL,
                    title       TEXT,
                    company     TEXT,
                    location    TEXT,
                    url         TEXT,
                    date_posted TEXT,
                    salary      TEXT,
                    description TEXT,
                    site        TEXT,
                    tags        JSONB DEFAULT '[]',
                    fetched_at  DOUBLE PRECISION,
                    score       INTEGER,
                    verdict     TEXT,
                    reason      TEXT,
                    tailored_resume TEXT,
                    cover_letter TEXT,
                    PRIMARY KEY (id, user_id)
                )
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS tailored_resume TEXT;
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS cover_letter TEXT;
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS interview_questions JSONB;
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS required_skills JSONB;
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS missing_skills JSONB;
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS found_skills JSONB;
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'saved';
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS skill_match_score INTEGER;
            """)
            cur.execute("""
                ALTER TABLE jobs ADD COLUMN IF NOT EXISTS embedding JSONB;
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_user_score
                    ON jobs (user_id, score DESC)
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_user_fetched
                    ON jobs (user_id, fetched_at DESC)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS source_metrics (
                    id                  SERIAL PRIMARY KEY,
                    run_id              TEXT NOT NULL,
                    user_id             TEXT NOT NULL,
                    board               TEXT NOT NULL,
                    raw_count           INTEGER DEFAULT 0,
                    filtered_count      INTEGER DEFAULT 0,
                    inserted_count      INTEGER DEFAULT 0,
                    fetched_at          DOUBLE PRECISION NOT NULL
                )
            """)


            cur.execute("""
                CREATE TABLE IF NOT EXISTS apply_attempts (
                    id                  TEXT PRIMARY KEY,
                    user_id             TEXT NOT NULL,
                    job_id              TEXT,
                    status              TEXT CHECK(status IN
                        ('queued','running','success','failed','manual_required')),
                    job_board           TEXT,
                    dry_run             INTEGER DEFAULT 1,
                    error_msg           TEXT,
                    screenshot          TEXT,
                    ai_patch_suggestion TEXT,
                    applied_at          DOUBLE PRECISION,
                    created_at          DOUBLE PRECISION
                )
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_apply_attempts_user_job
                    ON apply_attempts (user_id, job_id)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS resumes (
                    id           TEXT PRIMARY KEY,
                    user_id      TEXT NOT NULL,
                    filename     TEXT NOT NULL,
                    content      TEXT NOT NULL,
                    structured_data JSONB,
                    storage_path TEXT,
                    created_at   DOUBLE PRECISION
                )
            """)
            cur.execute("""
                ALTER TABLE resumes ADD COLUMN IF NOT EXISTS structured_data JSONB;
            """)
            cur.execute("""
                ALTER TABLE resumes ADD COLUMN IF NOT EXISTS embedding JSONB;
            """)
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_resumes_user
                    ON resumes (user_id)
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_search_config (
                    user_id          TEXT PRIMARY KEY,
                    queries          JSONB DEFAULT '[]',
                    locations        JSONB DEFAULT '[]',
                    boards           JSONB DEFAULT '["indeed","linkedin","glassdoor"]',
                    exclude_titles   JSONB DEFAULT '[]',
                    seniority_levels JSONB DEFAULT '[]',
                    profile_notes    TEXT,
                    results_per_site INTEGER DEFAULT 20,
                    hours_old        INTEGER DEFAULT 72,
                    updated_at       DOUBLE PRECISION
                )
            """)
            cur.execute("""
                ALTER TABLE user_search_config ADD COLUMN IF NOT EXISTS seniority_levels JSONB DEFAULT '[]';
            """)
            cur.execute("""
                ALTER TABLE user_search_config ADD COLUMN IF NOT EXISTS profile_notes TEXT;
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS task_progress (
                    task_id    TEXT PRIMARY KEY,
                    user_id    TEXT NOT NULL,
                    status     TEXT NOT NULL,
                    message    TEXT NOT NULL,
                    progress   INTEGER DEFAULT 0,
                    updated_at DOUBLE PRECISION
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS selector_patches (
                    broken_selector     TEXT PRIMARY KEY,
                    patched_selector    TEXT NOT NULL,
                    is_verified         BOOLEAN DEFAULT FALSE,
                    created_at          DOUBLE PRECISION
                )
            """)

    _logger.info("✅ Database schema ready.")


def update_task_progress(
    task_id: str,
    user_id: str,
    status: str,
    message: str,
    progress: int = 0,
) -> None:
    """Insert or update task progress in the task_progress table."""
    now = time.time()
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO task_progress (task_id, user_id, status, message, progress, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (task_id) DO UPDATE
                SET status = EXCLUDED.status,
                    message = EXCLUDED.message,
                    progress = EXCLUDED.progress,
                    updated_at = EXCLUDED.updated_at
            """, (task_id, user_id, status, message, progress, now))


def get_task_progress(task_id: str, user_id: str) -> dict | None:
    """Fetch task progress by task_id and user_id."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM task_progress WHERE task_id = %s AND user_id = %s",
                (task_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_active_tasks(user_id: str) -> list[dict]:
    """Fetch active task progress records for the user."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM task_progress WHERE user_id = %s AND status IN ('running', 'queued', 'pending') ORDER BY updated_at DESC",
                (user_id,),
            )
            rows = cur.fetchall()
            return [dict(row) for row in rows]



def save_tailored_materials(job_id: str, user_id: str, tailored_resume: str, cover_letter: str | None = None, interview_questions: list | None = None) -> None:
    """Save the LLM-generated tailored resume, cover letter, and interview questions to a job."""
    import json
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE jobs 
                SET tailored_resume = %s, cover_letter = %s, interview_questions = %s
                WHERE id = %s AND user_id = %s
            """, (tailored_resume, cover_letter, json.dumps(interview_questions) if interview_questions else None, job_id, user_id))


def save_skill_analysis(job_id: str, user_id: str, required_skills: list, missing_skills: list, match_score: int) -> None:
    """Save the AI skill extraction and gap analysis to a job."""
    import json
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE jobs 
                SET required_skills = %s, missing_skills = %s, skill_match_score = %s
                WHERE id = %s AND user_id = %s
            """, (json.dumps(required_skills), json.dumps(missing_skills), match_score, job_id, user_id))


def get_selector_patch(broken_selector: str) -> str | None:
    """Fetch a patched selector by its broken version."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT patched_selector FROM selector_patches WHERE broken_selector = %s",
                (broken_selector,),
            )
            row = cur.fetchone()
            return row[0] if row else None


def save_selector_patch(broken_selector: str, patched_selector: str) -> None:
    """Save or update a selector patch."""
    now = time.time()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO selector_patches (broken_selector, patched_selector, created_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (broken_selector) DO UPDATE
                SET patched_selector = EXCLUDED.patched_selector,
                    is_verified = FALSE,
                    created_at = EXCLUDED.created_at
            """, (broken_selector, patched_selector, now))


def verify_selector_patch(broken_selector: str) -> None:
    """Mark a selector patch as verified."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE selector_patches SET is_verified = TRUE WHERE broken_selector = %s",
                (broken_selector,),
            )


# ── Job Helpers ───────────────────────────────────────────────────────────────

def build_job_id(job: dict) -> str:
    """Stable unique ID for a job based on URL or title+company+location."""
    raw_key = (
        job.get("url")
        or f"{job.get('title', '')}|{job.get('company', '')}|{job.get('location', '')}"
    )
    return hashlib.sha256(raw_key.strip().lower().encode("utf-8")).hexdigest()


def _row_to_job(row: dict) -> dict:
    """Normalise a DB row into a plain job dict."""
    d = dict(row)
    tags = d.get("tags")
    if isinstance(tags, str):
        d["tags"] = json.loads(tags)
    elif tags is None:
        d["tags"] = []
    return d


# ── Job CRUD ──────────────────────────────────────────────────────────────────

from typing import Any

def save_jobs(jobs: list[dict], user_id: str, collector: Any = None) -> int:
    """Insert-or-ignore normalised jobs. Returns count of newly inserted rows."""
    from app.llm import embed_text
    inserted = 0
    now = time.time()
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            for job in jobs:
                job_id = build_job_id(job)
                tags_json = json.dumps(job.get("tags", []))
                
                # Check if job already exists to avoid unnecessary API calls
                cur.execute("SELECT 1 FROM jobs WHERE id = %s AND user_id = %s", (job_id, user_id))
                if cur.fetchone():
                    continue

                embed_payload = f"{job.get('title', '')} {job.get('company', '')} {tags_json} {job.get('description', '')}"
                embedding = embed_text(embed_payload)

                try:
                    cur.execute("""
                        INSERT INTO jobs (
                            id, user_id, title, company, location, url,
                            date_posted, salary, description, site, tags, fetched_at, embedding
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (id, user_id) DO NOTHING
                    """, (
                        job_id, user_id,
                        job.get("title", ""),
                        job.get("company", ""),
                        job.get("location", ""),
                        job.get("url", ""),
                        job.get("date_posted", ""),
                        job.get("salary", ""),
                        job.get("description", ""),
                        job.get("site", "Web"),
                        tags_json,
                        now,
                        json.dumps(embedding) if embedding else None
                    ))
                    if cur.rowcount:
                        inserted += 1
                        if collector:
                            collector.add_inserted(job.get("site", "unknown"), 1)
                except Exception as exc:
                    _logger.warning("Failed to insert job %s: %s", job_id, exc)
    return inserted



def get_unscored_jobs(user_id: str) -> list[dict]:
    """Retrieve jobs that haven't been scored yet for this user."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM jobs WHERE user_id = %s AND score IS NULL",
                (user_id,),
            )
            return [_row_to_job(row) for row in cur.fetchall()]

def rank_jobs_with_vector(job_ids: list[str], resume_id: str, user_id: str) -> dict[str, float]:
    """Calculate 1 - cosine_distance for the given jobs against a resume in Python to avoid pgvector requirement."""
    if not job_ids:
        return {}
        
    import math
    def cosine_similarity(v1, v2):
        if not v1 or not v2: return 0.0
        dot_product = sum(a * b for a, b in zip(v1, v2))
        norm_a = math.sqrt(sum(a * a for a in v1))
        norm_b = math.sqrt(sum(b * b for b in v2))
        if norm_a == 0 or norm_b == 0: return 0.0
        return dot_product / (norm_a * norm_b)

    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            # Get resume embedding
            cur.execute("SELECT embedding FROM resumes WHERE id = %s AND user_id = %s", (resume_id, user_id))
            r_row = cur.fetchone()
            if not r_row or not r_row[0]:
                return {}
            resume_emb = r_row[0]

            # Get job embeddings
            cur.execute("SELECT id, embedding FROM jobs WHERE id = ANY(%s) AND user_id = %s AND embedding IS NOT NULL", (job_ids, user_id))
            job_rows = cur.fetchall()
            
            similarities = {}
            for jid, j_emb in job_rows:
                similarities[jid] = cosine_similarity(resume_emb, j_emb)
            
            return similarities


def get_all_scored_jobs(user_id: str) -> list[dict]:
    """Retrieve all scored jobs for this user, sorted by score descending."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM jobs WHERE user_id = %s AND score IS NOT NULL ORDER BY score DESC",
                (user_id,),
            )
            return [_row_to_job(row) for row in cur.fetchall()]


def get_job_by_id(job_id: str, user_id: str) -> dict | None:
    """Retrieve a single job by ID, scoped to this user."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM jobs WHERE id = %s AND user_id = %s",
                (job_id, user_id),
            )
            row = cur.fetchone()
            return _row_to_job(row) if row else None


def save_score(job_id: str, result: dict, user_id: str) -> None:
    """Update a job with its LLM score."""
    import json
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE jobs
                SET score = %s, verdict = %s, reason = %s, found_skills = %s, missing_skills = %s
                WHERE id = %s AND user_id = %s
            """, (
                result.get("score"),
                result.get("verdict"),
                result.get("reason"),
                json.dumps(result.get("found_skills", [])),
                json.dumps(result.get("missing_skills", [])),
                job_id, user_id,
            ))


def update_job_status(job_id: str, status: str, user_id: str) -> None:
    """Update a job's status."""
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET status = %s WHERE id = %s AND user_id = %s",
                (status, job_id, user_id),
            )


def save_job_description(job_id: str, description: str, user_id: str) -> None:
    """Update a job's description after enrichment."""
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET description = %s WHERE id = %s AND user_id = %s",
                (description, job_id, user_id),
            )


def should_fetch_jobs(user_id: str) -> bool:
    """Check if we need to fetch new jobs based on TTL."""
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT MAX(fetched_at) as last_fetch FROM jobs WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            if not row or not row[0]:
                return True
            age_sec = time.time() - row[0]
            return age_sec > JOBS_CACHE_TTL_SEC


# ── Apply Queue ───────────────────────────────────────────────────────────────

def queue_apply(job_id: str, user_id: str, dry_run: bool = True) -> str:
    """Insert a new apply attempt with status='queued'. Returns the attempt ID."""
    attempt_id = str(uuid.uuid4())
    now = time.time()
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO apply_attempts (id, user_id, job_id, status, dry_run, created_at)
                VALUES (%s, %s, %s, 'queued', %s, %s)
            """, (attempt_id, user_id, job_id, 1 if dry_run else 0, now))
    return attempt_id


def update_apply_status(
    attempt_id: str,
    status: str,
    user_id: str,
    job_board: str = None,
    error_msg: str = None,
    screenshot: str = None,
    ai_patch_suggestion: str = None,
) -> None:
    """Update the status of an apply attempt."""
    now = time.time()
    applied_at = now if status in ("success", "failed", "manual_required") else None
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE apply_attempts
                SET status = %s, job_board = %s, error_msg = %s,
                    screenshot = %s, ai_patch_suggestion = %s, applied_at = %s
                WHERE id = %s AND user_id = %s
            """, (status, job_board, error_msg, screenshot,
                  ai_patch_suggestion, applied_at, attempt_id, user_id))


def get_apply_attempts(job_id: str, user_id: str) -> list[dict]:
    """Return all apply attempts for a given job, newest first."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM apply_attempts WHERE job_id = %s AND user_id = %s ORDER BY created_at DESC",
                (job_id, user_id),
            )
            return [dict(row) for row in cur.fetchall()]


def get_all_apply_attempts(user_id: str) -> list[dict]:
    """Return all apply attempts for this user, newest first (last 100)."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM apply_attempts WHERE user_id = %s ORDER BY created_at DESC LIMIT 100",
                (user_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def get_apply_attempt(attempt_id: str, user_id: str) -> dict | None:
    """Return a single apply attempt by ID, scoped to this user."""
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM apply_attempts WHERE id = %s AND user_id = %s",
                (attempt_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


# ── Deprecated stubs (kept for import compatibility) ─────────────────────────

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

def get_source_analytics(user_id: str) -> list[dict]:
    """Retrieve yield, dedupe rates, and score distributions grouped by source board."""
    query = """
    WITH fetch_stats AS (
        SELECT lower(board) as site_lower,
               SUM(raw_count) as total_raw,
               SUM(filtered_count) as total_filtered,
               SUM(inserted_count) as total_inserted
        FROM source_metrics
        WHERE user_id = %s
        GROUP BY lower(board)
    ),
    job_stats AS (
        SELECT lower(site) as site_lower,
               COUNT(*) as total_jobs,
               COUNT(CASE WHEN score >= 7 THEN 1 END) as strong_matches,
               COUNT(CASE WHEN score >= 4 AND score < 7 THEN 1 END) as maybe_matches,
               COUNT(CASE WHEN score IS NOT NULL AND score < 4 THEN 1 END) as no_matches,
               COUNT(score) as scored_count,
               AVG(score) as avg_score
        FROM jobs
        WHERE user_id = %s
        GROUP BY lower(site)
    )
    SELECT
        COALESCE(j.site_lower, f.site_lower) as board,
        COALESCE(f.total_raw, 0) as total_raw,
        COALESCE(f.total_filtered, 0) as total_filtered,
        COALESCE(f.total_inserted, 0) as total_inserted,
        COALESCE(j.total_jobs, 0) as db_total,
        COALESCE(j.scored_count, 0) as scored_count,
        COALESCE(j.strong_matches, 0) as strong_matches,
        COALESCE(j.maybe_matches, 0) as maybe_matches,
        COALESCE(j.no_matches, 0) as no_matches,
        COALESCE(j.avg_score, 0.0) as avg_score
    FROM job_stats j
    FULL OUTER JOIN fetch_stats f ON j.site_lower = f.site_lower
    ORDER BY COALESCE(f.total_raw, 0) DESC, COALESCE(j.strong_matches, 0) DESC
    """
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (user_id, user_id))
            return [dict(row) for row in cur.fetchall()]

