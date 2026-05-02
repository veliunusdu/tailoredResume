"""Browser automation for autonomous job applications."""
from __future__ import annotations
import time
import random
import os
from pathlib import Path
from urllib.parse import urlparse
import yaml

from app.logger import get_logger
from app.config import DATA_DIR, BASE_DIR
from app.db import update_apply_status
from app.sessions import load_session

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

_logger = get_logger(__name__)

# Heuristic-based platform detection
def detect_platform(url: str) -> str:
    """Detect the job board from the URL."""
    domain = urlparse(url).netloc.lower()
    if "linkedin.com" in domain:             return "linkedin"
    if "greenhouse.io" in domain:            return "greenhouse"
    if "lever.co" in domain:                 return "lever"
    if "ashbyhq.com" in domain:              return "ashby"
    if "workday.com" in domain:              return "workday"
    if "myworkdayjobs.com" in domain:        return "workday"
    if "smartrecruiters.com" in domain:      return "generic"
    if "jobvite.com" in domain:              return "generic"
    return "generic"


# Auth cookies that confirm a real logged-in session per platform
_AUTH_COOKIES = {
    "linkedin": "li_at",
    "indeed":   "INDEED_CSRF_TOKEN",
    "glassdoor": "gdId",
}


def _is_valid_session(platform: str, state: dict) -> bool:
    """Return True only if the session contains the expected auth cookie."""
    required = _AUTH_COOKIES.get(platform)
    if not required:
        return bool(state.get("cookies"))  # for unknown platforms, just check non-empty
    cookie_names = {c["name"] for c in state.get("cookies", [])}
    has_auth = required in cookie_names
    if not has_auth:
        _logger.warning(
            "⚠️  Session for %s exists but is missing auth cookie '%s'. "
            "You need to re-record — run: curl -X DELETE http://localhost:8000/sessions/%s "
            "then: curl -X POST http://localhost:8000/sessions/%s/record",
            platform, required, platform, platform
        )
    return has_auth


# ── LinkedIn URL Resolver ─────────────────────────────────────────────────────

def _resolve_linkedin_apply_url(page, job_url: str) -> str | None:
    """
    Check if a LinkedIn job has an external 'Apply' link.
    If it's just 'Easy Apply', this returns None.
    """
    try:
        page.goto(job_url, wait_until="domcontentloaded", timeout=15000)
        # Look for the 'Apply on company website' button
        btn = page.locator("a[data-tracking-control-name*='apply'], a:has-text('Apply on company website'), a:has-text('Apply on')").first
        if btn.count() > 0:
            href = btn.get_attribute("href", timeout=5000)
            return href
    except Exception as e:
        _logger.warning("   ⚠️  LinkedIn resolve failed: %s", e)
    return None


# ── Main Dispatcher ────────────────────────────────────────────────────────────

