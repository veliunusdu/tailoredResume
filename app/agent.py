"""
agent.py — orchestration only.

This module contains zero business logic.
It imports and calls other modules in the right order.
"""
from celery import group
from tqdm import tqdm

from app.jobs    import fetch_jobs
from app.filters import filter_jobs
from app.tasks   import enrich_job_task, score_jobs_task
from app.config  import SCORE_STRONG, SCORE_MAYBE, LLM_BATCH_SIZE
from app.db      import (
    save_jobs, 
    get_unscored_jobs, 
    save_score, 
    get_all_scored_jobs, 
    should_fetch_jobs,
    save_job_description
)
from app.logger  import get_logger
from app.tailor  import prepare_application

_logger = get_logger(__name__)

VERDICT_ICON = {"yes": "✅", "maybe": "🤔", "no": "❌"}


def _print_job(job: dict) -> None:
    icon = VERDICT_ICON.get(job.get("verdict", "no"), "❓")
    print(f"{icon}  [{job.get('score', 0)}/10] {job.get('title')} @ {job.get('company')}")
    print(f"     Location : {job.get('location')}")
    print(f"     Salary   : {job.get('salary')}")
    print(f"     Reason   : {job.get('reason')}")
    print(f"     URL      : {job.get('url')}")
    print()


def get_jobs(user_id: str, task_id: str | None = None) -> tuple[list[dict], list[dict]]:
    from app.db import update_task_progress
    _logger.info("Agent run started for user %s", user_id)

    # 1 & 2 — Fetch & Filter (Only if cache is stale)
    if should_fetch_jobs(user_id):
        if task_id:
            update_task_progress(task_id, user_id, "running", "Fetching raw job listings from configured boards...", 20)
        raw_jobs = fetch_jobs(user_id)
        
        if task_id:
            update_task_progress(task_id, user_id, "running", "Filtering jobs against your exclusion rules...", 40)
        filtered = filter_jobs(raw_jobs, user_id)
        _logger.info("Fetched %s raw jobs, rule-filtered to %s", len(raw_jobs), len(filtered))
        
        inserted = save_jobs(filtered, user_id=user_id)
        _logger.info("Inserted %s new jobs into the database.", inserted)
    else:
        _logger.info("Recent fetch detected. Using jobs from the database.")

    # 3 — Deep Enrichment & LLM scoring
    uncached_jobs = get_unscored_jobs(user_id)
    _logger.info("Found %s unscored jobs in the database.", len(uncached_jobs))

    if uncached_jobs:
        if task_id:
            update_task_progress(task_id, user_id, "running", "Enriching job descriptions with web scrapers...", 60)
        _logger.info("Enriching descriptions for unscored jobs...")
        
        with tqdm(total=len(uncached_jobs), desc="Enriching Jobs", unit="job") as pbar:
            for job in uncached_jobs:
                try:
                    enrich_job_task(job["id"], user_id)
                except Exception as e:
                    _logger.error(f"Failed to enrich job %s: %s", job["id"], e)
                pbar.update(1)

        if task_id:
            update_task_progress(task_id, user_id, "running", "AI evaluation: Scoring compatibility with Gemini...", 80)

        batches = [
            uncached_jobs[i : i + LLM_BATCH_SIZE]
            for i in range(0, len(uncached_jobs), LLM_BATCH_SIZE)
        ]
        
        _logger.info("Processing %s batches...", len(batches))
        
        with tqdm(total=len(batches), desc="Scoring Batches", unit="batch") as pbar:
            for batch in batches:
                try:
                    score_jobs_task([j["id"] for j in batch], user_id)
                except Exception as e:
                    _logger.error(f"Failed to score batch: %s", e)
                pbar.update(1)

    # 4 - Retrieve and sort by score descending
    if task_id:
        update_task_progress(task_id, user_id, "running", "Retrieving and sorting job matches...", 95)
    all_scored = get_all_scored_jobs(user_id)
    strong = [j for j in all_scored if j.get("score", 0) >= SCORE_STRONG]
    maybe = [j for j in all_scored if SCORE_MAYBE <= j.get("score", 0) < SCORE_STRONG]

    _logger.info(
        "Agent run completed: strong=%s maybe=%s",
        len(strong),
        len(maybe),
    )
    return strong, maybe


def run(user_id: str) -> None:
    _logger.info("Agent CLI run started for user %s", user_id)
    
    strong, maybe = get_jobs(user_id)
    
    # Output Results
    print(f"{'='*55}")
    print(f"  ✅ STRONG MATCHES ({len(strong)})")
    print(f"{'='*55}")
    for job in strong:
        _print_job(job)

    print(f"{'='*55}")
    print(f"  🤔 MAYBE ({len(maybe)})")
    print(f"{'='*55}")
    for job in maybe:
        _print_job(job)
