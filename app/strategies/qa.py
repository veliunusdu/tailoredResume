"""AI-powered Q&A helper for custom screening questions."""
from __future__ import annotations
import os
import litellm
from app.config import GEMINI_MODEL, GEMINI_API_KEY
from app.logger import get_logger

_logger = get_logger(__name__)

os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY


def answer_question(question: str, profile: dict, long_form: bool = False) -> str | None:
    """
    Use the LLM to answer a custom screening question based on the user's profile.
    Returns None if the question can't be answered confidently.
    """
    profile_summary = f"""
Name: {profile.get('first_name', '')} {profile.get('last_name', '')}
Location: {profile.get('location', '')}
LinkedIn: {profile.get('linkedin', '')}
Work Authorization: {profile.get('work_authorization', '')}
Remote Preference: {profile.get('remote_preference', '')}
Salary Expectation: {profile.get('salary_expectation', '')}
Custom Responses: {profile.get('custom_responses', {})}
""".strip()

    word_limit = "under 150 words" if long_form else "under 30 words — ideally just a number or yes/no if applicable"

    prompt = f"""You are filling out a job application for this candidate:
{profile_summary}

Answer the following application question concisely and professionally.
Keep it {word_limit}.
If you cannot answer confidently from the profile above, respond with exactly: CANNOT_ANSWER

Question: {question}"""

    try:
        model_name = GEMINI_MODEL
        if "gemini" in model_name and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"

        response = litellm.completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        answer = response.choices[0].message.content.strip()

        if answer == "CANNOT_ANSWER" or not answer:
            _logger.warning("🤔 Could not answer: '%s'", question[:60])
            return None

        return answer
    except Exception as e:
        _logger.error("Q&A LLM call failed: %s", e)
        return None
