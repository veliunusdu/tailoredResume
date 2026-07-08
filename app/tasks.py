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

@celery_app.task(name="app.tasks.bulk_ingest_jobs_task")
def bulk_ingest_jobs_task():
    """Periodic task to bulk ingest jobs for all users."""
    from app.db import get_connection
    _logger.info("Starting bulk job ingestion for all users...")
    
    # We fetch all unique users who have a search config
    try:
        with get_connection("system") as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT DISTINCT user_id FROM user_search_config")
                users = cur.fetchall()
        
        for row in users:
            user_id = row[0]
            _logger.info(f"Queueing sync_jobs_task for user: {user_id}")
            sync_jobs_task.delay(user_id)
            
        return {"status": "success", "users_queued": len(users)}
    except Exception as e:
        _logger.error(f"Failed to queue bulk ingestion: {e}")
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
        # Trigger enrichment background task
        enrich_pipeline_task.delay(job["id"], user_id)
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
            save_tailored_materials(
                job_id, 
                user_id, 
                result["tailored_resume"], 
                result.get("cover_letter"),
                result.get("interview_questions")
            )
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

@celery_app.task(name="app.tasks.process_raw_ingest")
def process_raw_ingest(title: str, company: str, raw_content: str, source: str, user_id: str):
    """Process raw scraped/ingested content in the background."""
    from app.enrich import clean_html_tags
    from app.db import save_jobs
    
    cleaned_description = clean_html_tags(raw_content)
    
    normalized_job = {
        "title": title,
        "company": company,
        "description": cleaned_description,
        "site": source
    }
    
    # Save the job listing scoped to the user
    from app.db import build_job_id
    save_jobs([normalized_job], user_id=user_id)
    job_id = build_job_id(normalized_job)
    
    # Trigger enrichment background task
    enrich_pipeline_task.delay(job_id, user_id)
    return True

@celery_app.task(name="app.tasks.enrich_pipeline_task")
def enrich_pipeline_task(job_id: str, user_id: str):
    """
    Orchestrate the AI skill extraction, skill gap analysis, and generic salary fetching stub.
    """
    from app.db import get_job_by_id, save_skill_analysis
    from app.llm import extract_job_skills
    from app.tailor import analyze_skill_gap, get_best_base_resume
    
    job = get_job_by_id(job_id, user_id=user_id)
    if not job:
        _logger.error(f"Job {job_id} not found for enrichment (user={user_id})")
        return False
        
    desc = job.get("description")
    if not desc:
        _logger.warning(f"Job {job_id} has no description for skill extraction.")
        return False

    _logger.info(f"Extracting AI skills for job {job_id}...")
    required_skills = extract_job_skills(desc)
    
    _logger.info(f"Analyzing skill gap for job {job_id}...")
    _, base_resume = get_best_base_resume(desc, user_id=user_id)
    
    if base_resume:
        gap_analysis = analyze_skill_gap(required_skills, base_resume)
    else:
        gap_analysis = {"match_score": 0, "missing_skills": required_skills}
        
    _logger.info(f"Saving skill analysis for job {job_id}: score={gap_analysis.get('match_score')}")
    save_skill_analysis(
        job_id, 
        user_id, 
        required_skills, 
        gap_analysis.get("missing_skills", []), 
        gap_analysis.get("match_score", 0)
    )
    
    # Generic stub for salary context
    # Note: Target-specific unofficial scrapers (like OpenWeb Ninja targeting Glassdoor)
    # are disabled per policy. To implement salary context, use an official API like
    # the BLS API or an authorized commercial partner.
    _logger.info(f"Salary context stub for {job.get('title')} at {job.get('location')}...")
    
    return True

