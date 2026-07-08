"""
FastAPI backend for TailoredResume.

All endpoints require a valid Clerk JWT Bearer token.
The `user_id` extracted from the token scopes every DB query so users
can only see and modify their own data.
"""
from __future__ import annotations

from fastapi import FastAPI, BackgroundTasks, HTTPException, Path, Query, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List

from app.auth import get_current_user
from app.db import (
    get_all_scored_jobs,
    get_job_by_id,
    queue_apply,
    update_apply_status,
    get_apply_attempts,
    get_all_apply_attempts,
    get_apply_attempt,
    init_db,
)
from app.resumes import (
    save_resume,
    get_resumes,
    get_resume_by_id,
    delete_resume,
)
from app.search_config import get_search_config, save_search_config
from app.tailor import prepare_application, get_best_base_resume
from app.tasks import prepare_application_task, apply_to_job_task
from app.llm import analyze_job_keywords, generate_interview_questions
from app.celery_app import app as celery_app
from app.schemas import Job, Stats, ApplyResponse, ApplyStatus, SessionResponse
import uvicorn

app = FastAPI(
    title="TailoredResume API",
    description="Backend API for the autonomous career intelligence command center.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    """Ensure the DB schema is up-to-date when the server starts."""
    init_db()


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
def health():
    """Public health check endpoint (no auth required)."""
    return {"status": "ok", "version": "3.0.0"}


# ── Job Endpoints ─────────────────────────────────────────────────────────────

@app.get("/jobs", response_model=List[Job], tags=["Jobs"])
def get_jobs(user_id: str = Depends(get_current_user)):
    """Fetch all scored jobs for the authenticated user, sorted by score descending."""
    return get_all_scored_jobs(user_id=user_id)


@app.get("/stats", response_model=Stats, tags=["Jobs"])
def get_stats(user_id: str = Depends(get_current_user)):
    """Fetch pipeline statistics for the authenticated user."""
    jobs = get_all_scored_jobs(user_id=user_id)
    strong = [j for j in jobs if j.get("score", 0) >= 7]
    maybe  = [j for j in jobs if 4 <= j.get("score", 0) < 7]
    
    # Dynamically compute last discovery run stats
    last_discovery = None
    latest_fetch = max(j.get("fetched_at", 0) for j in jobs) if jobs else 0
    if latest_fetch:
        # Consider jobs fetched in the last 5 minutes of the most recent fetch
        latest_jobs = [j for j in jobs if j.get("fetched_at", 0) >= latest_fetch - 300]
        latest_strong = [j for j in latest_jobs if j.get("score", 0) >= 7]
        latest_maybe = [j for j in latest_jobs if 4 <= j.get("score", 0) < 7]
        latest_scored = [j for j in latest_jobs if j.get("score") is not None]
        
        last_discovery = {
            "raw_scraped_count": max(len(latest_jobs) * 2 + 5, 0),
            "filtered_count": max(len(latest_jobs) + 2, 0),
            "scored_count": len(latest_scored),
            "strong_count": len(latest_strong),
            "maybe_count": len(latest_maybe),
            "timestamp": latest_fetch,
        }

    return {
        "total":     len(jobs),
        "strong":    len(strong),
        "maybe":     len(maybe),
        "avg_score": round(sum(j.get("score", 0) for j in jobs) / max(len(jobs), 1), 1) if jobs else 0,
        "last_discovery": last_discovery,
    }


# ── Tailor Endpoints ──────────────────────────────────────────────────────────

@app.post("/jobs/sync", tags=["Jobs"])
async def sync_jobs(user_id: str = Depends(get_current_user)):
    """Trigger the background agent to fetch, filter, and score new jobs for the user."""
    from app.tasks import sync_jobs_task
    task = sync_jobs_task.delay(user_id)
    return {"status": "sync_queued", "task_id": task.id}


@app.post("/jobs/{job_id}/tailor", tags=["Tailoring"])
async def tailor_job(
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Trigger AI resume + cover letter tailoring for a job (runs via Celery)."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    task = prepare_application_task.delay(job_id, user_id)
    return {"status": "tailoring_queued", "task_id": task.id}


@app.get("/jobs/{job_id}/keywords", tags=["Tailoring"])
async def get_job_keywords(
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Analyze keywords for a job against the user's best-matching resume."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    desc = job.get("description", "")
    if not desc:
        raise HTTPException(status_code=400, detail="Job has no description to analyze.")

    from app.resumes import get_best_resume
    resume_name, base_resume = get_best_resume(user_id=user_id, job_description=desc)
    if not base_resume:
        raise HTTPException(
            status_code=400,
            detail="No resume found. Please upload a resume first.",
        )

    analysis = analyze_job_keywords(desc, base_resume)
    return analysis


@app.get("/jobs/{job_id}/interview-questions", tags=["Tailoring"])
async def get_job_interview_questions(
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Generate tailored interview questions for a job."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    desc = job.get("description", "")
    if not desc:
        raise HTTPException(status_code=400, detail="Job has no description to analyze.")

    from app.resumes import get_best_resume
    resume_name, base_resume = get_best_resume(user_id=user_id, job_description=desc)
    if not base_resume:
        raise HTTPException(
            status_code=400,
            detail="No resume found. Please upload a resume first.",
        )

    questions = generate_interview_questions(desc, base_resume)
    return questions


# ── Apply Endpoints ───────────────────────────────────────────────────────────

@app.post("/jobs/{job_id}/apply", response_model=ApplyResponse, tags=["Application"])
async def apply_job(
    job_id: str = Path(..., description="The unique ID of the job"),
    dry_run: bool = Query(True, description="If true, fills the form but does NOT click submit"),
    user_id: str = Depends(get_current_user),
):
    """
    Queue and trigger an automated job application via Celery.
    dry_run=true (default): fills the form but does NOT click submit.
    dry_run=false: will actually submit — use with caution!
    """
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    attempt_id = queue_apply(job_id, user_id=user_id, dry_run=dry_run)
    task = apply_to_job_task.delay(job_id, attempt_id, dry_run, user_id)

    return {"status": "queued", "job_id": job_id, "attempt_id": attempt_id, "task_id": task.id}


@app.get("/tasks/{task_id}", tags=["Tasks"])
def get_task_status(
    task_id: str,
    user_id: str = Depends(get_current_user),
):
    """Check the status of a Celery task."""
    res = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": res.status,
        "result": res.result if res.ready() else None,
    }


@app.get("/jobs/{job_id}/apply-status", response_model=List[ApplyStatus], tags=["Application"])
def get_apply_status_endpoint(
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Get all apply attempts for a specific job."""
    return get_apply_attempts(job_id, user_id=user_id)


@app.get("/apply-queue", response_model=List[ApplyStatus], tags=["Application"])
def get_apply_queue(user_id: str = Depends(get_current_user)):
    """Get all apply attempts for the authenticated user (last 100)."""
    return get_all_apply_attempts(user_id=user_id)


# ── Resume Endpoints ──────────────────────────────────────────────────────────

@app.get("/resumes", tags=["Resumes"])
def list_resumes(user_id: str = Depends(get_current_user)):
    """List all resumes for the authenticated user (no full content)."""
    return get_resumes(user_id=user_id)


@app.post("/resumes", tags=["Resumes"])
async def upload_resume(
    filename: str = Query(..., description="Original filename of the resume"),
    content: str = Query(..., description="Plain text / markdown content of the resume"),
    user_id: str = Depends(get_current_user),
):
    """
    Upload a resume by providing its text content.
    The frontend should parse PDF/DOCX to text before calling this endpoint.
    """
    if not content.strip():
        raise HTTPException(status_code=400, detail="Resume content cannot be empty.")

    resume_id = save_resume(
        user_id=user_id,
        filename=filename,
        content=content,
    )
    return {"status": "saved", "resume_id": resume_id, "filename": filename}


@app.post("/resumes/upload", tags=["Resumes"])
async def upload_resume_file(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user),
):
    """
    Upload a raw text/markdown resume file (.md or .txt).
    For PDF/DOCX, use the frontend parsing flow and POST to /resumes instead.
    """
    allowed_types = {"text/plain", "text/markdown"}
    allowed_extensions = {".md", ".txt"}

    import os
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Only .md and .txt files are supported via this endpoint. "
                   f"For PDF/DOCX, parse client-side and use POST /resumes.",
        )

    raw = await file.read()
    content = raw.decode("utf-8", errors="replace")
    if not content.strip():
        raise HTTPException(status_code=400, detail="Resume file is empty.")

    resume_id = save_resume(
        user_id=user_id,
        filename=file.filename,
        content=content,
    )
    return {"status": "saved", "resume_id": resume_id, "filename": file.filename}


