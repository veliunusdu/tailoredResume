"""
Resume storage and retrieval using the SQLite resumes table.

Supports uploading markdown text directly and optionally storing a local/cloud path.
"""
from __future__ import annotations

import json
import time
import uuid

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
    `storage_path` is an optional path/URL to the raw file.
    """
    from app.llm import extract_structured_profile, embed_text

    resume_id = str(uuid.uuid4())
    now = time.time()

    _logger.info("Extracting structured profile for resume '%s'...", filename)
    structured_data = extract_structured_profile(content)
    structured_json = json.dumps(structured_data) if structured_data else None

    embedding = None
    if structured_json:
        _logger.info("Generating vector embedding for resume '%s'...", filename)
        embedding = embed_text(structured_json)

    with get_connection() as conn:
        conn.execute("""
            INSERT INTO resumes (id, user_id, filename, content, structured_data, embedding, storage_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            resume_id, user_id, filename, content,
            structured_json,
            json.dumps(embedding) if embedding else None,
            storage_path, now,
        ))

    _logger.info("✅ Saved resume '%s' for user %s (id=%s)", filename, user_id, resume_id)
    return resume_id


def get_resumes(user_id: str) -> list[dict]:
    """Return all resumes for a user (without the full content to keep payload small)."""
    with get_connection(user_id) as conn:
        rows = conn.execute("""
            SELECT id, user_id, filename, storage_path, created_at,
                   SUBSTR(content, 1, 200) AS preview, structured_data
            FROM resumes
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,)).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            sd = d.get("structured_data")
            if isinstance(sd, str):
                try:
                    d["structured_data"] = json.loads(sd)
                except Exception:
                    pass
            result.append(d)
        return result


def get_resume_by_id(resume_id: str, user_id: str) -> dict | None:
    """Return a single resume including its full content, scoped to this user."""
    with get_connection(user_id) as conn:
        row = conn.execute(
            "SELECT * FROM resumes WHERE id = ? AND user_id = ?",
            (resume_id, user_id),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        for key in ("structured_data", "embedding"):
            val = d.get(key)
            if isinstance(val, str):
                try:
                    d[key] = json.loads(val)
                except Exception:
                    pass
        return d


def delete_resume(resume_id: str, user_id: str) -> bool:
    """Delete a resume. Returns True if deleted, False if not found."""
    with get_connection(user_id) as conn:
        conn.execute(
            "DELETE FROM resumes WHERE id = ? AND user_id = ?",
            (resume_id, user_id),
        )
        deleted = conn.execute("SELECT changes()").fetchone()[0] > 0
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
    with get_connection(user_id) as conn:
        rows = conn.execute(
            "SELECT id, filename, content, structured_data FROM resumes WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
        resumes = []
        for r in rows:
            d = dict(r)
            sd = d.get("structured_data")
            if isinstance(sd, str):
                try:
                    d["structured_data"] = json.loads(sd)
                except Exception:
                    pass
            resumes.append(d)

    if not resumes:
        return None, None

    # Deduplicate resumes by content to avoid unnecessary LLM calls
    unique_resumes = []
    seen_contents = set()
    for r in resumes:
        content_str = (
            json.dumps(r["structured_data"], indent=2)
            if r.get("structured_data")
            else r["content"]
        )
        import hashlib
        content_hash = hashlib.md5(content_str.encode("utf-8")).hexdigest()
        if content_hash not in seen_contents:
            seen_contents.add(content_hash)
            # attach the computed string so we don't have to recompute it later
            r["_content_str"] = content_str
            unique_resumes.append(r)
            
    resumes = unique_resumes

    if len(resumes) == 1:
        return resumes[0]["filename"], resumes[0]["_content_str"]

    # Multiple resumes — use LLM to pick the best one
    try:
        import litellm
        import instructor
        from pydantic import BaseModel, Field
        from app.config import GEMINI_API_KEY, GEMINI_MODEL

        class ProfileSelection(BaseModel):
            selected_id: str = Field(description="The profile ID of the most relevant resume")
            reason: str = Field(description="Brief reason for selection")

        profiles_summary = ""
        profiles_map: dict[str, dict] = {}
        for r in resumes:
            content_str = r["_content_str"]
            profiles_map[r["id"]] = r
            profiles_summary += f"\n--- Profile ID: {r['id']} (Filename: {r['filename']}) ---\n{content_str[:800]}...\n"

        prompt = f"""
You are an expert recruiter. Route the JOB DESCRIPTION to the most suitable candidate profile.
Choose the ONE Profile ID that best fits the job requirements.

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

        selected = response.selected_id
        if selected in profiles_map:
            _logger.info("🤖 AI selected profile ID '%s'. Reason: %s", selected, response.reason)
            return profiles_map[selected]["filename"], profiles_map[selected]["_content_str"]

        _logger.warning("AI selected unknown profile ID '%s', falling back to first.", selected)
    except Exception as exc:
        _logger.error("Failed to select best resume via LLM: %s. Using first.", exc)

    return resumes[0]["filename"], resumes[0]["_content_str"]
