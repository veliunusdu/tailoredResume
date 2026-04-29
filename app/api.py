from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from app.db import get_all_scored_jobs, get_apply_status, queue_apply
from app.browser import apply_to_job
from app.sessions import record_session, session_exists, delete_session
import uvicorn
import threading

app = FastAPI(title="TailoredResume API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/jobs")
def get_jobs():
    """Fetch all scored jobs from SQLite."""
    return get_all_scored_jobs()

@app.get("/stats")
def get_stats():
    """Fetch pipeline statistics."""
    jobs = get_all_scored_jobs()
    strong = [j for j in jobs if j.get("score", 0) >= 7]
    maybe = [j for j in jobs if 4 <= j.get("score", 0) < 7]
    
    return {
        "total": len(jobs),
        "strong": len(strong),
        "maybe": len(maybe),
        "avg_score": round(sum(j.get("score", 0) for j in jobs) / max(len(jobs), 1), 1) if jobs else 0
    }

@app.post("/jobs/{job_id}/apply")
def start_apply(job_id: str, dry_run: bool = True):
    """Start the auto-apply process for a job in a background thread."""
    jobs = get_all_scored_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    
    if not job:
        return {"status": "error", "message": "Job not found"}

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

@app.get("/jobs/{job_id}/apply-status")
def get_job_apply_status(job_id: str):
    """Check the status of an application attempt."""
    return get_apply_status(job_id)

@app.post("/sessions/{platform}/record")
def record_platform_session(platform: str):
    """
    Opens a visible browser window so the user can log in manually.
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

@app.delete("/sessions/{platform}")
def remove_session(platform: str):
    """Delete a saved session."""
    if delete_session(platform):
        return {"status": "deleted", "platform": platform}
    return {"status": "error", "message": "Session not found"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
