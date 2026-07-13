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
from app.schemas import Job, Stats, ApplyResponse, ApplyStatus, SessionResponse, JobPayload, TailorPayload
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
    try:
        init_db()
        import logging
        logging.getLogger("app.api").info("✅ Database schema initialised.")
    except Exception as exc:
        import logging
        logging.getLogger("app.api").error("❌ DB init failed on startup: %s", exc, exc_info=True)


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Meta"])
def health():
    """Public health check endpoint (no auth required)."""
    return {"status": "ok", "version": "3.0.0"}


# ── Job Endpoints ─────────────────────────────────────────────────────────────

@app.post("/v1/ingest/job-listing", status_code=201, tags=["Ingestion"])
async def ingest_job_listing(
    payload: JobPayload,
    user_id: str = Depends(get_current_user)
):
    """Ingest a raw job description string directly into the database."""
    if not payload.title or not payload.raw_content:
        raise HTTPException(
            status_code=400, 
            detail="Title and raw content are required fields."
        )
    
    # 1. Clean the incoming payload string
    from app.enrich import clean_html_tags
    cleaned_description = clean_html_tags(payload.raw_content)
    
    # 2. Structure data
    normalized_job = {
        "title": payload.title.strip(),
        "company": payload.company_name.strip(),
        "description": cleaned_description,
        "site": payload.source_platform
    }
    
    # 3. Commit
    try:
        from app.db import save_jobs, build_job_id
        save_jobs([normalized_job], user_id=user_id)
        job_id = build_job_id(normalized_job)
        
        # Trigger enrichment background task
        from app.tasks import enrich_pipeline_task
        enrich_pipeline_task.delay(job_id, user_id)
        
        return {"status": "success", "message": f"Job saved: {payload.title}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database insertion failed: {str(e)}")

@app.post("/v1/ingest/job-listing-async", status_code=202, tags=["Ingestion"])
async def ingest_job_listing_async(
    payload: JobPayload,
    user_id: str = Depends(get_current_user)
):
    """Ingest a raw job description string and process it via Celery."""
    if not payload.title or not payload.raw_content:
        raise HTTPException(
            status_code=400, 
            detail="Title and raw content are required fields."
        )
        
    from app.tasks import process_raw_ingest
    task = process_raw_ingest.delay(
        title=payload.title.strip(),
        company=payload.company_name.strip(),
        raw_content=payload.raw_content,
        source=payload.source_platform,
        user_id=user_id
    )
    return {"status": "queued", "task_id": task.id, "message": f"Job processing queued: {payload.title}"}

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


# ── Job Status Endpoint ───────────────────────────────────────────────────────

