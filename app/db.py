"""
SQLite3-backed persistence for jobs, resumes, apply attempts, search config, and tasks.

Uses Python's built-in sqlite3 module — no external dependencies required.
Thread-safe via threading.local() per-thread connections.

Database file location: app.db in the project root.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Generator

from app.config import JOBS_CACHE_TTL_SEC
from app.logger import get_logger

_logger = get_logger(__name__)

# ── Database path ─────────────────────────────────────────────────────────────

_DB_PATH = Path(__file__).resolve().parents[1] / "app.db"

# ── Thread-local connection ───────────────────────────────────────────────────

_local = threading.local()


def _get_connection() -> sqlite3.Connection:
    """Return (or create) a per-thread SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")   # concurrent readers
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn = conn
    return _local.conn


@contextmanager
def get_connection(user_id: str | None = None) -> Generator:
    """Yield a SQLite connection, committing on success and rolling back on error."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ── Schema Initialisation ─────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables if they don't exist. Safe to call multiple times."""
    conn = _get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id              TEXT NOT NULL,
            user_id         TEXT NOT NULL,
            title           TEXT,
            company         TEXT,
            location        TEXT,
            url             TEXT,
            date_posted     TEXT,
            salary          TEXT,
            description     TEXT,
            site            TEXT,
            tags            TEXT DEFAULT '[]',
            fetched_at      REAL,
            score           INTEGER,
            verdict         TEXT,
            reason          TEXT,
            tailored_resume TEXT,
            cover_letter    TEXT,
            interview_questions TEXT,
            required_skills TEXT,
            missing_skills  TEXT,
            found_skills    TEXT,
            status          TEXT DEFAULT 'saved',
            skill_match_score INTEGER,
            embedding       TEXT,
            PRIMARY KEY (id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_jobs_user_score
            ON jobs (user_id, score DESC);

        CREATE INDEX IF NOT EXISTS idx_jobs_user_fetched
            ON jobs (user_id, fetched_at DESC);

        CREATE TABLE IF NOT EXISTS source_metrics (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id          TEXT NOT NULL,
            user_id         TEXT NOT NULL,
            board           TEXT NOT NULL,
            raw_count       INTEGER DEFAULT 0,
            filtered_count  INTEGER DEFAULT 0,
            inserted_count  INTEGER DEFAULT 0,
            fetched_at      REAL NOT NULL
        );

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
            applied_at          REAL,
            created_at          REAL
        );

        CREATE INDEX IF NOT EXISTS idx_apply_attempts_user_job
            ON apply_attempts (user_id, job_id);

        CREATE TABLE IF NOT EXISTS resumes (
            id              TEXT PRIMARY KEY,
            user_id         TEXT NOT NULL,
            filename        TEXT NOT NULL,
            content         TEXT NOT NULL,
            structured_data TEXT,
            embedding       TEXT,
            storage_path    TEXT,
            created_at      REAL
        );

        CREATE INDEX IF NOT EXISTS idx_resumes_user
            ON resumes (user_id);

        CREATE TABLE IF NOT EXISTS user_search_config (
            user_id          TEXT PRIMARY KEY,
            queries          TEXT DEFAULT '[]',
            locations        TEXT DEFAULT '[]',
            boards           TEXT DEFAULT '["indeed","linkedin","glassdoor"]',
            exclude_titles   TEXT DEFAULT '[]',
            seniority_levels TEXT DEFAULT '[]',
            profile_notes    TEXT,
            results_per_site INTEGER DEFAULT 20,
            hours_old        INTEGER DEFAULT 72,
            require_human_confirmation INTEGER DEFAULT 1,
            updated_at       REAL
        );

        CREATE TABLE IF NOT EXISTS task_progress (
            task_id    TEXT PRIMARY KEY,
            user_id    TEXT NOT NULL,
            status     TEXT NOT NULL,
            message    TEXT NOT NULL,
            progress   INTEGER DEFAULT 0,
            updated_at REAL
        );

        CREATE TABLE IF NOT EXISTS selector_patches (
            broken_selector     TEXT PRIMARY KEY,
            patched_selector    TEXT NOT NULL,
            is_verified         INTEGER DEFAULT 0,
            created_at          REAL
        );
    """)
    conn.commit()
    _logger.info("✅ SQLite database schema ready at %s", _DB_PATH)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows) -> list[dict]:
    return [dict(r) for r in rows]


def _row_to_job(row: sqlite3.Row | dict) -> dict:
    d = dict(row)
    tags = d.get("tags")
    if isinstance(tags, str):
        try:
            d["tags"] = json.loads(tags)
        except Exception:
            d["tags"] = []
    elif tags is None:
        d["tags"] = []
    # Parse JSON columns that may be stored as strings
    for col in ("interview_questions", "required_skills", "missing_skills", "found_skills", "embedding"):
        val = d.get(col)
        if isinstance(val, str):
            try:
                d[col] = json.loads(val)
            except Exception:
                pass
    return d


# ── Task Progress ─────────────────────────────────────────────────────────────

def update_task_progress(
    task_id: str,
    user_id: str,
    status: str,
    message: str,
    progress: int = 0,
) -> None:
    now = time.time()
    with get_connection(user_id) as conn:
        conn.execute("""
            INSERT INTO task_progress (task_id, user_id, status, message, progress, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(task_id) DO UPDATE SET
                status     = excluded.status,
                message    = excluded.message,
                progress   = excluded.progress,
                updated_at = excluded.updated_at
        """, (task_id, user_id, status, message, progress, now))


def get_task_progress(task_id: str, user_id: str) -> dict | None:
    with get_connection(user_id) as conn:
        row = conn.execute(
            "SELECT * FROM task_progress WHERE task_id = ? AND user_id = ?",
            (task_id, user_id),
        ).fetchone()
        return _row_to_dict(row)


def get_active_tasks(user_id: str) -> list[dict]:
    with get_connection(user_id) as conn:
        rows = conn.execute(
            "SELECT * FROM task_progress WHERE user_id = ? AND status IN ('running', 'queued', 'pending') ORDER BY updated_at DESC",
            (user_id,),
        ).fetchall()
        return _rows_to_list(rows)


# ── Tailored Materials ─────────────────────────────────────────────────────────

def save_tailored_materials(
    job_id: str,
    user_id: str,
    tailored_resume: str,
    cover_letter: str | None = None,
    interview_questions: list | None = None,
) -> None:
    with get_connection(user_id) as conn:
        conn.execute("""
            UPDATE jobs
            SET tailored_resume = ?, cover_letter = ?, interview_questions = ?
            WHERE id = ? AND user_id = ?
        """, (
            tailored_resume,
            cover_letter,
            json.dumps(interview_questions) if interview_questions else None,
            job_id,
            user_id,
        ))


def save_skill_analysis(
    job_id: str,
    user_id: str,
    required_skills: list,
    missing_skills: list,
    match_score: int,
) -> None:
    with get_connection(user_id) as conn:
        conn.execute("""
            UPDATE jobs
            SET required_skills = ?, missing_skills = ?, skill_match_score = ?
            WHERE id = ? AND user_id = ?
        """, (json.dumps(required_skills), json.dumps(missing_skills), match_score, job_id, user_id))


# ── Selector Patches ──────────────────────────────────────────────────────────

def get_selector_patch(broken_selector: str) -> str | None:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT patched_selector FROM selector_patches WHERE broken_selector = ?",
            (broken_selector,),
        ).fetchone()
        return row[0] if row else None


def save_selector_patch(broken_selector: str, patched_selector: str) -> None:
    now = time.time()
    with get_connection() as conn:
        conn.execute("""
            INSERT INTO selector_patches (broken_selector, patched_selector, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(broken_selector) DO UPDATE SET
                patched_selector = excluded.patched_selector,
                is_verified      = 0,
                created_at       = excluded.created_at
        """, (broken_selector, patched_selector, now))


def verify_selector_patch(broken_selector: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE selector_patches SET is_verified = 1 WHERE broken_selector = ?",
            (broken_selector,),
        )


# ── Job Helpers ───────────────────────────────────────────────────────────────

def build_job_id(job: dict) -> str:
    raw_key = (
        job.get("url")
        or f"{job.get('title', '')}|{job.get('company', '')}|{job.get('location', '')}"
    )
    return hashlib.sha256(raw_key.strip().lower().encode("utf-8")).hexdigest()


# ── Job CRUD ──────────────────────────────────────────────────────────────────

def save_jobs(jobs: list[dict], user_id: str, collector: Any = None) -> int:
    """Insert-or-ignore normalised jobs. Returns count of newly inserted rows."""
    from app.llm import embed_text
    inserted = 0
    now = time.time()

    with get_connection(user_id) as conn:
        for job in jobs:
            job_id = build_job_id(job)
            tags_json = json.dumps(job.get("tags", []))

            # Skip if already exists
            existing = conn.execute(
                "SELECT 1 FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id)
            ).fetchone()
            if existing:
                continue

            embed_payload = f"{job.get('title', '')} {job.get('company', '')} {tags_json} {job.get('description', '')}"
            embedding = embed_text(embed_payload)

            try:
                conn.execute("""
                    INSERT OR IGNORE INTO jobs (
                        id, user_id, title, company, location, url,
                        date_posted, salary, description, site, tags, fetched_at, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps(embedding) if embedding else None,
                ))
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
                    if collector:
                        collector.add_inserted(job.get("site", "unknown"), 1)
            except Exception as exc:
                _logger.warning("Failed to insert job %s: %s", job_id, exc)

    return inserted


def get_unscored_jobs(user_id: str) -> list[dict]:
    with get_connection(user_id) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? AND score IS NULL", (user_id,)
        ).fetchall()
        return [_row_to_job(r) for r in rows]


