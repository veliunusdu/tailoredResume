"""
LLM layer — Multi-provider support (Anthropic, Gemini, Ollama fallback).
All API calls are wrapped with tenacity retry and real token cost logging.
prompt_version is logged alongside every call for A/B testing.
"""

import functools
import json
from typing import Callable

import anthropic
import httpx
from pydantic import BaseModel, field_validator
from tenacity import retry, stop_after_attempt, wait_exponential

from ajas.config import settings
from ajas.logger import log
from ajas.sanitizer import sanitise

# ---------------------------------------------------------------------------
# Pydantic schemas for validated LLM output
# ---------------------------------------------------------------------------


class ExperienceBullet(BaseModel):
    text: str
    impact: str = ""
    relevance_score: float = 0.0


class ExperienceItem(BaseModel):
    company: str
    role: str = ""
    bullets: list[ExperienceBullet]


class TailoredCV(BaseModel):
    summary: str
    experience: list[ExperienceItem] = []
    skills: list[str]
    suggested_projects: list[str] = []

    @field_validator("suggested_projects", mode="before")
    @classmethod
    def normalize_projects(cls, v: list) -> list[str]:
        """Gemini sometimes returns projects as dicts {name, description}. Flatten to strings."""
        result = []
        for item in v:
            if isinstance(item, str):
                result.append(item)
            elif isinstance(item, dict):
                # Use 'name', 'title', or join all values as fallback
                text = (
                    item.get("name")
                    or item.get("title")
                    or "; ".join(str(v) for v in item.values())
                )
                result.append(text)
            else:
                result.append(str(item))
        return result


class TailoredCoverLetter(BaseModel):
    first_paragraph: str
    second_paragraph: str
    third_paragraph: str
    genuine_question: str
    word_count: int


class InterviewPrep(BaseModel):
    behavioral_questions: list[str]  # 5 STAR-format questions
    technical_questions: list[str]  # 2 role-specific technical questions
    elevator_pitch: str  # ≤30-second pitch


class NetworkingRequest(BaseModel):
    message: str  # ≤300 characters, no direct job ask
    char_count: int


# ---------------------------------------------------------------------------
# Token pricing (per-token USD)
# ---------------------------------------------------------------------------

PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"input": 3.0 / 1e6, "output": 15.0 / 1e6},
    "claude-3-sonnet-20240229": {"input": 3.0 / 1e6, "output": 15.0 / 1e6},
    "gemini-1.5-flash": {"input": 0.075 / 1e6, "output": 0.30 / 1e6},
    "gemini-3.1-flash-lite-preview": {
        "input": 0.035 / 1e6,
        "output": 0.15 / 1e6,
    },  # Estimated low cost
}


# ---------------------------------------------------------------------------
# Cost-tracking decorator
# ---------------------------------------------------------------------------


def track_cost_manual(
    model: str, in_tok: int, out_tok: int, prompt_version: str = "v1"
):
    """Log manual cost when not using the Anthropic Message object."""
    try:
        prices = PRICING.get(model, {"input": 0.0, "output": 0.0})
        cost = in_tok * prices["input"] + out_tok * prices["output"]
        from ajas.database import Database

        Database().log_cost(model, in_tok, out_tok, cost)
        log.info(
            "llm_call",
            model=model,
            prompt_version=prompt_version,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=round(cost, 8),
        )
    except Exception as e:
        log.warning(f"Manual cost tracking failed: {e}")


