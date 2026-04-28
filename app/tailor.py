"""Resume tailoring and cover letter generation module."""

import os
import json
from pathlib import Path
import litellm
from app.config import DATA_DIR, GEMINI_API_KEY, GEMINI_MODEL
from app.logger import get_logger

_logger = get_logger(__name__)

# Ensure API key is in environment for litellm
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

BASE_RESUME_PATH = DATA_DIR / "base_resume.md"
APPLICATIONS_DIR = DATA_DIR / "applications"


def get_base_resume() -> str | None:
    if BASE_RESUME_PATH.exists():
        return BASE_RESUME_PATH.read_text(encoding="utf-8")
    return None


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


def generate_cover_letter(job_description: str, base_resume: str, company: str, title: str) -> str | None:
    """Generate a modern, concise cover letter based on the resume and job."""
    prompt = f"""
    You are an expert career coach. Write a modern, concise, and highly effective cover letter for the position of {title} at {company}.
    Use the candidate's BASE RESUME to highlight 1-2 key achievements that directly map to the JOB DESCRIPTION.
    
    CONSTRAINTS:
    1. Keep it under 300 words.
    2. Do not use generic buzzwords. Be specific about the impact.
    3. No fabrication. Only use facts from the BASE RESUME.
    4. Output plain text or markdown without the [Your Name] placeholders if the name is in the resume.

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
        _logger.error("Failed to generate cover letter: %s", e)
        return None


def prepare_application(job: dict) -> None:
    """Generate and save tailored materials for a job."""
    base_resume = get_base_resume()
    if not base_resume:
        _logger.warning("No base resume found at %s. Skipping tailoring.", BASE_RESUME_PATH)
        return

    company = job.get("company", "Company")
    title = job.get("title", "Role")
    job_id = job.get("id", "unknown_id")
    desc = job.get("description", "")
    
    if not desc:
        _logger.warning("No description available for job %s. Cannot tailor.", job_id)
        return
        
    _logger.info("Tailoring resume for %s at %s...", title, company)
    tailored_resume = generate_tailored_resume(desc, base_resume)
    
    _logger.info("Generating cover letter for %s at %s...", title, company)
    cover_letter = generate_cover_letter(desc, base_resume, company, title)
    
    # Save to disk
    job_dir = APPLICATIONS_DIR / f"{company.replace(' ', '_')}_{job_id[:6]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    
    if tailored_resume:
        (job_dir / "tailored_resume.md").write_text(tailored_resume, encoding="utf-8")
    if cover_letter:
        (job_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
        
    _logger.info("Application materials saved to %s", job_dir)