def rank_jobs_with_vector(job_ids: list[str], resume_id: str, user_id: str) -> dict[str, float]:
    """Cosine similarity between job embeddings and a resume embedding, computed in Python."""
    if not job_ids:
        return {}

    import math

    def cosine_similarity(v1, v2):
        if not v1 or not v2:
            return 0.0
        dot = sum(a * b for a, b in zip(v1, v2))
        na = math.sqrt(sum(a * a for a in v1))
        nb = math.sqrt(sum(b * b for b in v2))
        return dot / (na * nb) if na and nb else 0.0

    with get_connection(user_id) as conn:
        r_row = conn.execute(
            "SELECT embedding FROM resumes WHERE id = ? AND user_id = ?", (resume_id, user_id)
        ).fetchone()
        if not r_row or not r_row[0]:
            return {}
        resume_emb = json.loads(r_row[0]) if isinstance(r_row[0], str) else r_row[0]

        placeholders = ",".join("?" * len(job_ids))
        job_rows = conn.execute(
            f"SELECT id, embedding FROM jobs WHERE id IN ({placeholders}) AND user_id = ? AND embedding IS NOT NULL",
            (*job_ids, user_id),
        ).fetchall()

        return {
            jid: cosine_similarity(resume_emb, json.loads(j_emb) if isinstance(j_emb, str) else j_emb)
            for jid, j_emb in job_rows
        }


