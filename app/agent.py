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
from app.browser import run_autonomous_applications

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


def get_jobs() -> tuple[list[dict], list[dict]]:
    _logger.info("Agent run started")

    # 1 & 2 — Fetch & Filter (Only if cache is stale)
    if should_fetch_jobs():
        raw_jobs = fetch_jobs()
        filtered = filter_jobs(raw_jobs)
        _logger.info("Fetched %s raw jobs, rule-filtered to %s", len(raw_jobs), len(filtered))
        
        inserted = save_jobs(filtered)
        _logger.info("Inserted %s new jobs into the database.", inserted)
    else:
        _logger.info("Recent fetch detected. Using jobs from the database.")

    # 3 — Deep Enrichment & LLM scoring
    uncached_jobs = get_unscored_jobs()
    _logger.info("Found %s unscored jobs in the database.", len(uncached_jobs))

    if uncached_jobs:
        _logger.info("Enriching descriptions for unscored jobs via Celery...")
        
        enrich_job_group = group(enrich_job_task.s(job["id"]) for job in uncached_jobs)
        enrich_result = enrich_job_group.apply_async()
        
        with tqdm(total=len(uncached_jobs), desc="Enriching Jobs", unit="job") as pbar:
            while not enrich_result.ready():
                import time
                time.sleep(0.5)
                # Note: completed_count calculation can be complex with groups, 
                # but for CLI we'll just wait or poll.
            pbar.update(len(uncached_jobs))

        batches = [
            uncached_jobs[i : i + LLM_BATCH_SIZE]
            for i in range(0, len(uncached_jobs), LLM_BATCH_SIZE)
        ]
        
        _logger.info("Processing %s batches via Celery workers...", len(batches))
        
        score_job_group = group(score_jobs_task.s([j["id"] for j in batch]) for batch in batches)
        score_result = score_job_group.apply_async()

        with tqdm(total=len(batches), desc="Scoring Batches", unit="batch") as pbar:
            while not score_result.ready():
                import time
                time.sleep(0.5)
            pbar.update(len(batches))

    # 4 - Retrieve and sort by score descending
    all_scored = get_all_scored_jobs()
    strong = [j for j in all_scored if j.get("score", 0) >= SCORE_STRONG]
    maybe = [j for j in all_scored if SCORE_MAYBE <= j.get("score", 0) < SCORE_STRONG]

    _logger.info(
        "Agent run completed: strong=%s maybe=%s",
        len(strong),
        len(maybe),
    )
    return strong, maybe


def run() -> None:
    _logger.info("Agent CLI run started")
    
    strong, maybe = get_jobs()
    
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
