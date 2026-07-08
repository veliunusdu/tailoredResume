from app.celery_app import app as celery_app
from app.logger import get_logger
from app.db import get_job_by_id, save_job_description, save_score
from app.enrich import enrich_description
from app.llm import score_jobs_batch
from app.tailor import prepare_application
from app.browser import apply_to_job

_logger = get_logger(__name__)

@celery_app.task(bind=True, name="app.tasks.sync_jobs_task")
def sync_jobs_task(self, user_id: str):
    """Run the job discovery and scoring agent pipeline for a single user."""
    from app.agent import get_jobs
    from app.db import update_task_progress
    _logger.info(f"Running job sync pipeline for user {user_id}")
    task_id = self.request.id
    try:
        update_task_progress(task_id, user_id, "running", "Job sync started. Fetching new job listings...", 10)
        strong, maybe = get_jobs(user_id, task_id=task_id)
        update_task_progress(task_id, user_id, "success", f"Sync completed! Found {len(strong)} perfect matches.", 100)
        return {"strong": len(strong), "maybe": len(maybe)}
    except Exception as e:
        _logger.error(f"Error syncing jobs for {user_id}: {e}", exc_info=True)
        update_task_progress(task_id, user_id, "failed", f"Failed: {str(e)}", 0)
        return {"error": str(e)}


@celery_app.task(name="app.tasks.enrich_job_task")
def enrich_job_task(job_id: str, user_id: str):
    """Scrape and enrich job description."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        _logger.error(f"Job {job_id} not found for enrichment (user={user_id})")
        return False

    url = job.get("url")
    if not url:
        _logger.error(f"Job {job_id} has no URL")
        return False

    _logger.info(f"Enriching job {job_id} from {url}")
    new_desc = enrich_description(url)
    if new_desc:
        save_job_description(job_id, new_desc, user_id=user_id)
        return True
    return False


@celery_app.task(name="app.tasks.score_jobs_task")
def score_jobs_task(job_ids: list, user_id: str):
    """Score a batch of jobs."""
    jobs = []
    for jid in job_ids:
        job = get_job_by_id(jid, user_id=user_id)
        if job:
            jobs.append(job)

    if not jobs:
        return []

    _logger.info(f"Scoring batch of {len(jobs)} jobs (user={user_id})")
    results = score_jobs_batch(jobs)
    for job, result in zip(jobs, results):
        save_score(job["id"], result, user_id=user_id)
    return results


@celery_app.task(bind=True, name="app.tasks.prepare_application_task")
def prepare_application_task(self, job_id: str, user_id: str):
    """Generate tailored resume and cover letter."""
    from app.db import update_task_progress
    job = get_job_by_id(job_id, user_id=user_id)
    task_id = self.request.id
    if not job:
        _logger.error(f"Job {job_id} not found for tailoring (user={user_id})")
        update_task_progress(task_id, user_id, "failed", "Job not found", 0)
        return False

    _logger.info(f"Preparing application for job {job_id} (user={user_id})")
    try:
        update_task_progress(task_id, user_id, "running", "Analyzing job description...", 20)
        result = prepare_application(job, user_id=user_id, task_id=task_id)
        if result and result.get("tailored_resume"):
            from app.db import save_tailored_materials
            save_tailored_materials(job_id, user_id, result["tailored_resume"], result.get("cover_letter"))
        update_task_progress(task_id, user_id, "success", "Resume & cover letter tailored successfully!", 100)
        return result
    except Exception as e:
        _logger.error(f"Error preparing application for job {job_id}: {e}", exc_info=True)
        update_task_progress(task_id, user_id, "failed", f"Failed: {str(e)}", 0)
        return False


@celery_app.task(name="app.tasks.apply_to_job_task")
def apply_to_job_task(job_id: str, attempt_id: str, dry_run: bool, user_id: str):
    """Execute autonomous application using Playwright."""
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        _logger.error(f"Job {job_id} not found for application (user={user_id})")
        return False

    _logger.info(f"Applying to job {job_id} (Attempt: {attempt_id}, Dry Run: {dry_run}, user={user_id})")
    apply_to_job(user_id, job, dry_run=dry_run, attempt_id=attempt_id)
    return True

