from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db import get_all_scored_jobs
import uvicorn

app = FastAPI(title="TailoredResume API")

# Allow requests from our Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
