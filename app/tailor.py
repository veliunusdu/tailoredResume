"""Resume tailoring and cover letter generation module using local filesystem."""

import os
from pathlib import Path
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

def get_best_base_resume(user_id: str, job_description: str, api_key: str = None) -> tuple[str | None, str | None]:
    """Find the best base resume from local storage for the given user and job description."""
    try:
        resumes_dir = Path("data") / "sessions" / user_id
        if not resumes_dir.exists():
            resumes_dir = Path("data")
            
        resume_files = list(resumes_dir.glob("*.md"))
        if not resume_files:
            _logger.warning("No base resumes found for user %s on disk", user_id)
            return None, None

        profiles_dict = {}
        profiles_summary = ""
        
        for rf in resume_files:
            fname = rf.name
            try:
                content = rf.read_text(encoding="utf-8")
                profiles_dict[fname] = content
                profiles_summary += f"\n--- {fname} ---\n{content[:1000]}...\n"
            except Exception as read_err:
                _logger.error("Failed to read resume %s for user %s: %s", fname, user_id, read_err)

        if not profiles_dict:
            return None, None

        if len(profiles_dict) == 1:
            fname = list(profiles_dict.keys())[0]
            return fname, profiles_dict[fname]

        # Multiple profiles found, use LLM to route
        prompt = f"""
        You are an expert recruiter. Route the JOB DESCRIPTION to the most suitable candidate profile.
        Choose the ONE resume filename that best fits the job requirements.
        
        JOB DESCRIPTION:
        {job_description[:2000]}
        
        AVAILABLE PROFILES (Excerpts):
        {profiles_summary}
        """

        model_name = GEMINI_MODEL
        if "gemini" in model_name and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"
            
        client = instructor.from_litellm(litellm.completion)
        response = client.chat.completions.create(
            model=model_name,
            response_model=ProfileSelection,
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key or GEMINI_API_KEY
        )
        
        selected = response.selected_file
        if selected in profiles_dict:
            _logger.info("🤖 AI selected profile '%s' for user %s. Reason: %s", selected, user_id, response.reason)
            return selected, profiles_dict[selected]
            
        _logger.warning("AI selected unknown profile '%s', falling back to first.", selected)
        first_key = list(profiles_dict.keys())[0]
        return first_key, profiles_dict[first_key]
        
    except Exception as e:
        _logger.error("Failed to select best profile for user %s: %s", user_id, e)
        return None, None


def generate_tailored_resume(job_description: str, base_resume: str, api_key: str = None) -> str | None:
    """Tailor the base resume for the specific job description."""
    prompt = f"""
    You are an expert technical recruiter and resume writer.
    I will provide you with a BASE RESUME and a JOB DESCRIPTION.
    Your task is to tailor the BASE RESUME to match the JOB DESCRIPTION as closely as possible.

    CRITICAL CONSTRAINTS (FACTUAL PRESERVATION):
    1. NEVER invent, fabricate, or hallucinate skills, experiences, or degrees that are not in the BASE RESUME.
    2. You may reorder bullet points to emphasize relevant experience.
    3. You may reword bullet points to use the exact terminology found in the JOB DESCRIPTION.
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
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key or GEMINI_API_KEY
        )
        return response.choices[0].message.content
    except Exception as e:
        _logger.error("Failed to generate tailored resume: %s", e)
        return None


def generate_cover_letter(job_description: str, base_resume: str, company: str, title: str, api_key: str = None) -> str | None:
    """Generate a modern, concise cover letter based on the resume and job."""
    prompt = f"""
    You are an expert career coach. Write a modern, concise, and highly effective cover letter for the position of {title} at {company}.
    Use the candidate's BASE RESUME to highlight 1-2 key achievements that directly map to the JOB DESCRIPTION.
    
    CONSTRAINTS:
    1. Keep it under 300 words.
    2. Do not use generic buzzwords.
    3. No fabrication. Only use facts from the BASE RESUME.
    4. Output plain text or markdown.

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
            messages=[{"role": "user", "content": prompt}],
            api_key=api_key or GEMINI_API_KEY
        )
        return response.choices[0].message.content
    except Exception as e:
        _logger.error("Failed to generate cover letter: %s", e)
        return None


def prepare_application(user_id: str, job: dict, api_key: str = None) -> None:
    """Generate and save tailored materials to Supabase Storage."""
    company = job.get("company", "Company")
    title = job.get("title", "Role")
    job_id = job.get("id", "unknown_id")
    desc = job.get("description", "")
    
    if not desc:
        _logger.warning("No description available for job %s. Cannot tailor.", job_id)
        return
        
    resume_name, base_resume = get_best_base_resume(user_id, desc, api_key=api_key)
    if not base_resume:
        return
        
    _logger.info("Tailoring resume for %s at %s for user %s...", title, company, user_id)
    tailored_resume = generate_tailored_resume(desc, base_resume, api_key=api_key)
    
    _logger.info("Generating cover letter for %s at %s for user %s...", title, company, user_id)
    cover_letter = generate_cover_letter(desc, base_resume, company, title, api_key=api_key)
    
    # Save to local filesystem
    try:
        session_dir = Path("data") / "sessions" / user_id / "tailored" / job_id
        session_dir.mkdir(parents=True, exist_ok=True)
        
        if tailored_resume:
            (session_dir / "resume.md").write_text(tailored_resume, encoding="utf-8")
        
        if cover_letter:
            (session_dir / "cover_letter.md").write_text(cover_letter, encoding="utf-8")
            
        _logger.info("Application materials saved to local storage for user %s, job %s", user_id, job_id)
    except Exception as e:
        _logger.error("Failed to save tailored materials locally for user %s, job %s: %s", user_id, job_id, e)
