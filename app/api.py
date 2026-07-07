import threading
from fastapi import FastAPI, BackgroundTasks, HTTPException, Path, Query, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from app.db import (
    get_all_scored_jobs,
    get_job_by_id,
    queue_apply,
    update_apply_status,
    get_apply_attempts,
    get_all_apply_attempts,
    get_user_api_key,
    get_discovery_stats,
)
from app.auth import get_current_user, User
from app.celery_app import app as celery_app
from app.sessions import record_session, session_exists, delete_session
from app.schemas import Job, Stats, ApplyResponse, ApplyStatus, SessionResponse, SecretPayload
import uvicorn

app = FastAPI(
    title="TailoredResume API",
    description="Backend API for the autonomous career intelligence command center.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Job Endpoints ─────────────────────────────────────────────────────────────

@app.get("/jobs", response_model=List[Job], tags=["Jobs"])
def get_jobs_endpoint(user: User = Depends(get_current_user)):
    """Fetch all scored jobs for the current user."""
    return get_all_scored_jobs(user.id)


@app.post("/jobs/discover", tags=["Jobs"])
async def discover_jobs(
    region: str = Query(None, description="The region to search in (e.g., global, turkey)"),
    user: User = Depends(get_current_user)
):
    """
    Trigger the discovery agent to fetch, filter, and score new jobs for the current user.
    This runs in a background thread to avoid blocking the API.
    """
    from app.agent import get_jobs
    
    def _run_discovery():
        try:
            get_jobs(user.id, region=region)
        except Exception as e:
            from app.logger import get_logger
            _logger = get_logger("app.api.discovery")
            _logger.error(f"Discovery failed for user {user.id}: {e}")
            from app.db import update_discovery_status
            update_discovery_status(user.id, "failed", f"Failed: {str(e)}")

    thread = threading.Thread(target=_run_discovery, daemon=True)
    thread.start()
    
    return {"status": "discovery_started", "region": region or "default"}


@app.get("/jobs/discover/status", tags=["Jobs"])
def get_discovery_status(user: User = Depends(get_current_user)):
    """Get the current discovery status and progress description."""
    from app.db import get_connection
    with get_connection() as conn:
        row = conn.execute(
            "SELECT discovery_status, discovery_progress FROM user_settings WHERE user_id = ?",
            (user.id,)
        ).fetchone()
        if row:
            return {
                "status": row["discovery_status"] or "idle",
                "progress": row["discovery_progress"] or ""
            }
    return {"status": "idle", "progress": ""}


@app.get("/stats", response_model=Stats, tags=["Jobs"])
def get_stats(user: User = Depends(get_current_user)):
    """Fetch pipeline statistics including totals and average match scores for the current user."""
    jobs = get_all_scored_jobs(user.id)
    strong = [j for j in jobs if j.get("score", 0) >= 7]
    maybe  = [j for j in jobs if 4 <= j.get("score", 0) < 7]
    
    last_discovery = get_discovery_stats(user.id)
    
    return {
        "total":     len(jobs),
        "strong":    len(strong),
        "maybe":     len(maybe),
        "avg_score": round(sum(j.get("score", 0) for j in jobs) / max(len(jobs), 1), 1) if jobs else 0,
        "last_discovery": last_discovery
    }


# ── Tailor Endpoint ───────────────────────────────────────────────────────────

@app.post("/jobs/{job_id}/tailor", tags=["Tailoring"])
async def tailor_job(
    job_id: str = Path(..., description="The unique ID of the job"),
    user: User = Depends(get_current_user)
):
    """Trigger AI resume + cover letter tailoring for a job (runs via Celery)."""
    job = get_job_by_id(user.id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    from app.tasks import prepare_application_task
    task = prepare_application_task.delay(user.id, job_id)
    return {"status": "tailoring_queued", "task_id": task.id}


@app.get("/jobs/{job_id}/keywords", tags=["Tailoring"])
async def get_job_keywords(
    job_id: str = Path(..., description="The unique ID of the job"),
    user: User = Depends(get_current_user)
):
    """Analyze keywords for a job against the base resume (on-the-fly)."""
    job = get_job_by_id(user.id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    desc = job.get("description", "")
    if not desc:
        raise HTTPException(status_code=400, detail="Job has no description to analyze.")
        
    from app.tailor import get_best_base_resume
    from app.llm import analyze_job_keywords
    
    resume_name, base_resume = get_best_base_resume(user.id, desc, api_key=get_user_api_key(user.id))
    if not base_resume:
        raise HTTPException(status_code=400, detail="Base resume not found. Please upload one first.")
    
    analysis = analyze_job_keywords(desc, base_resume, api_key=get_user_api_key(user.id))
    return analysis


@app.get("/jobs/{job_id}/interview-questions", tags=["Tailoring"])
async def get_job_interview_questions(
    job_id: str = Path(..., description="The unique ID of the job"),
    user: User = Depends(get_current_user)
):
    """Generate tailored interview questions for a job against the base resume (on-the-fly)."""
    job = get_job_by_id(user.id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    desc = job.get("description", "")
    if not desc:
        raise HTTPException(status_code=400, detail="Job has no description to analyze.")
        
    from app.tailor import get_best_base_resume
    from app.llm import generate_interview_questions
    
    resume_name, base_resume = get_best_base_resume(user.id, desc, api_key=get_user_api_key(user.id))
    if not base_resume:
        raise HTTPException(status_code=400, detail="Base resume not found. Please upload one first.")
    
    questions = generate_interview_questions(desc, base_resume, api_key=get_user_api_key(user.id))
    return questions


# ── Apply Endpoints ───────────────────────────────────────────────────────────

@app.post("/jobs/{job_id}/apply", response_model=ApplyResponse, tags=["Application"])
async def apply_job(
    job_id: str = Path(..., description="The unique ID of the job"), 
    dry_run: bool = Query(True, description="If true, fills the form but does NOT click submit"),
    user: User = Depends(get_current_user)
):
    """
    Queue and trigger an automated job application via Celery.
    """
    job = get_job_by_id(user.id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create a queued attempt record in Supabase
    attempt_id = queue_apply(user.id, job_id, dry_run=dry_run)

    # Offload to Celery worker
    from app.tasks import apply_to_job_task
    task = apply_to_job_task.delay(user.id, job_id, attempt_id, dry_run)

    return {"status": "queued", "job_id": job_id, "attempt_id": attempt_id, "task_id": task.id}


@app.get("/tasks/{task_id}", tags=["Tasks"])
def get_task_status(task_id: str, user: User = Depends(get_current_user)):
    """Check the status of a Celery task."""
    res = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": res.status,
        "result": res.result if res.ready() else None
    }


@app.get("/jobs/{job_id}/apply-status", response_model=List[ApplyStatus], tags=["Application"])
def get_apply_status_endpoint(
    job_id: str = Path(..., description="The unique ID of the job"),
    user: User = Depends(get_current_user)
):
    """Get all apply attempts for a specific job."""
    return get_apply_attempts(user.id, job_id)


@app.get("/apply-queue", response_model=List[ApplyStatus], tags=["Application"])
def get_apply_queue(user: User = Depends(get_current_user)):
    """Get all apply attempts across all jobs for the current user."""
    return get_all_apply_attempts(user.id)





# ── User Settings Endpoints ──────────────────────────────────────────────────

@app.get("/settings", tags=["Settings"])
def get_settings(user: User = Depends(get_current_user)):
    """Fetch search preferences for the current user."""
    from app.db import get_user_settings
    return get_user_settings(user.id)


@app.post("/settings", tags=["Settings"])
def update_settings(
    settings: dict, 
    user: User = Depends(get_current_user)
):
    """Update search preferences for the current user."""
    from app.db import save_user_settings
    save_user_settings(user.id, settings)
    return {"status": "updated"}


# ── Session Endpoints ─────────────────────────────────────────────────────────

@app.get("/sessions/{platform}/status", tags=["Sessions"])
def get_session_status(
    platform: str = Path(..., description="The platform (e.g., linkedin, indeed)"),
    user: User = Depends(get_current_user)
):
    """Check if a saved browser session exists for a platform."""
    return {"platform": platform, "session_saved": session_exists(user.id, platform)}


@app.post("/sessions/{platform}/record", response_model=SessionResponse, tags=["Sessions"])
def record_platform_session(
    platform: str = Path(..., description="The platform to record a session for"),
    user: User = Depends(get_current_user)
):
    """
    Opens a visible browser window so the user can log in manually.
    """
    if session_exists(user.id, platform):
        return {
            "status": "already_exists",
            "platform": platform,
            "message": "Session already saved. DELETE it first if you want to re-record.",
        }

    import threading, queue
    result_queue = queue.Queue()

    def _run():
        result_queue.put(record_session(user.id, platform))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join()

    return result_queue.get()


@app.delete("/sessions/{platform}", response_model=SessionResponse, tags=["Sessions"])
def delete_platform_session(
    platform: str = Path(..., description="The platform to remove session for"),
    user: User = Depends(get_current_user)
):
    """Delete a saved session."""
    deleted = delete_session(user.id, platform)
    return {"status": "deleted" if deleted else "not_found", "platform": platform}


# ── Secrets Endpoints ─────────────────────────────────────────────────────────

@app.get("/secrets", response_model=List[str], tags=["Secrets"])
def list_secrets(user: User = Depends(get_current_user)):
    """List the keys of all saved secrets for the current user."""
    from app.db import list_user_secrets
    return list_user_secrets(user.id)


@app.post("/secrets", tags=["Secrets"])
def save_secret(
    payload: SecretPayload,
    user: User = Depends(get_current_user)
):
    """Encrypt and save a user secret (e.g., 'gemini_api_key', 'linkedin_password')."""
    from app.db import save_user_secret
    save_user_secret(user.id, payload.secret_type, payload.value)
    return {"status": "saved", "secret_type": payload.secret_type}

# ── Resumes Endpoints ─────────────────────────────────────────────────────────

def extract_text_from_bytes(filename: str, file_bytes: bytes) -> str:
    """Extract plain text from PDF, DOCX, TXT, or Markdown bytes."""
    import io
    ext = filename.split(".")[-1].lower()
    
    if ext in ("md", "txt"):
        return file_bytes.decode("utf-8", errors="ignore")
        
    elif ext == "pdf":
        from pypdf import PdfReader
        pdf_file = io.BytesIO(file_bytes)
        reader = PdfReader(pdf_file)
        text = []
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text.append(t)
        return "\n".join(text)
        
    elif ext == "docx":
        import docx2txt
        docx_file = io.BytesIO(file_bytes)
        text = docx2txt.process(docx_file)
        return text
        
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


@app.get("/resumes", response_model=List[str], tags=["Resumes"])
def list_resumes(user: User = Depends(get_current_user)):
    """List all resumes in the user's local session folder."""
    from pathlib import Path
    resumes_dir = Path("data") / "sessions" / user.id
    if not resumes_dir.exists():
        return []
    try:
        return [f.name for f in resumes_dir.glob("*.md")]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/resumes", tags=["Resumes"])
async def upload_resume(
    file: UploadFile = File(...),
    user: User = Depends(get_current_user)
):
    """Upload or overwrite a resume. PDF/Word files will be automatically parsed to markdown and saved locally."""
    filename = file.filename
    ext = filename.split(".")[-1].lower()
    if ext not in ("pdf", "docx", "txt", "md"):
        raise HTTPException(
            status_code=400, 
            detail="Only PDF, DOCX, TXT, and MD resumes are allowed."
        )
    
    file_bytes = await file.read()
    try:
        text_content = extract_text_from_bytes(filename, file_bytes)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to parse resume file: {str(e)}"
        )
        
    if not text_content.strip():
        raise HTTPException(
            status_code=400,
            detail="The uploaded resume appeared to be empty or unparseable."
        )
        
    from pathlib import Path
    resumes_dir = Path("data") / "sessions" / user.id
    resumes_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        path = resumes_dir / "base_resume.md"
        path.write_text(text_content, encoding="utf-8")
        return {"status": "uploaded", "filename": filename, "parsed_to": "base_resume.md"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── System Endpoints ──────────────────────────────────────────────────────────

@app.post("/migration/start", tags=["System"])
def start_migration(user: User = Depends(get_current_user)):
    """Dummy endpoint (migration to Supabase not needed for local offline run)."""
    return {"status": "migration_skipped", "user_id": user.id}


if __name__ == "__main__":
    from app.logger import get_logger
    _logger = get_logger("app.api")
    _logger.info("Starting API server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
