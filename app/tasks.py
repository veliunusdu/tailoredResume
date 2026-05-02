from app.celery_app import app as celery_app
from app.logger import get_logger
from app.db import get_job_by_id, save_job_description, save_score
from app.enrich import enrich_description
from app.llm import score_jobs_batch
from app.tailor import prepare_application
from app.browser import apply_to_job

_logger = get_logger(__name__)

@celery_app.task(name="app.tasks.enrich_job_task")
def enrich_job_task(job_id: str):
    """Scrape and enrich job description."""
    job = get_job_by_id(job_id)
    if not job:
        _logger.error(f"Job {job_id} not found for enrichment")
        return False
    
    url = job.get("url")
    if not url:
        _logger.error(f"Job {job_id} has no URL")
        return False

    _logger.info(f"Enriching job {job_id} from {url}")
    new_desc = enrich_description(url)
    if new_desc:
        save_job_description(job_id, new_desc)
        return True
    return False

@celery_app.task(name="app.tasks.score_jobs_task")
def score_jobs_task(job_ids: list):
    """Score a batch of jobs."""
    jobs = []
    for jid in job_ids:
        job = get_job_by_id(jid)
        if job:
            jobs.append(job)
    
    if not jobs:
        return []

    _logger.info(f"Scoring batch of {len(jobs)} jobs")
    results = score_jobs_batch(jobs)
    for job, result in zip(jobs, results):
        save_score(job["id"], result)
    return results

@celery_app.task(name="app.tasks.prepare_application_task")
def prepare_application_task(job_id: str):
    """Generate tailored resume and cover letter."""
    job = get_job_by_id(job_id)
    if not job:
        _logger.error(f"Job {job_id} not found for tailoring")
        return False
    
    _logger.info(f"Preparing application for job {job_id}")
    prepare_application(job)
    return True

@celery_app.task(name="app.tasks.apply_to_job_task")
def apply_to_job_task(job_id: str, attempt_id: str, dry_run: bool):
    """Execute autonomous application using Playwright."""
    job = get_job_by_id(job_id)
    if not job:
        _logger.error(f"Job {job_id} not found for application")
        return False
    
    _logger.info(f"Applying to job {job_id} (Attempt: {attempt_id}, Dry Run: {dry_run})")
    apply_to_job(job, dry_run=dry_run, attempt_id=attempt_id)
    return True
