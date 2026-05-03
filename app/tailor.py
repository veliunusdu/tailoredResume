"""Resume tailoring and cover letter generation module."""

import os
import json
from pathlib import Path
import litellm
import instructor
from pydantic import BaseModel, Field
from app.config import DATA_DIR, GEMINI_API_KEY, GEMINI_MODEL
from app.logger import get_logger

_logger = get_logger(__name__)

# Ensure API key is in environment for litellm
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

APPLICATIONS_DIR = DATA_DIR / "applications"


class ProfileSelection(BaseModel):
    selected_file: str = Field(description="The filename of the most relevant resume profile")
    reason: str = Field(description="Brief reason for this selection based on job requirements")

def get_best_base_resume(job_description: str) -> tuple[str | None, str | None]:
    """Find the best base resume from DATA_DIR for the given job description."""
    resume_files = list(DATA_DIR.glob("*.md"))
    
    if not resume_files:
        return None, None
        
    if len(resume_files) == 1:
        return resume_files[0].name, resume_files[0].read_text(encoding="utf-8")
        
    # Multiple profiles found, use LLM to route
    profiles_summary = ""
    profiles_dict = {}
    for rf in resume_files:
        content = rf.read_text(encoding="utf-8")
        profiles_dict[rf.name] = content
        profiles_summary += f"\n--- {rf.name} ---\n{content[:1000]}...\n"

    prompt = f"""
    You are an expert recruiter. Route the JOB DESCRIPTION to the most suitable candidate profile.
    Choose the ONE resume filename that best fits the job requirements.
    
    JOB DESCRIPTION:
    {job_description[:2000]}
    
    AVAILABLE PROFILES (Excerpts):
    {profiles_summary}
    """

    try:
        model_name = GEMINI_MODEL
        if "gemini" in model_name and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"
            
        client = instructor.from_litellm(litellm.completion)
        response = client.chat.completions.create(
            model=model_name,
            response_model=ProfileSelection,
            messages=[{"role": "user", "content": prompt}],
            api_key=GEMINI_API_KEY
        )
        
        selected = response.selected_file
        if selected in profiles_dict:
            _logger.info("🤖 AI selected profile '%s'. Reason: %s", selected, response.reason)
            return selected, profiles_dict[selected]
            
        _logger.warning("AI selected unknown profile '%s', falling back to first.", selected)
        return resume_files[0].name, profiles_dict[resume_files[0].name]
        
    except Exception as e:
        _logger.error("Failed to select best profile: %s. Falling back to first.", e)
        return resume_files[0].name, profiles_dict[resume_files[0].name]


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
    company = job.get("company", "Company")
    title = job.get("title", "Role")
    job_id = job.get("id", "unknown_id")
    desc = job.get("description", "")
    
    if not desc:
        _logger.warning("No description available for job %s. Cannot tailor.", job_id)
        return
        
    resume_name, base_resume = get_best_base_resume(desc)
    if not base_resume:
        _logger.warning("No base resumes found in %s. Skipping tailoring.", DATA_DIR)
        return
        
    _logger.info("Tailoring resume for %s at %s using base profile '%s'...", title, company, resume_name)
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
