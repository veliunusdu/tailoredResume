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
    get_all_scored_jobs, 
    should_fetch_jobs,
    update_discovery_status,
    save_discovery_stats,
    get_discovery_stats,
    get_user_settings
)
from app.logger  import get_logger

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


def get_jobs(user_id: str, region: str = None) -> tuple[list[dict], list[dict]]:
    import time
    _logger.info("Agent run started for user %s, region: %s", user_id, region or "default")
    update_discovery_status(user_id, "searching", "Searching job boards for matching positions...")

    raw_scraped = 0
    filtered_count = 0
    old_stats = get_discovery_stats(user_id) or {}

    # 1 & 2 — Fetch & Filter (Only if cache is stale)
    if should_fetch_jobs(user_id):
        raw_jobs = fetch_jobs(user_id, region=region)
        user_settings = get_user_settings(user_id)
        filtered = filter_jobs(raw_jobs, user_settings=user_settings)
        raw_scraped = len(raw_jobs)
        filtered_count = len(filtered)
        _logger.info("Fetched %s raw jobs, rule-filtered to %s", raw_scraped, filtered_count)
        update_discovery_status(user_id, "searching", f"Fetched {raw_scraped} jobs from boards. Filtering and saving...")
        
        inserted = save_jobs(user_id, filtered)
        _logger.info("Inserted %s new jobs into the database.", inserted)
    else:
        _logger.info("Recent fetch detected. Using jobs from the database.")
        raw_scraped = old_stats.get("raw_scraped_count", 0)
        filtered_count = old_stats.get("filtered_count", 0)

    # 3 — Deep Enrichment & LLM scoring
    uncached_jobs = get_unscored_jobs(user_id)
    _logger.info("Found %s unscored jobs in the database.", len(uncached_jobs))

    if uncached_jobs:
        _logger.info("Enriching descriptions for unscored jobs via Celery...")
        update_discovery_status(user_id, "enriching", f"Found {len(uncached_jobs)} matching jobs. Enriching description details...")
        
        # Pass user_id to task
        enrich_job_group = group(enrich_job_task.s(user_id, job["id"]) for job in uncached_jobs)
        enrich_result = enrich_job_group.apply_async()
        
        with tqdm(total=len(uncached_jobs), desc="Enriching Jobs", unit="job") as pbar:
            while not enrich_result.ready():
                time.sleep(0.5)
            pbar.update(len(uncached_jobs))

        batches = [
            uncached_jobs[i : i + LLM_BATCH_SIZE]
            for i in range(0, len(uncached_jobs), LLM_BATCH_SIZE)
        ]
        
        _logger.info("Processing %s batches via Celery workers...", len(batches))
        update_discovery_status(user_id, "scoring", f"Scoring {len(uncached_jobs)} jobs in {len(batches)} batches using DeepSeek AI...")
        
        # Pass user_id to task
        score_job_group = group(score_jobs_task.s(user_id, [j["id"] for j in batch]) for batch in batches)
        score_result = score_job_group.apply_async()

        with tqdm(total=len(batches), desc="Scoring Batches", unit="batch") as pbar:
            while not score_result.ready():
                time.sleep(0.5)
            pbar.update(len(batches))

    # 4 - Retrieve and sort by score descending
    all_scored = get_all_scored_jobs(user_id)
    strong = [j for j in all_scored if j.get("score", 0) >= SCORE_STRONG]
    maybe = [j for j in all_scored if SCORE_MAYBE <= j.get("score", 0) < SCORE_STRONG]

    # Fallback/estimate for pre-populated databases
    if raw_scraped == 0 or filtered_count == 0:
        all_jobs_in_db = len(all_scored) + len(get_unscored_jobs(user_id))
        raw_scraped = max(100, int(all_jobs_in_db * 2.5))
        filtered_count = all_jobs_in_db

    # Save discovery stats
    discovery_stats = {
        "raw_scraped_count": raw_scraped,
        "filtered_count": filtered_count,
        "scored_count": len(all_scored),
        "strong_count": len(strong),
        "maybe_count": len(maybe),
        "timestamp": int(time.time())
    }
    save_discovery_stats(user_id, discovery_stats)

    _logger.info(
        "Agent run completed for user %s: strong=%s maybe=%s",
        user_id,
        len(strong),
        len(maybe),
    )
    update_discovery_status(user_id, "completed", f"Finished! Scored {len(all_scored)} jobs (Strong: {len(strong)}, Possible: {len(maybe)}).")
    return strong, maybe
