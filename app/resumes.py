"""
Resume storage and retrieval using the PostgreSQL resumes table.

Replaces the local DATA_DIR/*.md glob pattern with proper per-user DB storage.
Supports uploading markdown text directly and optionally storing an S3/Supabase path.
"""
from __future__ import annotations

import time
import uuid

import psycopg2.extras

from app.db import get_connection
from app.logger import get_logger

_logger = get_logger(__name__)


# ── CRUD ──────────────────────────────────────────────────────────────────────

def save_resume(
    user_id: str,
    filename: str,
    content: str,
    storage_path: str | None = None,
) -> str:
    """
    Save a resume for a user. Returns the new resume ID.
    `content` should be plain text / markdown extracted from the uploaded file.
    `storage_path` is an optional URL to the raw file in cloud storage.
    """
    resume_id = str(uuid.uuid4())
    now = time.time()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO resumes (id, user_id, filename, content, storage_path, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (resume_id, user_id, filename, content, storage_path, now))
    _logger.info("✅ Saved resume '%s' for user %s (id=%s)", filename, user_id, resume_id)
    return resume_id


def get_resumes(user_id: str) -> list[dict]:
    """Return all resumes for a user (without the full content to keep payload small)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT id, user_id, filename, storage_path, created_at,
                       LEFT(content, 200) AS preview
                FROM resumes
                WHERE user_id = %s
                ORDER BY created_at DESC
            """, (user_id,))
            return [dict(row) for row in cur.fetchall()]


def get_resume_by_id(resume_id: str, user_id: str) -> dict | None:
    """Return a single resume including its full content, scoped to this user."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM resumes WHERE id = %s AND user_id = %s",
                (resume_id, user_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def delete_resume(resume_id: str, user_id: str) -> bool:
    """Delete a resume. Returns True if deleted, False if not found."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM resumes WHERE id = %s AND user_id = %s",
                (resume_id, user_id),
            )
            deleted = cur.rowcount > 0
    if deleted:
        _logger.info("🗑️  Deleted resume %s for user %s", resume_id, user_id)
    return deleted


def get_best_resume(user_id: str, job_description: str) -> tuple[str | None, str | None]:
    """
    Find the best resume for this user given a job description.

    If the user has one resume, return it directly.
    If they have multiple, use the LLM to pick the most relevant one.
    Returns (filename, content) or (None, None) if no resumes exist.
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, filename, content FROM resumes WHERE user_id = %s ORDER BY created_at DESC",
                (user_id,),
            )
            resumes = [dict(r) for r in cur.fetchall()]

    if not resumes:
        return None, None

    if len(resumes) == 1:
        return resumes[0]["filename"], resumes[0]["content"]

    # Multiple resumes — use LLM to pick the best one
    try:
        import litellm
        import instructor
        from pydantic import BaseModel, Field
        from app.config import GEMINI_API_KEY, GEMINI_MODEL

        class ProfileSelection(BaseModel):
            selected_filename: str = Field(
                description="The filename of the most relevant resume"
            )
            reason: str = Field(description="Brief reason for selection")

        profiles_summary = ""
        profiles_map: dict[str, str] = {}
        for r in resumes:
            profiles_map[r["filename"]] = r["content"]
            profiles_summary += f"\n--- {r['filename']} ---\n{r['content'][:800]}...\n"

        prompt = f"""
You are an expert recruiter. Route the JOB DESCRIPTION to the most suitable candidate profile.
Choose the ONE resume filename that best fits the job requirements.

JOB DESCRIPTION:
{job_description[:2000]}

AVAILABLE PROFILES (Excerpts):
{profiles_summary}
"""
        model_name = GEMINI_MODEL
        if "gemini" in model_name and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"

        client = instructor.from_litellm(litellm.completion)
        response = client.chat.completions.create(
            model=model_name,
            response_model=ProfileSelection,
            messages=[{"role": "user", "content": prompt}],
            api_key=GEMINI_API_KEY,
        )

        selected = response.selected_filename
        if selected in profiles_map:
            _logger.info(
                "🤖 AI selected profile '%s'. Reason: %s", selected, response.reason
            )
            return selected, profiles_map[selected]

        _logger.warning("AI selected unknown profile '%s', falling back to first.", selected)
    except Exception as exc:
        _logger.error("Failed to select best resume via LLM: %s. Using first.", exc)

    return resumes[0]["filename"], resumes[0]["content"]
