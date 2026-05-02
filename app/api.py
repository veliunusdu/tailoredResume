from fastapi import FastAPI, BackgroundTasks, HTTPException, Path, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List
from app.db import get_all_scored_jobs, get_apply_status, queue_apply
from app.browser import apply_to_job
from app.sessions import record_session, session_exists, delete_session
from app.schemas import Job, Stats, ApplyResponse, ApplyStatus, SessionResponse
import uvicorn
import threading

app = FastAPI(
    title="TailoredResume API",
    description="Backend API for the autonomous career intelligence command center.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/jobs", response_model=List[Job], tags=["Jobs"])
def get_jobs():
    """Fetch all scored jobs from SQLite, sorted by score descending."""
    return get_all_scored_jobs()

@app.get("/stats", response_model=Stats, tags=["Jobs"])
def get_stats():
    """Fetch pipeline statistics including totals and average match scores."""
    jobs = get_all_scored_jobs()
    strong = [j for j in jobs if j.get("score", 0) >= 7]
    maybe = [j for j in jobs if 4 <= j.get("score", 0) < 7]
    
    return {
        "total": len(jobs),
        "strong": len(strong),
        "maybe": len(maybe),
        "avg_score": round(sum(j.get("score", 0) for j in jobs) / max(len(jobs), 1), 1) if jobs else 0
    }

@app.post("/jobs/{job_id}/apply", response_model=ApplyResponse, tags=["Application"])
def start_apply(
    job_id: str = Path(..., description="The unique ID of the job to apply for"), 
    dry_run: bool = Query(True, description="If true, simulates the application without submitting")
):
    """Start the auto-apply process for a job in a background thread."""
    jobs = get_all_scored_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Use threading instead of BackgroundTasks to avoid Playwright/FastAPI loop conflicts
    attempt_id = queue_apply(job_id, job["url"])
    
    thread = threading.Thread(
        target=apply_to_job,
        args=(job["url"],),
        kwargs={"dry_run": dry_run, "attempt_id": attempt_id},
        daemon=True
    )
    thread.start()
    
    return {"status": "queued", "job_id": job_id, "attempt_id": attempt_id}

@app.get("/jobs/{job_id}/apply-status", response_model=ApplyStatus, tags=["Application"])
def get_job_apply_status(job_id: str = Path(..., description="The unique ID of the job")):
    """Check the current status of an application attempt for a specific job."""
    return get_apply_status(job_id)

@app.post("/sessions/{platform}/record", response_model=SessionResponse, tags=["Sessions"])
def record_platform_session(platform: str = Path(..., description="The platform to record a session for (e.g., linkedin, lever)")):
    """
    Opens a visible browser window so the user can log in manually to save session cookies.
    """
    if session_exists(platform):
        return {
            "status": "already_exists",
            "platform": platform,
            "message": "Session already saved. DELETE it first if you want to re-record.",
        }

    import threading, queue
    result_queue = queue.Queue()

    def _run():
        result_queue.put(record_session(platform))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    thread.join()

    return result_queue.get()

@app.delete("/sessions/{platform}", response_model=SessionResponse, tags=["Sessions"])
def remove_session(platform: str = Path(..., description="The platform to remove the session for")):
    """Delete a saved session for a specific platform."""
    if delete_session(platform):
        return {"status": "deleted", "platform": platform}
    raise HTTPException(status_code=404, detail=f"Session for {platform} not found")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