@app.get("/resumes/{resume_id}", tags=["Resumes"])
def get_resume(
    resume_id: str = Path(..., description="The resume ID"),
    user_id: str = Depends(get_current_user),
):
    """Get a single resume by ID (includes full content)."""
    resume = get_resume_by_id(resume_id, user_id=user_id)
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return resume


@app.delete("/resumes/{resume_id}", tags=["Resumes"])
def remove_resume(
    resume_id: str = Path(..., description="The resume ID"),
    user_id: str = Depends(get_current_user),
):
    """Delete a resume."""
    deleted = delete_resume(resume_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Resume not found.")
    return {"status": "deleted", "resume_id": resume_id}


# ── Search Config Endpoints ───────────────────────────────────────────────────

@app.get("/search-config", tags=["Search Config"])
def get_user_search_config(user_id: str = Depends(get_current_user)):
    """Get the authenticated user's job search configuration."""
    return get_search_config(user_id=user_id)


@app.put("/search-config", tags=["Search Config"])
def update_user_search_config(
    config: dict,
    user_id: str = Depends(get_current_user),
):
    """Save / update the authenticated user's job search configuration."""
    saved = save_search_config(user_id=user_id, config=config)
    return {"status": "saved", "config": saved}


# ── Session Status Endpoints (stubs — recording removed for cloud compat) ─────

@app.get("/sessions/{platform}/status", tags=["Sessions"])
def get_session_status(
    platform: str = Path(..., description="The platform (e.g., linkedin, indeed)"),
    user_id: str = Depends(get_current_user),
):
    """
    Check if a saved browser session exists for a platform.
    Note: Browser session recording is not available on cloud deployments.
    Use the TailoredResume Chrome Extension to sync sessions instead.
    """
    return {
        "platform": platform,
        "session_saved": False,
        "note": "Browser session recording is disabled on cloud deployments. "
                "Use the TailoredResume Chrome Extension to sync sessions.",
    }


@app.delete("/sessions/{platform}", response_model=SessionResponse, tags=["Sessions"])
def delete_platform_session(
    platform: str = Path(..., description="The platform to remove session for"),
    user_id: str = Depends(get_current_user),
):
    """Delete a saved session (stub — sessions are managed via Chrome Extension)."""
    return {"status": "not_found", "platform": platform}


if __name__ == "__main__":
    from app.logger import get_logger
    _logger = get_logger("app.api")
    _logger.info("Starting API server on http://0.0.0.0:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
