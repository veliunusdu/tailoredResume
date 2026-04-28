"""
llm.py — all LLM calls live here.

This module knows nothing about jobs specifically.
It takes a prompt string and returns a parsed dict.
"""
import os
import json
from typing import Any
import litellm
from app.config import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_FACTOR,
    RETRY_INITIAL_DELAY_SEC,
    LLM_MIN_INTERVAL_SEC,
    LLM_RATE_LIMIT_COOLDOWN_SEC,
    LLM_MAX_DESC_CHARS,
)
from app.logger import get_logger
from app.utils import retry, RateLimiter

_logger = get_logger(__name__)

# Ensure API key is in environment for litellm
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

_rate_limiter = RateLimiter(LLM_MIN_INTERVAL_SEC)

_SYSTEM_PROMPT_SINGLE = """
You are a job fit evaluator for a university student with the following profile:

- Level: beginner / entry-level, currently learning
- Stack: Python, some experience with Flask and basic ML concepts
- Looking for: internships, junior roles, entry-level positions in backend, data, or AI/ML
- Location: open to fully remote worldwide
- Dealbreakers: requires 3+ years experience, requires degree already completed,
  senior/lead/principal roles, test/sample/fake postings

Evaluate the job and return ONLY valid JSON in this exact schema:
{
  "verdict": "yes" | "maybe" | "no",
  "score": <integer 0-10>,
  "reason": "<one sentence>"
}

Commit to a verdict first. Score 8-10 = strong match, 4-7 = possible, 0-3 = not suitable.
""".strip()

_SYSTEM_PROMPT_BATCH = """
You are a job fit evaluator for a university student with the following profile:

- Level: beginner / entry-level, currently learning
- Stack: Python, some experience with Flask and basic ML concepts
- Looking for: internships, junior roles, entry-level positions in backend, data, or AI/ML
- Location: open to fully remote worldwide
- Dealbreakers: requires 3+ years experience, requires degree already completed,
  senior/lead/principal roles, test/sample/fake postings

Evaluate the list of jobs provided. For each job, return its evaluation.
Return ONLY valid JSON in this exact schema, a JSON array of objects:
[
  {
    "id": "<job_id_from_prompt>",
    "verdict": "yes" | "maybe" | "no",
    "score": <integer 0-10>,
    "reason": "<one sentence>"
  }
]

Commit to a verdict first. Score 8-10 = strong match, 4-7 = possible, 0-3 = not suitable.
""".strip()

@retry(
    max_attempts=RETRY_ATTEMPTS,
    initial_delay_sec=RETRY_INITIAL_DELAY_SEC,
    backoff_factor=RETRY_BACKOFF_FACTOR,
    rate_limit_cooldown_sec=LLM_RATE_LIMIT_COOLDOWN_SEC,
    logger=_logger,
)
def _call_llm_raw(user_prompt: str, is_batch: bool = False) -> Any:
    _rate_limiter.wait()
    sys_prompt = _SYSTEM_PROMPT_BATCH if is_batch else _SYSTEM_PROMPT_SINGLE
    
    # Prefix with gemini/ for litellm routing if it's a gemini model
    model_name = GEMINI_MODEL
    if "gemini" in model_name and not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"
        
    response = litellm.completion(
        model=model_name,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ]
    )
    raw = (response.choices[0].message.content or "").strip()
    
    if not raw:
        raise ValueError("Empty response from LLM")

    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.strip("`").strip()
        if raw.startswith("json"):
            raw = raw[4:].strip()

    parsed = json.loads(raw)
    if is_batch and not isinstance(parsed, list):
        raise ValueError("Unexpected LLM response format: expected list")
    elif not is_batch and not isinstance(parsed, dict):
        raise ValueError("Unexpected LLM response format: expected dict")
    return parsed

def _normalize_result(result: dict) -> dict:
    score = result.get("score", 0)
    try:
        score = int(score)
        score = max(0, min(10, score))
    except (TypeError, ValueError):
        score = 0
    return {
        "verdict": str(result.get("verdict", "no")),
        "score": score,
        "reason": str(result.get("reason", "No reason provided")),
    }

def score_job(job: dict) -> dict:
    """Build the scoring prompt for a job and return the parsed verdict."""
    user_prompt = (
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
        f"Tags: {', '.join(job['tags'][:10])}\n"
        f"Description (excerpt): {job['description'][:LLM_MAX_DESC_CHARS]}"
    )
    try:
        result = _call_llm_raw(user_prompt, is_batch=False)
        return _normalize_result(result)
    except Exception as exc:
        _logger.error("LLM call failed after retries: %s", exc)
        return _normalize_result({"verdict": "no", "score": 0, "reason": "model unavailable"})

def score_jobs_batch(jobs: list[dict]) -> list[dict]:
    """Score a batch of jobs in a single LLM call. Fallback to per-job on error."""
    if not jobs:
        return []

    user_prompt_lines = []
    for i, job in enumerate(jobs):
        user_prompt_lines.append(f"--- Job {i} ---")
        user_prompt_lines.append(f"ID: {i}")
        user_prompt_lines.append(f"Title: {job['title']}")
        user_prompt_lines.append(f"Company: {job['company']}")
        user_prompt_lines.append(f"Location: {job['location']}")
        user_prompt_lines.append(f"Tags: {', '.join(job['tags'][:10])}")
        user_prompt_lines.append(f"Description (excerpt): {job['description'][:LLM_MAX_DESC_CHARS]}")
        user_prompt_lines.append("")

    user_prompt = "\n".join(user_prompt_lines)

    try:
        results = _call_llm_raw(user_prompt, is_batch=True)
        # Match back by id
        result_map = {str(res.get("id")): res for res in results if isinstance(res, dict)}
        
        final_results = []
        for i in range(len(jobs)):
            if str(i) in result_map:
                final_results.append(_normalize_result(result_map[str(i)]))
            else:
                _logger.warning("Job %s missing in batch result, falling back to per-job", i)
                final_results.append(score_job(jobs[i]))
        return final_results

    except Exception as exc:
        _logger.error("Batch LLM call failed: %s. Falling back to per-job scoring.", exc)
        return [score_job(job) for job in jobs]