def get_all_scored_jobs(user_id: str) -> list[dict]:
    with get_connection(user_id) as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? AND score IS NOT NULL ORDER BY score DESC",
            (user_id,),
        ).fetchall()
        return [_row_to_job(r) for r in rows]


def get_job_by_id(job_id: str, user_id: str) -> dict | None:
    with get_connection(user_id) as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id)
        ).fetchone()
        return _row_to_job(row) if row else None


def save_score(job_id: str, result: dict, user_id: str) -> None:
    with get_connection(user_id) as conn:
        conn.execute("""
            UPDATE jobs
            SET score = ?, verdict = ?, reason = ?, found_skills = ?, missing_skills = ?
            WHERE id = ? AND user_id = ?
        """, (
            result.get("score"),
            result.get("verdict"),
            result.get("reason"),
            json.dumps(result.get("found_skills", [])),
            json.dumps(result.get("missing_skills", [])),
            job_id, user_id,
        ))


def update_job_status(job_id: str, status: str, user_id: str) -> None:
    with get_connection(user_id) as conn:
        conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ? AND user_id = ?",
            (status, job_id, user_id),
        )


def save_job_description(job_id: str, description: str, user_id: str) -> None:
    with get_connection(user_id) as conn:
        conn.execute(
            "UPDATE jobs SET description = ? WHERE id = ? AND user_id = ?",
            (description, job_id, user_id),
        )


def should_fetch_jobs(user_id: str) -> bool:
    with get_connection(user_id) as conn:
        row = conn.execute(
            "SELECT MAX(fetched_at) as last_fetch FROM jobs WHERE user_id = ?", (user_id,)
        ).fetchone()
        if not row or not row[0]:
            return True
        return (time.time() - row[0]) > JOBS_CACHE_TTL_SEC


# ── Apply Queue ───────────────────────────────────────────────────────────────

