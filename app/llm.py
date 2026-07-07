"""
llm.py — all LLM calls live here.

This module knows nothing about jobs specifically.
It takes a prompt string and returns structured Pydantic objects.
"""
import os
import json
from typing import Any, Type, List
import litellm
import instructor
from pydantic import BaseModel, Field
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
if not GEMINI_API_KEY:
    _logger.error("GEMINI_API_KEY is not set! Check your .env file.")

os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY # Fallback for some litellm versions
os.environ["DEEPSEEK_API_KEY"] = GEMINI_API_KEY

_rate_limiter = RateLimiter(LLM_MIN_INTERVAL_SEC)

# ── Pydantic Models for Instructor ────────────────────────────────────────────

class SingleJobEvaluation(BaseModel):
    verdict: str = Field(description="'yes', 'maybe', or 'no'")
    score: int = Field(description="Integer 0-10. 8-10 = strong match, 4-7 = possible, 0-3 = not suitable")
    reason: str = Field(description="One sentence explanation")

class BatchJobEvaluationItem(BaseModel):
    id: str = Field(description="The job ID from the prompt")
    verdict: str = Field(description="'yes', 'maybe', or 'no'")
    score: int = Field(description="Integer 0-10")
    reason: str = Field(description="One sentence explanation")

class BatchJobEvaluations(BaseModel):
    evaluations: List[BatchJobEvaluationItem]

class KeywordAnalysis(BaseModel):
    found: List[str]
    missing: List[str]

class InterviewQuestion(BaseModel):
    question: str
    type: str = Field(description="'Technical', 'Behavioral', or 'Experience'")
    focus: str = Field(description="Brief explanation of what this question tests")

class InterviewQuestionsList(BaseModel):
    questions: List[InterviewQuestion]

_SYSTEM_PROMPT_SINGLE = """
You are a job fit evaluator for a university student with the following profile:

- Level: beginner / entry-level, currently learning
- Stack: Python, some experience with Flask and basic ML concepts
- Looking for: internships, junior roles, entry-level positions in backend, data, or AI/ML
- Location: open to fully remote worldwide
- Dealbreakers: requires 3+ years experience, requires degree already completed,
  senior/lead/principal roles, test/sample/fake postings
""".strip()

_SYSTEM_PROMPT_BATCH = """
You are a job fit evaluator for a university student with the following profile:

- Level: beginner / entry-level, currently learning
- Stack: Python, some experience with Flask and basic ML concepts
- Looking for: internships, junior roles, entry-level positions in backend, data, or AI/ML
- Location: open to fully remote worldwide
- Dealbreakers: requires 3+ years experience, requires degree already completed,
  senior/lead/principal roles, test/sample/fake postings
""".strip()

_SYSTEM_PROMPT_KEYWORDS = """
You are an expert ATS (Applicant Tracking System) optimizer.
Your task is to compare a JOB DESCRIPTION against a BASE RESUME and identify key technical skills, tools, and keywords.

1. Extract the top 10-15 most important keywords from the JOB DESCRIPTION.
2. Determine if each keyword is present in the BASE RESUME.
3. Be strict but fair. If a skill is implied (e.g., "Python" in JD, "Django" in Resume), it might still be considered missing unless the keyword "Python" actually appears.
""".strip()

_SYSTEM_PROMPT_INTERVIEW = """
You are a senior technical interviewer at a top tech company.
Your task is to generate 5-7 high-quality interview questions tailored to a specific candidate for a specific job.

I will provide you with a JOB DESCRIPTION and the candidate's BASE RESUME.

CRITICAL INSTRUCTIONS:
1. Generate a mix of:
   - Technical: Deep dives into skills mentioned inJD and Resume.
   - Experience-based: Questions about specific projects in the Resume relevant to the JD.
   - Behavioral: Tailored to the company's likely culture based on the JD.
2. For each question, provide a "focus" explanation (why you're asking it).
""".strip()

@retry(
    max_attempts=RETRY_ATTEMPTS,
    initial_delay_sec=RETRY_INITIAL_DELAY_SEC,
    backoff_factor=RETRY_BACKOFF_FACTOR,
    rate_limit_cooldown_sec=LLM_RATE_LIMIT_COOLDOWN_SEC,
    logger=_logger,
)
def _call_llm_structured(user_prompt: str, response_model: Type[BaseModel], system_prompt: str = None) -> BaseModel:
    _rate_limiter.wait()
    sys_prompt = system_prompt or _SYSTEM_PROMPT_SINGLE
    
    # Prefix with gemini/ for litellm routing if it's a gemini model
    model_name = GEMINI_MODEL
    if "gemini" in model_name and not model_name.startswith("gemini/"):
        model_name = f"gemini/{model_name}"
        
    client = instructor.from_litellm(litellm.completion)
        
    response = client.chat.completions.create(
        model=model_name,
        response_model=response_model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        api_key=GEMINI_API_KEY
    )
    return response

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
        result = _call_llm_structured(user_prompt, SingleJobEvaluation, system_prompt=_SYSTEM_PROMPT_SINGLE)
        return _normalize_result(result.model_dump())
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
        results = _call_llm_structured(user_prompt, BatchJobEvaluations, system_prompt=_SYSTEM_PROMPT_BATCH)
        # Match back by id
        result_map = {str(res.id): res.model_dump() for res in results.evaluations}
        
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

def analyze_job_keywords(job_description: str, base_resume: str) -> dict:
    """Analyze keywords in job description and find matches/misses in base resume."""
    user_prompt = (
        f"=== JOB DESCRIPTION ===\n{job_description[:LLM_MAX_DESC_CHARS * 2]}\n\n"
        f"=== BASE RESUME ===\n{base_resume[:LLM_MAX_DESC_CHARS * 2]}"
    )
    try:
        result = _call_llm_structured(user_prompt, KeywordAnalysis, system_prompt=_SYSTEM_PROMPT_KEYWORDS)
        return result.model_dump()
    except Exception as exc:
        _logger.error("Keyword analysis LLM call failed: %s", exc)
        return {"found": [], "missing": []}

def generate_interview_questions(job_description: str, base_resume: str) -> list[dict]:
    """Generate tailored interview questions based on job description and base resume."""
    user_prompt = (
        f"=== JOB DESCRIPTION ===\n{job_description[:LLM_MAX_DESC_CHARS * 2]}\n\n"
        f"=== BASE RESUME ===\n{base_resume[:LLM_MAX_DESC_CHARS * 2]}"
    )
    try:
        result = _call_llm_structured(user_prompt, InterviewQuestionsList, system_prompt=_SYSTEM_PROMPT_INTERVIEW)
        return [q.model_dump() for q in result.questions]
    except Exception as exc:
        _logger.error("Interview questions LLM call failed: %s", exc)
        return []
