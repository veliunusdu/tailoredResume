"""
agent.py — orchestration only.

This module contains zero business logic.
It imports and calls other modules in the right order.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from app.jobs    import fetch_jobs
from app.filters import filter_jobs
from app.llm     import score_jobs_batch
from app.enrich  import enrich_description
from app.config  import SCORE_STRONG, SCORE_MAYBE, LLM_BATCH_SIZE, LLM_MAX_CONCURRENT_BATCHES
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
        _logger.info("Enriching descriptions for unscored jobs...")
        
        def enrich_job(job):
            desc = job.get("description", "")
            if not desc or len(desc) < 200:
                url = job.get("url")
                if url:
                    new_desc = enrich_description(url)
                    if new_desc:
                        job["description"] = new_desc
                        save_job_description(job["id"], new_desc)
            return job

        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_job = {executor.submit(enrich_job, job): job for job in uncached_jobs}
            with tqdm(total=len(uncached_jobs), desc="Enriching Jobs", unit="job") as pbar:
                for future in as_completed(future_to_job):
                    try:
                        future.result()
                    except Exception as exc:
                        _logger.error("Job enrichment failed: %s", exc)
                    pbar.update(1)

        batches = [
            uncached_jobs[i : i + LLM_BATCH_SIZE]
            for i in range(0, len(uncached_jobs), LLM_BATCH_SIZE)
        ]
        
        _logger.info("Processing %s batches of up to %s jobs each.", len(batches), LLM_BATCH_SIZE)
        
        def process_batch(batch):
            results = score_jobs_batch(batch)
            for job, result in zip(batch, results):
                job.update(result)
                save_score(job["id"], result)
            return batch

        with ThreadPoolExecutor(max_workers=LLM_MAX_CONCURRENT_BATCHES) as executor:
            future_to_batch = {executor.submit(process_batch, batch): batch for batch in batches}
            with tqdm(total=len(batches), desc="Scoring Batches", unit="batch") as pbar:
                for future in as_completed(future_to_batch):
                    try:
                        future.result()
                    except Exception as exc:
                        _logger.error("Batch processing failed: %s", exc)
                    pbar.update(1)

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