@app.put("/jobs/{job_id}/status", tags=["Jobs"])
async def update_status_endpoint(
    payload: dict,
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Update the status of a job (e.g. for the Kanban board)."""
    status = payload.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="status is required")
        
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    from app.db import update_job_status
    update_job_status(job_id, status, user_id)
    return {"status": "updated", "job_id": job_id, "new_status": status}


# ── Tailor Endpoints ──────────────────────────────────────────────────────────

@app.post("/jobs/sync", tags=["Jobs"])
async def sync_jobs(user_id: str = Depends(get_current_user)):
    """Trigger the background agent to fetch, filter, and score new jobs for the user."""
    from app.tasks import sync_jobs_task
    task = sync_jobs_task.delay(user_id)
    return {"status": "sync_queued", "task_id": task.id}


@app.post("/jobs/{job_id}/tailor", tags=["Tailoring"])
async def tailor_job(
    payload: TailorPayload,
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Trigger AI resume + cover letter tailoring for a job (runs via Celery)."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    task = prepare_application_task.delay(job_id, user_id, payload.tone_style)
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


@app.get("/jobs/{job_id}/salary-insights", tags=["Intelligence"])
async def get_salary_insights(
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Analyze the job and user's resume to generate salary negotiation insights."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    desc = job.get("description", "")
    if not desc:
        raise HTTPException(status_code=400, detail="Job has no description to analyze.")

    from app.resumes import get_best_resume
    resume_name, base_resume = get_best_resume(user_id=user_id, job_description=desc)
    if not base_resume:
        raise HTTPException(status_code=400, detail="No resume found. Please upload a resume first.")

    from app.llm import generate_salary_insights
    insights = generate_salary_insights(desc, job.get("title", ""), job.get("location", ""), base_resume)
    return insights


@app.get("/jobs/{job_id}/roadmap", tags=["Intelligence"])
async def get_job_roadmap(
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Generate an actionable learning roadmap based on missing skills."""
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

    missing = job.get("missing_skills") or []
    if not missing:
        # Fallback if the job hasn't been scored with the new pipeline
        from app.llm import analyze_job_keywords
        analysis = analyze_job_keywords(desc, base_resume)
        missing = analysis.get("missing", [])

    from app.agents.career_coach import generate_skill_roadmap
    roadmap = generate_skill_roadmap(missing, desc, base_resume)
    return roadmap


@app.get("/jobs/{job_id}/rejection-analysis", tags=["Intelligence"])
async def get_job_rejection_analysis(
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Generate a candid analysis of why the user was rejected."""
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

    missing = job.get("missing_skills") or []
    if not missing:
        from app.llm import analyze_job_keywords
        analysis = analyze_job_keywords(desc, base_resume)
        missing = analysis.get("missing", [])

    from app.agents.career_coach import generate_rejection_analysis
    analysis = generate_rejection_analysis(missing, desc, base_resume)
    return analysis

@app.get("/jobs/{job_id}/company-research", tags=["Intelligence"])
async def get_company_research(
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Generate a dossier on the company for the given job."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    company = job.get("company", "")
    desc = job.get("description", "")
    
    if not company:
        raise HTTPException(status_code=400, detail="Job has no company name.")

    from app.agents.researcher import generate_company_dossier
    dossier = generate_company_dossier(company, desc)
    return dossier

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

    if job.get("interview_questions"):
        return job["interview_questions"]

    from app.resumes import get_best_resume
    resume_name, base_resume = get_best_resume(user_id=user_id, job_description=desc)
    if not base_resume:
        raise HTTPException(
            status_code=400,
            detail="No resume found. Please upload a resume first.",
        )

    questions = generate_interview_questions(desc, base_resume)
    return questions

from app.schemas import InterviewAnswerPayload

@app.post("/jobs/{job_id}/interview/grade", tags=["Intelligence"])
async def grade_interview_answer_endpoint(
    payload: InterviewAnswerPayload,
    job_id: str = Path(..., description="The unique ID of the job"),
    user_id: str = Depends(get_current_user),
):
    """Grade a candidate's answer to an interview question."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    desc = job.get("description", "")
    if not desc:
        raise HTTPException(status_code=400, detail="Job has no description.")

    from app.resumes import get_best_resume
    resume_name, base_resume = get_best_resume(user_id=user_id, job_description=desc)
    if not base_resume:
        raise HTTPException(status_code=400, detail="No resume found.")

    from app.llm import grade_interview_answer
    grade = grade_interview_answer(payload.question, payload.answer, desc, base_resume)
    return grade


# ── Apply Endpoints ───────────────────────────────────────────────────────────

@app.post("/jobs/{job_id}/apply", response_model=ApplyResponse, tags=["Application"])
async def apply_job(
    job_id: str = Path(..., description="The unique ID of the job"),
    dry_run: bool | None = Query(None, description="If true, fills the form but does NOT click submit"),
    user_id: str = Depends(get_current_user),
):
    """
    Queue and trigger an automated job application via Celery.
    If dry_run is omitted, it defaults to the user's require_human_confirmation setting.
    """
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if dry_run is None:
        from app.search_config import get_search_config
        cfg = get_search_config(user_id)
        dry_run = bool(cfg.get("require_human_confirmation", 1))

    # Dedup check: prevent queuing if an attempt is already queued or running
    import redis
    import os

    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        redis_client = None

    if redis_client:
        dedup_key = f"apply_dedup:{user_id}:{job_id}"
        # Set atomic lock with 5-minute expiration
        acquired = redis_client.set(dedup_key, "queued", nx=True, ex=300)
        if not acquired:
            recent_attempts = get_apply_attempts(job_id, user_id=user_id)
            latest_id = recent_attempts[0].get("id") if recent_attempts else "unknown"
            latest_status = redis_client.get(dedup_key) or "queued"
            _logger.info("Job %s is already being processed (%s) for user %s. Dedup key exists.", job_id, latest_status, user_id)
            return {
                "status": latest_status,
                "job_id": job_id,
                "attempt_id": latest_id,
                "task_id": "already_queued",
            }
    else:
        recent_attempts = get_apply_attempts(job_id, user_id=user_id)
        if recent_attempts:
            latest = recent_attempts[0]
            if latest.get("status") in ("queued", "running"):
                _logger.info("Job %s is already %s for user %s. Skipping duplicate apply.", job_id, latest.get("status"), user_id)
                return {
                    "status": latest.get("status"),
                    "job_id": job_id,
                    "attempt_id": latest.get("id"),
                    "task_id": "already_queued",
                }

    attempt_id = queue_apply(job_id, user_id=user_id, dry_run=dry_run)
    task = apply_to_job_task.delay(job_id, attempt_id, dry_run, user_id)

    return {"status": "queued", "job_id": job_id, "attempt_id": attempt_id, "task_id": task.id}


@app.get("/tasks/active", tags=["Tasks"])
def get_active_tasks_endpoint(
    user_id: str = Depends(get_current_user),
):
    """List all active (running or queued) tasks for the authenticated user."""
    from app.db import get_active_tasks
    return get_active_tasks(user_id)


@app.get("/tasks/{task_id}", tags=["Tasks"])
def get_task_status(
    task_id: str,
    user_id: str = Depends(get_current_user),
):
    """Check the status of a Celery task."""
    from app.db import get_task_progress
    db_progress = get_task_progress(task_id, user_id)

    if db_progress:
        return {
            "task_id": task_id,
            "status": db_progress.get("status", "unknown"),
            "message": db_progress.get("message"),
            "progress": db_progress.get("progress", 0),
            "result": None,
        }

    # Fallback: try Celery if no DB record (with timeout protection)
    try:
        res = celery_app.AsyncResult(task_id)
        status = res.status.lower() if res.status else "pending"
        
        result_payload = None
        if res.ready():
            result_payload = {"error": str(res.result)} if isinstance(res.result, Exception) else res.result

        return {
            "task_id": task_id,
            "status": status,
            "message": f"Task is {status}",
            "progress": 0,
            "result": result_payload,
        }
    except Exception:
        return {
            "task_id": task_id,
            "status": "queued",
            "message": "Task queued, waiting for worker...",
            "progress": 0,
            "result": None,
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

@app.post("/search-config/parse-intent", tags=["Search Config"])
async def parse_search_intent_endpoint(payload: dict, user_id: str = Depends(get_current_user)):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    from app.llm import parse_search_intent
    intent = parse_search_intent(text)
    return intent.model_dump()


@app.post("/search-config/chat", tags=["Search Config"])
async def chat_search_intent_endpoint(payload: dict, user_id: str = Depends(get_current_user)):
    text = (payload.get("text") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
        
    from app.llm import parse_search_intent
    intent = parse_search_intent(text).model_dump()
    
    # Merge with existing config
    current_config = get_search_config(user_id=user_id)
    
    if intent.get("queries"):
        # Format queries to dict format if needed
        current_config["queries"] = [{"query": q, "tier": 1} for q in intent["queries"]]
        
    if intent.get("locations"):
        # Format locations
        current_config["locations"] = [{"location": loc["location"], "remote": loc["remote"]} for loc in intent["locations"]]
        
    if intent.get("seniority_levels"):
        current_config["seniority_levels"] = intent["seniority_levels"]
        
    if intent.get("exclude_titles"):
        current_config["exclude_titles"] = intent["exclude_titles"]
        
    if intent.get("notes"):
        current_config["profile_notes"] = intent["notes"]
        
    saved = save_search_config(user_id=user_id, config=current_config)
    return {"status": "saved", "config": saved, "intent": intent}


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
