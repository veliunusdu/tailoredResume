"""
llm.py — all LLM calls live here.

This module knows nothing about jobs specifically.
It takes a prompt string and returns structured Pydantic objects.
"""
import os
import json
from typing import Any, Type, List, Optional, Dict
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

class ExperienceItem(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str
    description: List[str]

class EducationItem(BaseModel):
    institution: str
    degree: str
    graduation_date: str

class ProjectItem(BaseModel):
    name: str
    description: str
    skills_used: List[str]

class StructuredProfile(BaseModel):
    skills: List[str]
    experience: List[ExperienceItem]
    education: List[EducationItem]
    projects: List[ProjectItem]
    years: int = Field(description="Total years of professional experience")
    desired_role: str = Field(description="Inferred desired role based on history")

class SingleJobEvaluation(BaseModel):
    verdict: str = Field(description="'yes', 'maybe', or 'no'")
    score: int = Field(description="Integer 0-10. 8-10 = strong match, 4-7 = possible, 0-3 = not suitable")
    reason: str = Field(description="One sentence explanation")
    found_skills: List[str] = Field(description="List of required tech stack skills found in candidate's profile.", default_factory=list)
    missing_skills: List[str] = Field(description="List of required tech stack skills missing from candidate's profile.", default_factory=list)

class BatchJobEvaluationItem(BaseModel):
    id: str = Field(description="The job ID from the prompt")
    verdict: str = Field(description="'yes', 'maybe', or 'no'")
    score: int = Field(description="Integer 0-10")
    reason: str = Field(description="One sentence explanation")
    found_skills: List[str] = Field(description="List of required skills found.", default_factory=list)
    missing_skills: List[str] = Field(description="List of required skills missing.", default_factory=list)

class BatchJobEvaluations(BaseModel):
    evaluations: List[BatchJobEvaluationItem]

class SearchIntentLocation(BaseModel):
    location: str
    remote: bool

class SearchIntent(BaseModel):
    queries: List[str]
    locations: List[SearchIntentLocation]
    seniority_levels: List[str] = Field(default_factory=list)
    exclude_titles: List[str] = Field(default_factory=list)
    visa_sponsorship: Optional[bool] = Field(default=None, description="True if the user explicitly needs visa sponsorship, False if they explicitly do not, None if unmentioned.")
    notes: str = ""

class KeywordAnalysis(BaseModel):
    found: List[str]
    missing: List[str]
    score: int = Field(description="ATS match score from 0 to 100 based on keyword overlap.")

class InterviewQuestion(BaseModel):
    question: str
    type: str = Field(description="'Technical', 'Behavioral', or 'Experience'")
    focus: str = Field(description="Brief explanation of what this question tests")

class InterviewQuestionsList(BaseModel):
    questions: List[InterviewQuestion]

class InterviewAnswerGrade(BaseModel):
    score: int = Field(description="Score from 0 to 10")
    feedback: str = Field(description="Constructive feedback on what was good and what to improve")
    ideal_points: List[str] = Field(description="2-3 bullet points of what a perfect answer would include")

class JobSkills(BaseModel):
    skills: List[str] = Field(description="A clean array of technical hard skills (e.g., ['React', 'TypeScript', 'Go'])")

_SYSTEM_PROMPT_SINGLE = """
You are an expert tech recruiter and career advisor.
Your task is to analyze the candidate's profile and the given job description to evaluate the fit, provide recommendations, or answer specific career-related queries.
""".strip()

_SYSTEM_PROMPT_INTENT_PARSER = """
You are an expert career intent parser.
Your task is to take a user's free-text job search request and convert it into a structured SearchIntent object.
Extract their queries (e.g. "backend engineer"), desired locations, desired seniority levels (if any), explicit title exclusions (if any), visa sponsorship needs, and any other notes they mention.
If they do not specify a seniority level, leave the list empty. Do not assume "junior" or "senior" unless explicitly requested.
""".strip()

_SYSTEM_PROMPT_PROFILE_BUILDER = """
You are an expert technical recruiter and resume parser.
Your task is to take a raw unstructured resume text and convert it into a highly structured JSON profile.
Extract all technical skills into a clean array.
Extract the work experience, education, and projects.
Calculate the total years of professional experience (excluding internships unless they are the only experience).
Infer the candidate's desired role based on their most recent positions and skills (e.g. 'Backend Engineer', 'Data Scientist').
""".strip()

def build_scoring_system_prompt(profile: dict) -> str:
    seniority = ", ".join(profile.get("seniority_levels") or []) or "any level — do not penalize seniority either way"
    locations = ", ".join(profile.get("locations") or []) or "Remote"
    dealbreakers = ", ".join(profile.get("exclude_titles") or []) or "none"
    resume_summary = profile.get("resume_summary", "No resume uploaded.")
    structured_data = profile.get("structured_data")
    notes = profile.get("profile_notes", "none")

    if structured_data:
        import json
        resume_context = f"Candidate Profile (Structured JSON):\n{json.dumps(structured_data, indent=2)}"
        missing_flag = ""
    else:
        resume_context = f"Candidate Resume Summary:\n{resume_summary}"
        missing_flag = 'If Candidate Resume Summary is "No resume uploaded." or empty, you MUST cap the score at 5 and set the verdict to "maybe" or "no".'

    return f"""You are an expert job fit evaluator tailored to a specific candidate.

{resume_context}

Target Search Profile:
- Target Seniority: {seniority}
- Target Locations: {locations}
- Additional Notes: {notes}

Explicit Dealbreakers:
- Excluded Titles: {dealbreakers}
- test/sample/fake postings

Your task is to evaluate if a given job matches this specific candidate's resume and target profile.

GRADING RUBRIC & CONSTRAINTS:
1. {missing_flag or "Resume is provided. Base your score heavily on the candidate's actual experience versus the job description requirements."}
2. Location/Dealbreakers: For location mismatches (e.g., job requires on-site when target is Remote-only) or explicit dealbreaker/excluded titles, you MUST set the verdict to "no" and score 0-2.
3. Scoring Scale:
   - 8-10: Strong match (resume and profile align perfectly)
   - 4-7: Possible fit (partial match, or missing resume)
   - 0-3: Non-match or dealbreakers present
4. Skills Extraction: Accurately identify core technical skills from the job description. Cross-reference with the candidate profile to populate `found_skills` and `missing_skills`.
"""

_SYSTEM_PROMPT_KEYWORDS = """
You are an expert ATS (Applicant Tracking System) optimizer.
Your task is to compare a JOB DESCRIPTION against a BASE RESUME and identify key technical skills, tools, and keywords.

1. Extract the top 10-15 most important keywords from the JOB DESCRIPTION.
2. Determine if each keyword is present in the BASE RESUME.
3. Be strict but fair. If a skill is implied (e.g., "Python" in JD, "Django" in Resume), it might still be considered missing unless the keyword "Python" actually appears.
4. Calculate an ATS match score from 0 to 100 based on the percentage of found vs missing keywords and their relative importance.
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

_SYSTEM_PROMPT_SKILL_EXTRACTION = """
You are an expert technical skills extractor.
Your task is to analyze the following JOB DESCRIPTION and extract the core required tech stack.
Return a clean JSON array containing only technical hard skills (e.g., programming languages, frameworks, tools, databases, cloud platforms).
Do not include soft skills like "Communication" or "Teamwork". Do not include generic terms like "Computer Science".
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

class SalaryInsightsResponse(BaseModel):
    listed_salary: str = Field(description="The salary listed in the job description, or 'Not specified'")
    estimated_market_rate: str = Field(description="The estimated market rate for this role, location, and seniority")
    negotiation_leverage: str = Field(description="One of: High, Medium, Low")
    recommendation: str = Field(description="A short 1-2 sentence strategy for negotiation based on the candidate's skills vs the job requirements")

def generate_salary_insights(job_desc: str, job_title: str, job_location: str, resume_text: str) -> dict:
    """Analyze the job and resume to provide salary negotiation insights."""
    prompt = f"""
    You are an expert tech recruiter and salary negotiator.
    Given the following job description and candidate resume, provide salary insights.
    
    Job Title: {job_title}
    Job Location: {job_location}
    
    JOB DESCRIPTION:
    {job_desc}
    
    CANDIDATE RESUME:
    {resume_text}
    """
    
    try:
        res = _call_llm_structured(prompt, SalaryInsightsResponse)
        return res.model_dump()
    except Exception as e:
        _logger.error("Failed to generate salary insights: %s", e)
        return {
            "listed_salary": "Unknown",
            "estimated_market_rate": "Data unavailable",
            "negotiation_leverage": "Medium",
            "recommendation": "Unable to generate insights at this time."
        }


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

def score_job(job: dict, profile: dict) -> dict:
    """Build the scoring prompt for a job and return the parsed verdict."""
    sys_prompt = build_scoring_system_prompt(profile)
    user_prompt = (
        f"Title: {job['title']}\n"
        f"Company: {job['company']}\n"
        f"Location: {job['location']}\n"
        f"Tags: {', '.join(job['tags'][:10])}\n"
        f"Description (excerpt): {job['description'][:LLM_MAX_DESC_CHARS]}"
    )
    try:
        result = _call_llm_structured(user_prompt, SingleJobEvaluation, system_prompt=sys_prompt)
        return _normalize_result(result.model_dump())
    except Exception as exc:
        _logger.error("LLM call failed after retries: %s", exc)
        return _normalize_result({"verdict": "no", "score": 0, "reason": "model unavailable"})

def score_jobs_batch(jobs: list[dict], profile: dict) -> list[dict]:
    """Score a batch of jobs in a single LLM call. Fallback to per-job on error."""
    if not jobs:
        return []

    sys_prompt = build_scoring_system_prompt(profile)

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
        results = _call_llm_structured(user_prompt, BatchJobEvaluations, system_prompt=sys_prompt)
        # Match back by id
        result_map = {str(res.id): res.model_dump() for res in results.evaluations}
        
        final_results = []
        for i in range(len(jobs)):
            if str(i) in result_map:
                final_results.append(_normalize_result(result_map[str(i)]))
            else:
                _logger.warning("Job %s missing in batch result, falling back to per-job", i)
                final_results.append(score_job(jobs[i], profile))
        return final_results

    except Exception as exc:
        _logger.error("Batch LLM call failed: %s. Falling back to per-job scoring.", exc)
        return [score_job(job, profile) for job in jobs]

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

def extract_job_skills(job_description: str) -> list[str]:
    """Extract a list of technical skills from a raw job description."""
    try:
        result = _call_llm_structured(
            f"Extract technical skills from this job description:\n\n{job_description[:LLM_MAX_DESC_CHARS]}", 
            JobSkills, 
            system_prompt="You are an expert at extracting technical hard skills from job descriptions. Only extract hard skills (e.g. 'React', 'Python', 'AWS'), ignore soft skills."
        )
        return result.skills
    except Exception as exc:
        _logger.error("Skill extraction LLM call failed: %s", exc)
        return []

_SYSTEM_PROMPT_INTERVIEW_GRADER = """
You are a senior technical interviewer. 
Your task is to grade a candidate's answer to an interview question.
Be constructive, professional, and highlight exactly what they did well and what they missed.
Provide 2-3 bullet points of what a perfect, 10/10 answer would look like.
""".strip()

def grade_interview_answer(question: str, answer: str, job_description: str, base_resume: str) -> dict:
    """Grade a user's answer to an interview question."""
    user_prompt = (
        f"=== JOB DESCRIPTION ===\n{job_description[:LLM_MAX_DESC_CHARS]}\n\n"
        f"=== CANDIDATE RESUME ===\n{base_resume[:LLM_MAX_DESC_CHARS]}\n\n"
        f"=== INTERVIEW QUESTION ===\n{question}\n\n"
        f"=== CANDIDATE ANSWER ===\n{answer}"
    )
    try:
        result = _call_llm_structured(user_prompt, InterviewAnswerGrade, system_prompt=_SYSTEM_PROMPT_INTERVIEW_GRADER)
        return result.model_dump()
    except Exception as exc:
        _logger.error("Interview grading LLM call failed: %s", exc)
        return {
            "score": 0,
            "feedback": "Failed to grade answer due to an internal error.",
            "ideal_points": []
        }

def parse_search_intent(text: str) -> SearchIntent:
    return _call_llm_structured(text, SearchIntent, system_prompt=_SYSTEM_PROMPT_INTENT_PARSER)

def extract_structured_profile(resume_text: str) -> dict:
    try:
        # Pass a longer text segment since resumes can be long
        result = _call_llm_structured(resume_text[:LLM_MAX_DESC_CHARS * 4], StructuredProfile, system_prompt=_SYSTEM_PROMPT_PROFILE_BUILDER)
        return result.model_dump()
    except Exception as exc:
        _logger.error("Structured profile extraction failed: %s", exc)
        return {}

_EMBEDDINGS_DISABLED = False

def embed_text(text: str) -> list[float]:
    """Generate a vector embedding for the given text."""
    global _EMBEDDINGS_DISABLED
    if _EMBEDDINGS_DISABLED:
        return []
        
    # If using a non-Gemini model (e.g. DeepSeek), we do not have a valid Google API key for embeddings
    if "gemini" not in GEMINI_MODEL.lower():
        _logger.info("Configured model is %s (non-Gemini). Disabling vector embeddings.", GEMINI_MODEL)
        _EMBEDDINGS_DISABLED = True
        return []
        
    try:
        response = litellm.embedding(
            model="gemini/text-embedding-004",
            input=[text[:LLM_MAX_DESC_CHARS * 2]],
        )
        return response.data[0].embedding
    except Exception as exc:
        _logger.error("Embedding generation failed. Disabling future embedding calls: %s", exc)
        _EMBEDDINGS_DISABLED = True
        return []
