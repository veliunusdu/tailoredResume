"""
Browser automation dispatcher for autonomous job applications.
Now user-aware for multi-user session management and resume storage.
"""

import time
import random
from pathlib import Path
from urllib.parse import urlparse

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from app.logger import get_logger
from app.config import DATA_DIR
from app.sessions import load_session
from app.strategies import get_strategy
from app.strategies.base import ApplyPayload, ApplyResult
from app.utils import minify_dom
from app.resilience import send_webhook_alert, generate_selector_patch

_logger = get_logger(__name__)

MAX_APPLICATIONS_PER_RUN = 10
APPLIED_LOG = DATA_DIR / "applications_log.txt"

STEALTH_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ── Platform Detection ────────────────────────────────────────────────────────

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
        return bool(state.get("cookies"))
    cookie_names = {c["name"] for c in state.get("cookies", [])}
    has_auth = required in cookie_names
    if not has_auth:
        _logger.warning("⚠️ Session for %s exists but is missing auth cookie.", platform)
    return has_auth


# ── LinkedIn URL Resolver ─────────────────────────────────────────────────────

def _resolve_linkedin_apply_url(page, job_url: str) -> str | None:
    """Extract external apply URL from LinkedIn job listing."""
    _logger.info("   🔗 Looking for external apply link on LinkedIn...")
    try:
        page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
        apply_link = page.locator(
            "a[data-tracking-control-name*='apply'], "
            "a:has-text('Apply on company website'), "
            "a:has-text('Apply on')"
        ).first
        href = apply_link.get_attribute("href", timeout=5000)
        if href and href.startswith("http") and "linkedin.com" not in href:
            return href
    except Exception as e:
        _logger.warning("   ⚠️ LinkedIn resolve failed: %s", e)
    return None


# ── Resume Resolver ───────────────────────────────────────────────────────────

def _get_resume_path(user_id: str, job: dict) -> Path | None:
    """Resolve the tailored or base resume path on the local disk."""
    job_id  = job.get("id", "unknown")
    
    try:
        # 1. Try tailored resume first
        tailored_path = Path("data") / "sessions" / user_id / "tailored" / job_id / "resume.md"
        if tailored_path.exists():
            _logger.info("   📄 Using tailored resume from local storage.")
            return tailored_path
            
        # 2. Fallback to base resume
        base_path = Path("data") / "sessions" / user_id / "base_resume.md"
        if base_path.exists():
            _logger.info("   📄 Using base resume from local storage.")
            return base_path
            
        # 3. Try global fallback in data/ base resume
        fallback_path = Path("data") / "base_resume.md"
        if fallback_path.exists():
            _logger.info("   📄 Using global fallback base resume.")
            return fallback_path
            
        _logger.error("   ⚠️ No base resumes found for user %s on local disk.", user_id)
        return None
            
    except Exception as e:
        _logger.error("   ⚠️ Resume resolution failed for user %s: %s", user_id, e)
        return None


# ── Main Apply Entry Point ────────────────────────────────────────────────────