def queue_apply(job_id: str, user_id: str, dry_run: bool = True) -> str:
    attempt_id = str(uuid.uuid4())
    now = time.time()
    with get_connection(user_id) as conn:
        conn.execute("""
            INSERT INTO apply_attempts (id, user_id, job_id, status, dry_run, created_at)
            VALUES (?, ?, ?, 'queued', ?, ?)
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
    now = time.time()
    applied_at = now if status in ("success", "failed", "manual_required") else None
    with get_connection(user_id) as conn:
        conn.execute("""
            UPDATE apply_attempts
            SET status = ?, job_board = ?, error_msg = ?,
                screenshot = ?, ai_patch_suggestion = ?, applied_at = ?
            WHERE id = ? AND user_id = ?
        """, (status, job_board, error_msg, screenshot, ai_patch_suggestion, applied_at, attempt_id, user_id))


def get_apply_attempts(job_id: str, user_id: str) -> list[dict]:
    with get_connection(user_id) as conn:
        rows = conn.execute(
            "SELECT * FROM apply_attempts WHERE job_id = ? AND user_id = ? ORDER BY created_at DESC",
            (job_id, user_id),
        ).fetchall()
        return _rows_to_list(rows)


def get_all_apply_attempts(user_id: str) -> list[dict]:
    with get_connection(user_id) as conn:
        rows = conn.execute(
            "SELECT * FROM apply_attempts WHERE user_id = ? ORDER BY created_at DESC LIMIT 100",
            (user_id,),
        ).fetchall()
        return _rows_to_list(rows)


def get_apply_attempt(attempt_id: str, user_id: str) -> dict | None:
    with get_connection(user_id) as conn:
        row = conn.execute(
            "SELECT * FROM apply_attempts WHERE id = ? AND user_id = ?",
            (attempt_id, user_id),
        ).fetchone()
        return _row_to_dict(row)


# ── Analytics ─────────────────────────────────────────────────────────────────

def get_source_analytics(user_id: str) -> list[dict]:
    """Retrieve yield, dedupe rates, and score distributions grouped by source board."""
    with get_connection(user_id) as conn:
        # Fetch stats from source_metrics
        sm_rows = conn.execute("""
            SELECT LOWER(board) as site_lower,
                   SUM(raw_count) as total_raw,
                   SUM(filtered_count) as total_filtered,
                   SUM(inserted_count) as total_inserted
            FROM source_metrics
            WHERE user_id = ?
            GROUP BY LOWER(board)
        """, (user_id,)).fetchall()
        fetch_stats = {r["site_lower"]: dict(r) for r in sm_rows}

        # Job stats from jobs
        js_rows = conn.execute("""
            SELECT LOWER(site) as site_lower,
                   COUNT(*) as total_jobs,
                   SUM(CASE WHEN score >= 7 THEN 1 ELSE 0 END) as strong_matches,
                   SUM(CASE WHEN score >= 4 AND score < 7 THEN 1 ELSE 0 END) as maybe_matches,
                   SUM(CASE WHEN score IS NOT NULL AND score < 4 THEN 1 ELSE 0 END) as no_matches,
                   COUNT(score) as scored_count,
                   AVG(score) as avg_score
            FROM jobs
            WHERE user_id = ?
            GROUP BY LOWER(site)
        """, (user_id,)).fetchall()
        job_stats = {r["site_lower"]: dict(r) for r in js_rows}

        all_sites = set(fetch_stats.keys()) | set(job_stats.keys())
        results = []
        for site in all_sites:
            f = fetch_stats.get(site, {})
            j = job_stats.get(site, {})
            results.append({
                "board":          site,
                "total_raw":      f.get("total_raw", 0),
                "total_filtered": f.get("total_filtered", 0),
                "total_inserted": f.get("total_inserted", 0),
                "db_total":       j.get("total_jobs", 0),
                "scored_count":   j.get("scored_count", 0),
                "strong_matches": j.get("strong_matches", 0),
                "maybe_matches":  j.get("maybe_matches", 0),
                "no_matches":     j.get("no_matches", 0),
                "avg_score":      round(float(j.get("avg_score") or 0.0), 2),
            })
        results.sort(key=lambda x: (-x["total_raw"], -x["strong_matches"]))
        return results


# ── Deprecated stubs (kept for import compatibility) ──────────────────────────

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