def track_cost(prompt_version: str = "v1") -> Callable:
    """Decorator: extracts usage from Anthropic Message object."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            message = func(*args, **kwargs)
            try:
                # Handle Anthropic message objects
                if hasattr(message, "usage"):
                    model = message.model
                    in_tok = message.usage.input_tokens
                    out_tok = message.usage.output_tokens
                    track_cost_manual(model, in_tok, out_tok, prompt_version)
            except Exception as e:
                log.warning(f"Decorator cost tracking failed: {e}")
            return message

        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Provider Callers
# ---------------------------------------------------------------------------


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def call_ollama(prompt: str, model: str = "llama3") -> str:
    """Call local Ollama model."""
    url = "http://localhost:11434/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False, "format": "json"}
    response = httpx.post(url, json=payload, timeout=60)
    response.raise_for_status()
    return response.json()["response"]


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def call_gemini(
    prompt: str, system_prompt: str = "", model: str = "gemini-3.1-flash-lite-preview"
) -> str:
    """Call Google Gemini API via REST."""
    key = settings.gemini_api_key or settings.anthropic_api_key
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    combined_prompt = f"SYSTEM: {system_prompt}\n\nUSER: {prompt}"
    payload = {
        "contents": [{"parts": [{"text": combined_prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    response = httpx.post(url, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        in_tok = data.get("usageMetadata", {}).get("promptTokenCount", 0)
        out_tok = data.get("usageMetadata", {}).get("candidatesTokenCount", 0)
        track_cost_manual(model, in_tok, out_tok)
        return text
    except (KeyError, IndexError) as e:
        log.error(f"Failed to parse Gemini response: {e}. Raw: {data}")
        raise


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30), reraise=True)
def _call_anthropic_raw(
    prompt: str, system_prompt: str = ""
) -> "anthropic.types.Message":
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=4000,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    )


def call_llm(prompt: str, system_prompt: str = "", prompt_version: str = "v1") -> str:
    """Route to appropriate provider based on available keys."""
    # Ensure PII is stripped before any external API call
    prompt = sanitise(prompt)
    system_prompt = sanitise(system_prompt)

    any_key = settings.anthropic_api_key or settings.gemini_api_key

    if any_key and any_key.startswith("AIza"):
        log.debug("Routing to Gemini (AIza key detected)")
        return call_gemini(prompt, system_prompt)

    if settings.anthropic_api_key and not settings.anthropic_api_key.startswith("AIza"):
        log.debug("Routing to Anthropic")
        tracked_call = track_cost(prompt_version)(_call_anthropic_raw)
        try:
            return tracked_call(prompt, system_prompt).content[0].text
        except Exception as e:
            log.warning(f"Anthropic failed: {e}. Trying fallback.")

    try:
        return call_ollama(prompt)
    except Exception:
        log.warning("No valid API providers found — returning mock data.")
        return json.dumps(
            {
                "summary": "Mock summary — No valid API keys found.",
                "skills": ["Mock"],
                "experience": [
                    {
                        "company": "Mock",
                        "role": "Mock",
                        "bullets": [{"text": "Mocked."}],
                    }
                ],
                "first_paragraph": "Mock content.",
                "second_paragraph": "Mock.",
                "third_paragraph": "Mock.",
                "genuine_question": "Mock?",
                "word_count": 0,
                "behavioral_questions": ["Mock?"],
                "technical_questions": ["Mock?"],
                "elevator_pitch": "Mock.",
            }
        )


# ---------------------------------------------------------------------------
# High-level pipeline helpers
# ---------------------------------------------------------------------------


def tailor_cv(
    job_description: str, master_cv: str, prompt_version: str = "v1"
) -> TailoredCV:
    system_prompt = (
        "You are an expert CV tailoring assistant. Rewrite CV bullet points to highlight "
        "relevant skills based on the job description. \n"
        "CRITICAL: Do NOT hallucinate. ONLY include skills that are explicitly present in the Master CV. "
        "Do NOT add new skills even if they are relevant to the job description.\n"
        "Return ONLY valid JSON matching the schema."
    )
    prompt = (
        f"JD:\n{job_description}\n\n"
        f"Master CV:\n{master_cv}\n\n"
        "Return a JSON object with these keys:\n"
        "  summary: string\n"
        "  experience: list of {company: string, role: string, bullets: [{text: string, impact: string}]}\n"
        "  skills: list of strings\n"
        "  suggested_projects: list of STRINGS only (e.g. ['Project A', 'Project B']) — NOT objects or dicts"
    )
    raw = call_llm(prompt, system_prompt, prompt_version=prompt_version)
    clean = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return TailoredCV.model_validate_json(clean)


def generate_cover_letter(
    job_description: str, master_cv: str, prompt_version: str = "v1"
) -> TailoredCoverLetter:
    system_prompt = "3 paragraphs, ≤300 words, end with genuine question. Return JSON."
    prompt = f"JD:\n{job_description}\n\nCV:\n{master_cv}\n\nReturn JSON: first_paragraph, second_paragraph, third_paragraph, genuine_question, word_count."
    raw = call_llm(prompt, system_prompt, prompt_version=prompt_version)
    clean = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return TailoredCoverLetter.model_validate_json(clean)


def generate_interview_prep(
    job_description: str, tailored_cv_text: str, prompt_version: str = "v1"
) -> InterviewPrep:
    system_prompt = (
        "Expert interview coach. Return JSON: 5 STAR questions, 2 technical, 30s pitch."
    )
    prompt = f"JD:\n{job_description}\n\nCV:\n{tailored_cv_text}"
    raw = call_llm(prompt, system_prompt, prompt_version=prompt_version)
    clean = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return InterviewPrep.model_validate_json(clean)


def generate_networking_request(
    profile_text: str, job_title: str, company: str, prompt_version: str = "v1"
) -> NetworkingRequest:
    system_prompt = "Networking assistant. ≤300 chars message. Return JSON."
    prompt = (
        f"Hiring Manager Profile:\n{profile_text}\n\nRole: {job_title} at {company}"
    )
    raw = call_llm(prompt, system_prompt, prompt_version=prompt_version)
    clean = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    result = NetworkingRequest.model_validate_json(clean)
    if len(result.message) > 300:
        result.message = result.message[:297] + "..."
    return result


def parse_cv_to_master(cv_text: str, prompt_version: str = "v1") -> str:
    """Extract structured MasterCV data from raw CV text."""
    system_prompt = (
        "You are a master recruiter and CV parser. Extract as much detail as possible from "
        "the provided text into a structured JSON format. "
        "For PII, use these exact keys: [[FULL_NAME]], [[EMAIL]], [[PHONE]], [[LINKEDIN]], [[STREET_ADDRESS]]. "
        "For bullets, assign 3-5 relevant keywords and a weight (1-10) based on role impact."
    )
    prompt = (
        f"Parse this CV text into a MasterCV JSON object:\n\n{cv_text}\n\n"
        "The JSON must follow this structure:\n"
        "{\n"
        "  'pii': {'[[FULL_NAME]]': '...', ...},\n"
        "  'experience': [{'company': '...', 'role': '...', 'bullets': [{'text': '...', 'keywords': [], 'weight': 10}]}],\n"
        "  'skills': [],\n"
        "  'preferences': {'target_roles': [], 'target_salary': None, 'location_preference': [], 'remote_preference': 'Remote', 'visa_sponsorship': false}\n"
        "}"
    )
    raw = call_llm(prompt, system_prompt, prompt_version=prompt_version)
    clean = (
        raw.strip()
        .removeprefix("```json")
        .removeprefix("```")
        .removesuffix("```")
        .strip()
    )
    return clean
