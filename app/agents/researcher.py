from pydantic import BaseModel, Field
from typing import List
from app.llm import _call_llm_structured
import logging

_logger = logging.getLogger("app.agents.researcher")

class CompanyValue(BaseModel):
    title: str
    description: str

class CompanyDossier(BaseModel):
    summary: str = Field(description="A 2-sentence summary of what the company does")
    recent_news: List[str] = Field(description="2-3 plausible recent news or initiatives")
    culture_values: List[CompanyValue] = Field(description="2-3 inferred core values of the company")
    tech_stack_hints: List[str] = Field(description="Inferred tech stack based on their industry or job description")

_SYSTEM_PROMPT_RESEARCHER = """
You are an expert tech recruiter and company researcher.
Your task is to generate a concise "Company Dossier" based on a company's name and a job description.
If you know of the company, use your external knowledge. If the company is unknown, infer their domain, culture, and stack based on the job description provided.
Keep the dossier professional, highly actionable, and brief.
""".strip()

def generate_company_dossier(company_name: str, job_description: str) -> dict:
    """Generate a quick research dossier for a company."""
    user_prompt = (
        f"=== COMPANY NAME ===\n{company_name}\n\n"
        f"=== JOB DESCRIPTION ===\n{job_description[:2000]}"
    )
    
    try:
        result = _call_llm_structured(user_prompt, CompanyDossier, system_prompt=_SYSTEM_PROMPT_RESEARCHER)
        return result.model_dump()
    except Exception as exc:
        _logger.error("Company researcher LLM call failed: %s", exc)
        return {
            "summary": f"Could not generate research for {company_name}.",
            "recent_news": [],
            "culture_values": [],
            "tech_stack_hints": []
        }
