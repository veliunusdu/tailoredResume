"""
Auto-Apply AI Q&A — powered exclusively by Claude.

All other LLM calls (scoring, tailoring, enrichment) use Gemini.
This module is the ONLY place in the codebase that uses ANTHROPIC_API_KEY.
"""
import os
import json
from typing import Dict, Any
from litellm import completion
from app.config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from app.logger import get_logger

_logger = get_logger(__name__)

# Set the Anthropic key for litellm
if ANTHROPIC_API_KEY:
    os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY
else:
    _logger.warning(
        "⚠️  ANTHROPIC_API_KEY not set. Claude Auto-Apply Q&A will be disabled. "
        "Add it to your .env file: ANTHROPIC_API_KEY=sk-ant-..."
    )

# The model litellm will call — prefix 'anthropic/' is required
_CLAUDE_MODEL = f"anthropic/{CLAUDE_MODEL}" if not CLAUDE_MODEL.startswith("anthropic/") else CLAUDE_MODEL


def is_claude_available() -> bool:
    """Returns True if Claude is configured and ready."""
    return bool(ANTHROPIC_API_KEY)


def answer_question(question_text: str, profile: Dict[str, Any]) -> str:
    """
    Use Claude to answer a job screening question based on the user's profile.

    Returns the answer as a string, or "CANNOT_ANSWER" if the profile
    doesn't contain enough information or Claude is not configured.
    """
    if not is_claude_available():
        _logger.warning("   ⚠️  Claude not configured — skipping AI answer for: %s", question_text[:40])
        return "CANNOT_ANSWER"

    prompt = f"""You are an AI assistant helping a job candidate fill out a job application form.

CANDIDATE PROFILE:
{json.dumps(profile, indent=2)}

SCREENING QUESTION:
{question_text}

STRICT RULES:
1. Answer based ONLY on information in the profile above. Do NOT invent or assume facts.
2. If the information is not in the profile, respond with exactly: CANNOT_ANSWER
3. Be concise and professional. Max 2-3 sentences for open text, single value for dropdowns/numbers.
4. For yes/no questions, answer "Yes" or "No" only.
5. For numeric questions (years of experience, etc.), answer with just the number.

ANSWER:"""

    try:
        response = completion(
            model=_CLAUDE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        answer = response.choices[0].message.content.strip()
        _logger.info("🤖 Claude answered [%.35s...] → '%s'", question_text, answer)
        return answer
    except Exception as e:
        _logger.error("❌ Claude Q&A call failed: %s", e)
        return "CANNOT_ANSWER"
