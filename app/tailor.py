"""Resume tailoring and cover letter generation module."""

import os
import litellm
import instructor
from pydantic import BaseModel, Field
from app.config import GEMINI_API_KEY, GEMINI_MODEL
from app.logger import get_logger

_logger = get_logger(__name__)

# Ensure API key is in environment for litellm
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY


class ProfileSelection(BaseModel):
    selected_file: str = Field(description="The filename of the most relevant resume profile")
    reason: str = Field(description="Brief reason for this selection based on job requirements")

def get_best_base_resume(job_description: str, user_id: str | None = None) -> tuple[str | None, str | None]:
    """
    Find the best base resume for the given job description.
    When user_id is provided, queries the PostgreSQL resumes table.
    Falls back to local DATA_DIR/*.md for backward compatibility.
    """
    if user_id:
        from app.resumes import get_best_resume
        return get_best_resume(user_id=user_id, job_description=job_description)

    # Legacy local-file fallback (single-user / dev mode)
    from app.config import DATA_DIR
    resume_files = list(DATA_DIR.glob("*.md"))
    if not resume_files:
        return None, None
    if len(resume_files) == 1:
        return resume_files[0].name, resume_files[0].read_text(encoding="utf-8")

    # Multiple local files — pick the first one (LLM routing moved to resumes.py)
    _logger.warning(
        "Multiple local resumes found and no user_id provided. Using %s.",
        resume_files[0].name,
    )
    return resume_files[0].name, resume_files[0].read_text(encoding="utf-8")


def generate_tailored_resume(job_description: str, base_resume: str) -> str | None:
    """
    Tailor the base resume for the specific job description.
    Strict constraint: NO FABRICATION. Factual preservation only.
    """
    prompt = f"""
    You are an expert technical recruiter and resume writer.
    I will provide you with a BASE RESUME and a JOB DESCRIPTION.
    Your task is to tailor the BASE RESUME to match the JOB DESCRIPTION as closely as possible.

    CRITICAL CONSTRAINTS (FACTUAL PRESERVATION):
    1. NEVER invent, fabricate, or hallucinate skills, experiences, or degrees that are not in the BASE RESUME.
    2. You may reorder bullet points to emphasize relevant experience.
    3. You may reword bullet points to use the exact terminology found in the JOB DESCRIPTION (e.g., changing "Built UI" to "Developed frontend interfaces" if the job asks for that), provided the core truth remains identical.
    4. You may omit irrelevant experience if it distracts from the core requirements.
    5. Output the result in clean Markdown format.

    === JOB DESCRIPTION ===
    {job_description}

    === BASE RESUME ===
    {base_resume}
    """

    try:
        model_name = GEMINI_MODEL
        if "gemini" in model_name and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"
            
        response = litellm.completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        _logger.error("Failed to generate tailored resume: %s", e)
        return None


def generate_cover_letter(job_description: str, resume_context: str, company: str, title: str) -> str | None:
    """Generate a modern, concise cover letter based on the tailored resume and job."""
    prompt = f"""
    You are an expert career coach. Write a modern, concise, and highly effective cover letter for the position of {title} at {company}.
    Use the candidate's TAILORED RESUME to highlight 1-2 key achievements that directly map to the JOB DESCRIPTION.
    
    CONSTRAINTS:
    1. Keep it under 300 words.
    2. Do not use generic buzzwords. Be specific about the impact.
    3. No fabrication. Only use facts from the TAILORED RESUME.
    4. Output plain text or markdown without the [Your Name] placeholders if the name is in the resume.

    === JOB DESCRIPTION ===
    {job_description}

    === TAILORED RESUME ===
    {resume_context}
    """

    try:
        model_name = GEMINI_MODEL
        if "gemini" in model_name and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"
            
        response = litellm.completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content
    except Exception as e:
        _logger.error("Failed to generate cover letter: %s", e)
        return None


def prepare_application(job: dict, user_id: str | None = None, task_id: str | None = None) -> dict:
    """
    Generate tailored resume and cover letter for a job.
    Returns a dict with 'tailored_resume' and 'cover_letter' keys.
    When user_id is provided, fetches the resume from the DB.
    """
    from app.db import update_task_progress
    company = job.get("company", "Company")
    title = job.get("title", "Role")
    job_id = job.get("id", "unknown_id")
    desc = job.get("description", "")

    result = {"tailored_resume": None, "cover_letter": None, "interview_questions": None}

    if not desc:
        _logger.warning("No description available for job %s. Cannot tailor.", job_id)
        return result

    if task_id and user_id:
        update_task_progress(task_id, user_id, "running", "Selecting best base resume profile...", 40)
    resume_name, base_resume = get_best_base_resume(desc, user_id=user_id)
    if not base_resume:
        _logger.warning("No base resume found for user %s. Skipping tailoring.", user_id)
        return result

    if task_id and user_id:
        update_task_progress(task_id, user_id, "running", "Tailoring resume bullet points...", 65)
    _logger.info("Tailoring resume for %s at %s using profile '%s'...", title, company, resume_name)
    tailored_resume = generate_tailored_resume(desc, base_resume)

    if task_id and user_id:
        update_task_progress(task_id, user_id, "running", "Generating tailored cover letter...", 85)
    _logger.info("Generating cover letter for %s at %s...", title, company)
    cover_letter = generate_cover_letter(desc, tailored_resume or base_resume, company, title)

    if task_id and user_id:
        update_task_progress(task_id, user_id, "running", "Generating tailored interview questions...", 92)
    _logger.info("Generating interview questions for %s at %s...", title, company)
    from app.llm import generate_interview_questions
    interview_questions = generate_interview_questions(desc, base_resume)

    result["tailored_resume"] = tailored_resume
    result["cover_letter"] = cover_letter
    result["interview_questions"] = interview_questions

    # Optionally save to local disk in dev mode (when no user_id)
    if not user_id:
        from pathlib import Path
        from app.config import DATA_DIR
        applications_dir = DATA_DIR / "applications"
        job_dir = applications_dir / f"{company.replace(' ', '_')}_{job_id[:6]}"
        job_dir.mkdir(parents=True, exist_ok=True)
        if tailored_resume:
            (job_dir / "tailored_resume.md").write_text(tailored_resume, encoding="utf-8")
        if cover_letter:
            (job_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
        _logger.info("Application materials saved to %s", job_dir)

    _logger.info("✅ Application materials ready for job %s", job_id)
    return result
