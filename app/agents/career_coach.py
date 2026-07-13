from pydantic import BaseModel, Field
from typing import List
from app.llm import _call_llm_structured, LLM_MAX_DESC_CHARS

class RoadmapStep(BaseModel):
    skill: str
    action_items: List[str] = Field(description="2-3 specific things to learn or build")
    estimated_time: str = Field(description="e.g. '1 week', '2 days'")

class SkillGapRoadmap(BaseModel):
    summary: str = Field(description="Encouraging summary of the gap")
    steps: List[RoadmapStep]

_SYSTEM_PROMPT_COACH = """
You are an expert AI Career Coach and Technical Mentor.
A user wants to apply for a job, but they are missing several required skills.
Your task is to generate a fast, actionable, and highly specific learning roadmap to help them bridge the gap.
For each missing skill, give 2-3 specific things they should learn or build, and a realistic time estimate to learn the basics.
Keep it encouraging but realistic.
""".strip()

def generate_skill_roadmap(missing_skills: List[str], job_description: str, base_resume: str) -> dict:
    """Generate an actionable learning roadmap for missing skills."""
    if not missing_skills:
        return {
            "summary": "You have all the required skills for this job! You're good to go.",
            "steps": []
        }

    user_prompt = (
        f"=== MISSING SKILLS ===\n{', '.join(missing_skills)}\n\n"
        f"=== JOB DESCRIPTION ===\n{job_description[:LLM_MAX_DESC_CHARS]}\n\n"
        f"=== BASE RESUME ===\n{base_resume[:LLM_MAX_DESC_CHARS]}"
    )

    try:
        result = _call_llm_structured(user_prompt, SkillGapRoadmap, system_prompt=_SYSTEM_PROMPT_COACH)
        return result.model_dump()
    except Exception as exc:
        import logging
        logging.getLogger("app.agents.career_coach").error("Career coach LLM call failed: %s", exc)
        return {
            "summary": "Failed to generate roadmap.",
            "steps": []
        }


class RejectionReason(BaseModel):
    category: str = Field(description="e.g. 'Skill Gap', 'Experience Level', 'Tooling'")
    explanation: str = Field(description="Honest explanation of why this led to rejection")
    action_to_take: str = Field(description="What to do differently next time")

class RejectionAnalysis(BaseModel):
    harsh_truth: str = Field(description="A blunt but constructive 1-sentence summary of why they were rejected")
    reasons: List[RejectionReason]
    next_steps: str = Field(description="Encouraging closing thought")

_SYSTEM_PROMPT_REJECTION = """
You are an expert technical recruiter giving candid, "behind-closed-doors" feedback to a candidate who was just rejected for a job.
Analyze their BASE RESUME, the JOB DESCRIPTION, and the known MISSING SKILLS.
Be honest about why they likely didn't make the cut. Identify specific gaps (e.g., missing hard skills, not enough senior experience, lack of specific domain knowledge).
Provide actionable advice on what they must improve before applying to similar roles.
""".strip()

def generate_rejection_analysis(missing_skills: List[str], job_description: str, base_resume: str) -> dict:
    """Generate a candid analysis of why the user was likely rejected from a job."""
    user_prompt = (
        f"=== MISSING SKILLS ===\n{', '.join(missing_skills) if missing_skills else 'None identified'}\n\n"
        f"=== JOB DESCRIPTION ===\n{job_description[:LLM_MAX_DESC_CHARS]}\n\n"
        f"=== BASE RESUME ===\n{base_resume[:LLM_MAX_DESC_CHARS]}"
    )

    try:
        result = _call_llm_structured(user_prompt, RejectionAnalysis, system_prompt=_SYSTEM_PROMPT_REJECTION)
        return result.model_dump()
    except Exception as exc:
        import logging
        logging.getLogger("app.agents.career_coach").error("Rejection analysis LLM call failed: %s", exc)
        return {
            "harsh_truth": "Failed to analyze rejection.",
            "reasons": [],
            "next_steps": "Keep applying!"
        }
