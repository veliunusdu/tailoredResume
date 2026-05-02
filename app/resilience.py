"""Diagnosis engine for analyzing strategy failures and alerting."""
from __future__ import annotations
import os
import requests
import litellm
from app.config import WEBHOOK_URL, GEMINI_MODEL, GEMINI_API_KEY
from app.logger import get_logger

_logger = get_logger(__name__)

# Ensure API key is available for litellm
os.environ["GEMINI_API_KEY"] = GEMINI_API_KEY

def send_webhook_alert(title: str, platform: str, error_msg: str, suggestion: str = None) -> None:
    """Send a failure alert to the configured WEBHOOK_URL (Slack/Discord)."""
    if not WEBHOOK_URL:
        _logger.warning("WEBHOOK_URL not configured. Skipping alert.")
        return

    content = f"⚠️ **Job Application Failure**\n\n**Job:** {title}\n**Platform:** {platform}\n**Error:** `{error_msg}`"
    if suggestion:
        content += f"\n\n🤖 **AI Patch Suggestion:** `{suggestion}`"

    try:
        # Generic webhook format (works for Discord and Slack with 'text' or 'content' keys)
        payload = {"content": content, "text": content} 
        response = requests.post(WEBHOOK_URL, json=payload, timeout=10)
        response.raise_for_status()
        _logger.info("✅ Webhook alert sent.")
    except Exception as e:
        _logger.error("❌ Failed to send webhook alert: %s", e)

def generate_selector_patch(error_msg: str, minified_dom: str) -> str:
    """
    Use Gemini to analyze the error and minified DOM to suggest a corrected CSS/XPath selector.
    """
    if not minified_dom:
        return "No DOM content available for analysis."

    prompt = f"""
You are a senior QA automation engineer specializing in Playwright and robust CSS selectors.

An automated job application failed with the following error:
"{error_msg}"

This usually means a CSS selector in our strategy script is broken due to a UI update on the website.

Below is the minified HTML (DOM) of the page at the time of failure. 
Find the most stable, reliable CSS or XPath selector for the element that failed (e.g., the 'First Name' input, the 'Apply' button, etc.).

Return ONLY the corrected selector string. No explanation, no conversational filler, no code blocks.

--- MINIFIED DOM ---
{minified_dom}
""".strip()

    try:
        model_name = GEMINI_MODEL
        if "gemini" in model_name and not model_name.startswith("gemini/"):
            model_name = f"gemini/{model_name}"

        _logger.info("🤖 Requesting AI patch suggestion...")
        response = litellm.completion(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            api_key=GEMINI_API_KEY
        )
        suggestion = response.choices[0].message.content.strip()
        _logger.info("✅ AI Suggestion received: %s", suggestion)
        return suggestion
    except Exception as e:
        _logger.error("❌ AI patch generation failed: %s", e)
        return f"AI analysis failed: {str(e)}"

def diagnose_and_alert(job_id: str, title: str, platform: str, error_msg: str, minified_dom: str) -> None:
    """
    Background task to generate a patch and send an alert.
    This is intended to be called asynchronously.
    """
    from app.db import update_apply_status
    
    # 1. Generate patch
    suggestion = generate_selector_patch(error_msg, minified_dom)
    
    # 2. Find the latest attempt for this job to update it
    # Note: In a production environment, we'd pass the attempt_id directly.
    # For now, we'll log it and alert.
    _logger.info("Diagnosing failure for Job %s: %s", job_id, title)
    
    # 3. Send alert
    send_webhook_alert(title, platform, error_msg, suggestion)
    
    # 4. Note: The attempt status update with suggestion will happen in app/browser.py 
    # to ensure attempt_id is available.