def apply_to_job(user_id: str, job: dict, dry_run: bool = True, attempt_id: str = None) -> bool:
    """
    Orchestrates a single job application for a specific user.
    """
    from app.db import update_apply_status

    if not sync_playwright:
        _logger.error("❌ Playwright not installed.")
        return False

    original_url = job.get("url")
    if not original_url:
        _logger.warning("⚠️ No URL for job.")
        return False

    # Load user profile and secrets
    import yaml
    from app.db import get_user_secret, list_user_secrets
    
    profile_path = DATA_DIR / "profile.yaml"
    profile = {}
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            profile.update(data.get("personal_info", {}))
            profile.update(data.get("links", {}))
            profile.update(data.get("preferences", {}))
            profile["custom_responses"] = data.get("custom_responses", {})
    
    # Inject decrypted secrets
    profile["secrets"] = {}
    secret_keys = list_user_secrets(user_id)
    for sk in secret_keys:
        profile["secrets"][sk] = get_user_secret(user_id, sk)

    resume_path = _get_resume_path(user_id, job)
    if not resume_path:
        _logger.error("❌ Cannot apply without a resume.")
        if attempt_id:
            update_apply_status(user_id, attempt_id, "failed", error_msg="Resume not found in Supabase Storage.")
        return False
        
    debug_dir   = DATA_DIR / "debug"
    debug_dir.mkdir(exist_ok=True)
    job_id_short = job.get("id", "unknown")[:8]

    _logger.info("━" * 60)
    _logger.info("🤖 JOB APPLICATION STARTED (USER: %s)", user_id)
    _logger.info("   Title   : %s", job.get("title"))
    _logger.info("   Company : %s", job.get("company"))
    _logger.info("   Mode    : %s", "🔵 DRY RUN" if dry_run else "🔴 LIVE — WILL SUBMIT!")
    _logger.info("━" * 60)

    with sync_playwright() as p:
        _logger.info("🌐 Launching browser...")
        from app.config import BROWSERLESS_URL, PLAYWRIGHT_PROXY_URL
        
        proxy_config = None
        if PLAYWRIGHT_PROXY_URL:
            proxy_config = {"server": PLAYWRIGHT_PROXY_URL}
            _logger.info("   📡 Using proxy: %s", PLAYWRIGHT_PROXY_URL)

        if BROWSERLESS_URL:
            _logger.info("   ☁️  Connecting to Browserless.io...")
            # Browserless uses connect_over_cdp
            browser = p.chromium.connect_over_cdp(BROWSERLESS_URL)
            context = browser.new_context(
                user_agent=STEALTH_UA,
                viewport={"width": 1280, "height": 800},
                proxy=proxy_config
            )
        else:
            user_profile_dir = DATA_DIR / "browser_profiles" / user_id
            user_profile_dir.mkdir(parents=True, exist_ok=True)
            
            context = p.chromium.launch_persistent_context(
                user_data_dir=str(user_profile_dir),
                headless=False,
                user_agent=STEALTH_UA,
                viewport={"width": 1280, "height": 800},
                proxy=proxy_config,
                args=["--disable-blink-features=AutomationControlled"],
            )

        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            platform  = detect_platform(original_url)
            apply_url = original_url

            _logger.info("🔍 Platform detected: %s", platform.upper())

            # ── LinkedIn Handling ──
            if platform == "linkedin":
                session_state = load_session(user_id, "linkedin")
                valid_session = session_state and _is_valid_session("linkedin", session_state)

                if valid_session:
                    _logger.info("🔑 LinkedIn session valid — loading from Supabase...")
                    context.add_cookies(session_state.get("cookies", []))
                else:
                    _logger.info("   No valid LinkedIn session — checking for external apply link...")

                resolved = _resolve_linkedin_apply_url(page, original_url)
                if resolved:
                    apply_url = resolved
                    platform  = detect_platform(apply_url)
                    _logger.info("✅ External ATS found: %s (%s)", apply_url, platform.upper())
                elif valid_session:
                    _logger.info("🔵 No external link — attempting LinkedIn Easy Apply...")
                    platform = "linkedin_easyapply"
                    apply_url = original_url
                else:
                    msg = "No external apply link found, and no valid LinkedIn session."
                    _logger.warning("⚠️ %s", msg)
                    if attempt_id:
                        update_apply_status(user_id, attempt_id, "manual_required", "linkedin", error_msg=msg)
                    return False

            # ── Load saved session for other platforms ──
            elif platform not in ("greenhouse", "lever", "ashby"):
                session_state = load_session(user_id, platform)
                if session_state:
                    context.add_cookies(session_state.get("cookies", []))
                    _logger.info("🔑 Loaded %s session from Supabase.", platform)

            if attempt_id:
                update_apply_status(user_id, attempt_id, "running", job_board=platform)

            _logger.info("🌍 Navigating to: %s", apply_url)

            payload = ApplyPayload(
                job_id      = job.get("id", ""),
                job_url     = original_url,
                apply_url   = apply_url,
                job_board   = platform,
                profile     = profile,
                resume_path = resume_path,
            )

            strategy = get_strategy(platform)
            _logger.info("📝 Running %s strategy...", platform.upper())

            result: ApplyResult = strategy.apply(page, payload, dry_run=dry_run)

            screenshot_path = str(debug_dir / f"{job_id_short}_result.png")
            try:
                page.screenshot(path=screenshot_path)
            except Exception:
                screenshot_path = None

            if result.success:
                _logger.info("✅ Application complete! (status=%s)", result.status)
                if attempt_id:
                    update_apply_status(user_id, attempt_id, result.status, platform, screenshot=screenshot_path)
            else:
                _logger.error("❌ Application failed: %s", result.error_msg)
                if attempt_id:
                    update_apply_status(user_id, attempt_id, "failed", platform,
                                        error_msg=result.error_msg, screenshot=screenshot_path)

            return result.success

        except Exception as e:
            error_message = str(e)
            _logger.error("💥 Unexpected error: %s", error_message)
            
            # Resilience Background Thread
            import threading
            def _background_diagnosis(uid, aid, err_msg, plat, captured_dom):
                suggestion = generate_selector_patch(err_msg, captured_dom)
                if aid:
                    from app.db import update_apply_status
                    update_apply_status(uid, aid, "failed", job_board=plat, error_msg=err_msg, ai_patch_suggestion=suggestion)
                send_webhook_alert(job.get("title", "Unknown"), plat or "generic", err_msg, suggestion)
            
            try:
                raw_html = page.content()
                minified = minify_dom(raw_html)
                current_platform = platform if 'platform' in locals() else None
                threading.Thread(target=_background_diagnosis, args=(user_id, attempt_id, error_message, current_platform, minified), daemon=True).start()
            except Exception:
                pass

            screenshot_path = None
            try:
                sp = str(debug_dir / f"{job_id_short}_error.png")
                page.screenshot(path=sp)
                screenshot_path = sp
            except Exception:
                pass
            if attempt_id:
                update_apply_status(user_id, attempt_id, "failed", error_msg=error_message, screenshot=screenshot_path)
            return False

        finally:
            context.close()
            # If we connected to browserless, we might need to close the browser object too
            if BROWSERLESS_URL and 'browser' in locals():
                browser.close()
            _logger.info("🔒 Browser closed.")
            
            # Cleanup temp resume
            try:
                if resume_path and resume_path.exists():
                    resume_path.unlink()
            except Exception:
                pass
