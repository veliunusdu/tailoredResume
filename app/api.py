import threading
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.db import (
    get_all_scored_jobs,
    get_job_by_id,
    queue_apply,
    update_apply_status,
    get_apply_attempts,
    get_all_apply_attempts,
    get_apply_attempt,
)
from app.tailor import prepare_application
from app.browser import apply_to_job
from app.sessions import record_session, session_exists, delete_session
import uvicorn

app = FastAPI(title="TailoredResume API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Job Endpoints ─────────────────────────────────────────────────────────────

@app.get("/jobs")
def get_jobs():
    """Fetch all scored jobs from SQLite."""
    return get_all_scored_jobs()


@app.get("/stats")
def get_stats():
    """Fetch pipeline statistics."""
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

@app.post("/jobs/{job_id}/tailor")
async def tailor_job(job_id: str, background_tasks: BackgroundTasks):
    """Trigger AI resume + cover letter tailoring for a job (runs in background)."""
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    background_tasks.add_task(prepare_application, job)
    return {"status": "tailoring_started"}


# ── Apply Endpoints ───────────────────────────────────────────────────────────

def _run_apply_background(job: dict, attempt_id: str, dry_run: bool):
    """Wrapper to run apply_to_job in a real thread (Playwright needs it)."""
    apply_to_job(job, dry_run=dry_run, attempt_id=attempt_id)


@app.post("/jobs/{job_id}/apply")
async def apply_job(job_id: str, dry_run: bool = True):
    """
    Queue and trigger an autonomous job application.
    dry_run=true (default): fills the form but does NOT click submit.
    dry_run=false: will actually submit — use with caution!
    """
    job = get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Create a queued attempt record
    attempt_id = queue_apply(job_id, dry_run=dry_run)

    # Run in a real OS thread — Playwright requires a non-async context
    thread = threading.Thread(
        target=_run_apply_background,
        args=(job, attempt_id, dry_run),
        daemon=True,
    )
    thread.start()

    return {"status": "queued", "attempt_id": attempt_id, "dry_run": dry_run}


@app.get("/jobs/{job_id}/apply-status")
def get_apply_status(job_id: str):
    """Get all apply attempts for a specific job."""
    return get_apply_attempts(job_id)


@app.get("/apply-queue")
def get_apply_queue():
    """Get all apply attempts across all jobs (last 100)."""
    return get_all_apply_attempts()


# ── Session Endpoints ─────────────────────────────────────────────────────────

@app.get("/sessions/{platform}/status")
def get_session_status(platform: str):
    """Check if a saved browser session exists for a platform."""
    return {"platform": platform, "session_saved": session_exists(platform)}


@app.post("/sessions/{platform}/record")
def record_platform_session(platform: str):
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


@app.delete("/sessions/{platform}")
def delete_platform_session(platform: str):
    """Delete a saved session (e.g. when it has expired)."""
    deleted = delete_session(platform)
    return {"status": "deleted" if deleted else "not_found", "platform": platform}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
