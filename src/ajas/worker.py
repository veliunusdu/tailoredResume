import os

from celery import Celery

from ajas.cli import generate_cl_pipeline, generate_cv_pipeline
from ajas.logger import log, set_trace_id

# Redis URL from environment or default
REDIS_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")

app = Celery("ajas", broker=REDIS_URL, backend=REDIS_URL)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@app.task(bind=True, name="generate_cv_task")
def generate_cv_task(self, job_path: str, master_path: str, trace_id: str):
    """Background task to generate a CV."""
    set_trace_id(trace_id)
    log.info("celery_task_started", task="generate_cv", job_path=job_path)
    try:
        generate_cv_pipeline(job_path, master_path)
        log.info("celery_task_completed", task="generate_cv")
        return {"status": "success", "task": "generate_cv", "job_path": job_path}
    except Exception as e:
        log.error("celery_task_failed", task="generate_cv", error=str(e))
        raise


@app.task(bind=True, name="generate_cl_task")
def generate_cl_task(self, job_path: str, master_path: str, trace_id: str):
    """Background task to generate a Cover Letter."""
    set_trace_id(trace_id)
    log.info("celery_task_started", task="generate_cl", job_path=job_path)
    try:
        generate_cl_pipeline(job_path, master_path)
        log.info("celery_task_completed", task="generate_cl")
        return {"status": "success", "task": "generate_cl", "job_path": job_path}
    except Exception as e:
        log.error("celery_task_failed", task="generate_cl", error=str(e))
        raise
