"""
agent.py — orchestration only.

This module contains zero business logic.
It imports and calls other modules in the right order.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.jobs    import fetch_jobs
from app.filters import filter_jobs
from app.llm     import score_job, score_jobs_batch
from app.config  import SCORE_STRONG, SCORE_MAYBE, LLM_BATCH_SIZE, LLM_MAX_CONCURRENT_BATCHES
from app.db      import build_llm_cache_key, get_cached_llm_score, set_cached_llm_score
from app.logger  import get_logger

_logger = get_logger(__name__)

VERDICT_ICON = {"yes": "✅", "maybe": "🤔", "no": "❌"}


def _print_job(job: dict) -> None:
    icon = VERDICT_ICON.get(job.get("verdict", "no"), "❓")
    print(f"{icon}  [{job['score']}/10] {job['title']} @ {job['company']}")
    print(f"     Location : {job['location']}")
    print(f"     Salary   : {job['salary']}")
    print(f"     Reason   : {job['reason']}")
    print(f"     URL      : {job['url']}")
    print()


def get_jobs() -> tuple[list[dict], list[dict]]:
    _logger.info("Agent run started")

    # 1 — Fetch
    raw_jobs = fetch_jobs()

    # 2 — Rule-based filter + normalize
    filtered = filter_jobs(raw_jobs)
    _logger.info("Fetched %s raw jobs, rule-filtered to %s", len(raw_jobs), len(filtered))

    # 3 — LLM scoring
    strong, maybe = [], []
    uncached_jobs = []
    
    cache_hits = 0
    for job in filtered:
        cache_key = build_llm_cache_key(job)
        cached_result = get_cached_llm_score(cache_key)
        if cached_result is not None:
            job.update(cached_result)
            if job["score"] >= SCORE_STRONG:
                strong.append(job)
            elif job["score"] >= SCORE_MAYBE:
                maybe.append(job)
            cache_hits += 1
        else:
            uncached_jobs.append(job)

    _logger.info("Found %s uncached jobs to score (%s cache hits)", len(uncached_jobs), cache_hits)

    if uncached_jobs:
        batches = [
            uncached_jobs[i : i + LLM_BATCH_SIZE]
            for i in range(0, len(uncached_jobs), LLM_BATCH_SIZE)
        ]
        
        _logger.info("Processing %s batches of up to %s jobs each.", len(batches), LLM_BATCH_SIZE)
        
        def process_batch(batch):
            results = score_jobs_batch(batch)
            for job, result in zip(batch, results):
                job.update(result)
                cache_key = build_llm_cache_key(job)
                set_cached_llm_score(cache_key, result)
            return batch

        with ThreadPoolExecutor(max_workers=LLM_MAX_CONCURRENT_BATCHES) as executor:
            future_to_batch = {executor.submit(process_batch, batch): batch for batch in batches}
            for future in as_completed(future_to_batch):
                try:
                    completed_batch = future.result()
                    for job in completed_batch:
                        if job.get("score", 0) >= SCORE_STRONG:
                            strong.append(job)
                        elif job.get("score", 0) >= SCORE_MAYBE:
                            maybe.append(job)
                except Exception as exc:
                    _logger.error("Batch processing failed: %s", exc)

    # Sort by score descending
    strong.sort(key=lambda x: x.get("score", 0), reverse=True)
    maybe.sort(key=lambda x: x.get("score", 0), reverse=True)

    _logger.info(
        "Agent run completed: raw=%s filtered=%s strong=%s maybe=%s",
        len(raw_jobs),
        len(filtered),
        len(strong),
        len(maybe),
    )
    return strong, maybe


def run() -> None:
    _logger.info("Agent CLI run started")
    
    strong, maybe = get_jobs()
    
    # 4 — Output
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
