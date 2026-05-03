import threading
from fastapi import FastAPI, BackgroundTasks, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from app.db import (
    get_all_scored_jobs,
    get_job_by_id,
    queue_apply,
    update_apply_status,
    get_apply_attempts,
    get_all_apply_attempts,
    get_apply_attempt,
)
from app.tailor import prepare_application, get_base_resume
from app.browser import apply_to_job
from app.tasks import prepare_application_task, apply_to_job_task
from app.llm import analyze_job_keywords, generate_interview_questions
from app.celery_app import app as celery_app
from app.sessions import record_session, session_exists, delete_session
from app.schemas import Job, Stats, ApplyResponse, ApplyStatus, SessionResponse
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
def get_jobs():
    """Fetch all scored jobs from SQLite, sorted by score descending."""
    return get_all_scored_jobs()


@app.get("/stats", response_model=Stats, tags=["Jobs"])
def get_stats():
    """Fetch pipeline statistics including totals and average match scores."""
    jobs = get_all_scored_jobs()
    strong = [j for j in jobs if j.get("score", 0) >= 7]
    maybe  = [j for j in jobs if 4 <= j.get("score", 0) < 7]
    return {
        "total":     len(jobs),
        "strong":    len(strong),
        "maybe":     len(maybe),
        "avg_score": round(sum(j.get("score", 0) for j in jobs) / max(len(jobs), 1), 1) if jobs else 0,
    }


# ── Tailor Endpoint ───────────────────────────────────────────────────────────

@app.post("/jobs/{job_id}/tailor", tags=["Tailoring"])
async def tailor_job(
    job_id: str = Path(..., description="The unique ID of the job")
):
    """Trigger AI resume + cover letter tailoring for a job (runs via Celery)."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    task = prepare_application_task.delay(job_id)
    return {"status": "tailoring_queued", "task_id": task.id}


@app.get("/jobs/{job_id}/keywords", tags=["Tailoring"])
async def get_job_keywords(
    job_id: str = Path(..., description="The unique ID of the job")
):
    """Analyze keywords for a job against the base resume (on-the-fly)."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    base_resume = get_base_resume()
    if not base_resume:
        raise HTTPException(status_code=400, detail="Base resume not found. Please upload one first.")
    
    desc = job.get("description", "")
    if not desc:
        raise HTTPException(status_code=400, detail="Job has no description to analyze.")
        
    analysis = analyze_job_keywords(desc, base_resume)
    return analysis


@app.get("/jobs/{job_id}/interview-questions", tags=["Tailoring"])
async def get_job_interview_questions(
    job_id: str = Path(..., description="The unique ID of the job")
):
    """Generate tailored interview questions for a job against the base resume (on-the-fly)."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    base_resume = get_base_resume()
    if not base_resume:
        raise HTTPException(status_code=400, detail="Base resume not found. Please upload one first.")
    
    desc = job.get("description", "")
    if not desc:
        raise HTTPException(status_code=400, detail="Job has no description to analyze.")
        
    questions = generate_interview_questions(desc, base_resume)
    return questions


# ── Apply Endpoints ───────────────────────────────────────────────────────────

@app.post("/jobs/{job_id}/apply", response_model=ApplyResponse, tags=["Application"])
async def apply_job(
    job_id: str = Path(..., description="The unique ID of the job"), 
    dry_run: bool = Query(True, description="If true, fills the form but does NOT click submit")
):
    """
    Queue and trigger an autonomous job application via Celery.
    dry_run=true (default): fills the form but does NOT click submit.
    dry_run=false: will actually submit — use with caution!
    """
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create a queued attempt record in SQLite
    attempt_id = queue_apply(job_id, dry_run=dry_run)

    # Offload to Celery worker
    task = apply_to_job_task.delay(job_id, attempt_id, dry_run)

    return {"status": "queued", "job_id": job_id, "attempt_id": attempt_id, "task_id": task.id}


@app.get("/tasks/{task_id}", tags=["Tasks"])
def get_task_status(task_id: str):
    """Check the status of a Celery task."""
    res = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "status": res.status,
        "result": res.result if res.ready() else None
    }


@app.get("/jobs/{job_id}/apply-status", response_model=List[ApplyStatus], tags=["Application"])
def get_apply_status_endpoint(job_id: str = Path(..., description="The unique ID of the job")):
    """Get all apply attempts for a specific job."""
    return get_apply_attempts(job_id)


@app.get("/apply-queue", response_model=List[ApplyStatus], tags=["Application"])
def get_apply_queue():
    """Get all apply attempts across all jobs (last 100)."""
    return get_all_apply_attempts()


# ── Session Endpoints ─────────────────────────────────────────────────────────

@app.get("/sessions/{platform}/status", tags=["Sessions"])
def get_session_status(platform: str = Path(..., description="The platform (e.g., linkedin, indeed)")):
    """Check if a saved browser session exists for a platform."""
    return {"platform": platform, "session_saved": session_exists(platform)}


@app.post("/sessions/{platform}/record", response_model=SessionResponse, tags=["Sessions"])
def record_platform_session(platform: str = Path(..., description="The platform to record a session for")):
    """
    Opens a visible browser window so the user can log in manually.
    Session (cookies) saves automatically when the browser is closed.

    Supported platforms: linkedin, workday, indeed, glassdoor

    IMPORTANT: This is a blocking call — it returns only after the browser is closed.
    Run it from a separate terminal, not from the dashboard.
    """
    if session_exists(platform):
        return {
            "status": "already_exists",
            "platform": platform,
            "message": "Session already saved. DELETE it first if you want to re-record.",
        }

    # Run in a real OS thread — Playwright sync API conflicts with asyncio event loop
    import threading, queue
    result_queue = queue.Queue()

    def _run():
        result_queue.put(record_session(platform))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join()  # Wait for browser to be closed before returning

    return result_queue.get()


@app.delete("/sessions/{platform}", response_model=SessionResponse, tags=["Sessions"])
def delete_platform_session(platform: str = Path(..., description="The platform to remove session for")):
    """Delete a saved session (e.g. when it has expired)."""
    deleted = delete_session(platform)
    return {"status": "deleted" if deleted else "not_found", "platform": platform}


if __name__ == "__main__":
    from app.logger import get_logger
    _logger = get_logger("app.api")
    _logger.info("Starting API server on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