def apply_to_job(original_url: str, dry_run: bool = True, attempt_id: str = None) -> bool:
    """
    Main entry point for autonomous application.
    Automatically detects platform and selects the correct strategy.
    """
    if not sync_playwright:
        _logger.error("❌ Playwright not installed.")
        return False

    platform = detect_platform(original_url)
    apply_url = original_url
    
    # Load user data
    profile_path = DATA_DIR / "profile.yaml"
    if not profile_path.exists():
        _logger.error("❌ Profile not found at %s. Run 'init' first.", profile_path)
        return False
        
    with open(profile_path, 'r', encoding='utf-8') as f:
        profile = yaml.safe_load(f)

    # Find resume
    resume_path = str(DATA_DIR / "resume.pdf")  # Default base resume
    job_hash = hashlib.md5(original_url.encode()).hexdigest()[:8]
    tailored_resume = DATA_DIR / "applications" / f"{job_hash}_resume.pdf"
    
    if tailored_resume.exists():
        resume_path = str(tailored_resume)
        _logger.info("   📄 Using tailored resume: %s", tailored_resume.name)
    else:
        _logger.info("   📄 Using base resume (no tailored version found).")

    from app.strategies import get_strategy, ApplyPayload
    
    _logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    _logger.info("🤖 AUTO-APPLY STARTED")
    _logger.info("   Mode    : %s", "🔵 DRY RUN (no submit)" if dry_run else "🚀 LIVE SUBMIT")
    _logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    if attempt_id:
        update_apply_status(attempt_id, "running")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False) # Visible for debugging
        context = browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        try:
            _logger.info("🌐 Launching browser...")
            _logger.info("🔍 Platform detected: %s", platform.upper())

            # ── LinkedIn: try external ATS first, then Easy Apply ──
            if platform == "linkedin":
                session_state = load_session("linkedin")
                valid_session = session_state and _is_valid_session("linkedin", session_state)

                if valid_session:
                    _logger.info("🔑 LinkedIn session valid (%d cookies) — loading...", len(session_state.get("cookies", [])))
                    context.add_cookies(session_state.get("cookies", []))
                else:
                    _logger.info("   No valid LinkedIn session — checking for external apply link...")

                # First: check for an external "Apply on company website" link
                resolved = _resolve_linkedin_apply_url(page, original_url)
                if resolved:
                    apply_url = resolved
                    platform  = detect_platform(apply_url)
                    _logger.info("✅ External ATS found: %s (%s)", apply_url, platform.upper())

                elif valid_session:
                    _logger.info("🔵 No external link — attempting LinkedIn Easy Apply with saved session...")
                    platform = "linkedin_easyapply"
                    apply_url = original_url

                else:
                    msg = (
                        "No external apply link found, and no valid LinkedIn session.\n"
                        "   → Run in a new terminal:\n"
                        "       curl -X POST http://localhost:8000/sessions/linkedin/record\n"
                        "   → Log in to LinkedIn in the browser that opens, then close it."
                    )
                    _logger.warning("⚠️  %s", msg)
                    if attempt_id:
                        update_apply_status(attempt_id, "manual_required", "linkedin", error_msg=msg)
                    return False

            # ── Generic Session Loading ──
            elif platform != "generic":
                state = load_session(platform)
                if state:
                    _logger.info("🔑 Loaded session for %s (%d cookies)", platform, len(state.get("cookies", [])))
                    context.add_cookies(state.get("cookies", []))
                else:
                    _logger.warning("⚠️  No saved session for %s. Some sites may require login.", platform)

            _logger.info("🌍 Navigating to: %s", apply_url)
            _logger.info("📝 Running %s strategy...", platform.upper())

            # ── Execute Strategy ──
            payload = ApplyPayload(
                job_url=apply_url,
                profile=profile,
                resume_path=resume_path
            )
            
            strategy = get_strategy(platform)
            result = strategy.apply(page, payload, dry_run=dry_run)

            # Screenshot result
            debug_dir = DATA_DIR / "debug"
            debug_dir.mkdir(exist_ok=True)
            shot_path = debug_dir / f"{job_hash}_result.png"
            page.screenshot(path=str(shot_path))
            _logger.info("📸 Screenshot: %s", shot_path)

            if result.success:
                _logger.info("✅ Application complete! (status=%s)", result.status)
                if attempt_id:
                    update_apply_status(attempt_id, result.status, platform, screenshot_path=str(shot_path))
            else:
                _logger.error("❌ Application failed: %s", result.error_msg)
                if attempt_id:
                    update_apply_status(attempt_id, result.status, platform, error_msg=result.error_msg, screenshot_path=str(shot_path))

            _logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            browser.close()
            return result.success

        except Exception as e:
            _logger.error("❌ Fatal error during application: %s", e)
            if attempt_id:
                update_apply_status(attempt_id, "failed", platform, error_msg=str(e))
            browser.close()
            return False

def run_autonomous_applications(jobs: list[dict], dry_run: bool = True):
    """Bulk application runner for the CLI pipeline."""
    _logger.info("🚀 Starting bulk application run for %d jobs...", len(jobs))
    for job in jobs:
        apply_to_job(job["url"], dry_run=dry_run)

import hashlib
