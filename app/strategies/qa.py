import os
import json
from typing import Dict, Any
from litellm import completion
from app.config import GEMINI_MODEL, GEMINI_API_KEY, ANTHROPIC_API_KEY
from app.logger import get_logger

_logger = get_logger(__name__)

# Set environment variables for litellm
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY
if ANTHROPIC_API_KEY:
    os.environ["ANTHROPIC_API_KEY"] = ANTHROPIC_API_KEY

def answer_question(question_text: str, profile: Dict[str, Any]) -> str:
    """
    Use LLM to answer a screening question based on the user's profile.
    """
    prompt = f"""
    You are an AI assistant helping a candidate apply for a job.
    Based on the candidate's profile below, answer the following screening question.
    
    CANDIDATE PROFILE:
    {json.dumps(profile, indent=2)}
    
    QUESTION:
    {question_text}
    
    INSTRUCTIONS:
    - Answer truthfully based ONLY on the profile.
    - If the answer is not in the profile, respond with "CANNOT_ANSWER".
    - Keep the answer concise and professional.
    - If it's a numeric question (e.g. "Years of experience"), respond with just the number or a short phrase.
    
    ANSWER:
    """
    
    try:
        response = completion(
            model=GEMINI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200
        )
        answer = response.choices[0].message.content.strip()
        _logger.info("🤖 AI Answered: '%s' -> '%s'", question_text[:30], answer)
        return answer
    except Exception as e:
        _logger.error("❌ AI Question answering failed: %s", e)
        return "CANNOT_ANSWER"
