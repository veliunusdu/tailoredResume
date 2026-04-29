"""
Browser automation dispatcher for autonomous job applications.

Architecture:
  apply_to_job(job, dry_run) 
      → detect_platform(url)
      → resolve LinkedIn → external ATS URL
      → load saved session (cookies)
      → get_strategy(platform)
      → strategy.apply(page, payload, dry_run)
      → update_apply_status(attempt_id, result)
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

_logger = get_logger(__name__)

MAX_APPLICATIONS_PER_RUN = 10
APPLIED_LOG = DATA_DIR / "applications_log.txt"

# Realistic browser user agent to reduce bot detection
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
    Navigate to a LinkedIn job listing and extract the external 'Apply on company website' URL.
    Returns None if the job only has LinkedIn Easy Apply (requires login).
    """
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
        _logger.warning("   ⚠️  LinkedIn resolve failed: %s", e)
    return None


# ── Resume Resolver ───────────────────────────────────────────────────────────

def _get_resume_path(job: dict) -> Path | None:
    """Return the tailored resume for this job, falling back to the base resume."""
    company = job.get("company", "Company")
    job_id  = job.get("id", "unknown")
    tailored = DATA_DIR / "applications" / f"{company.replace(' ', '_')}_{job_id[:6]}" / "tailored_resume.md"
    if tailored.exists():
        _logger.info("   📄 Using tailored resume: %s", tailored.name)
        return tailored
    base = DATA_DIR / "base_resume.md"
    if base.exists():
        _logger.info("   📄 Using base resume (no tailored version found).")
        return base
    _logger.warning("   ⚠️  No resume found!")
    return None


# ── Main Apply Entry Point ────────────────────────────────────────────────────

def apply_to_job(job: dict, dry_run: bool = True, attempt_id: str = None) -> bool:
    """
    Orchestrates a single job application.
    Returns True on success, False on failure.
    """
    from app.db import update_apply_status

    if not sync_playwright:
        _logger.error("❌ Playwright not installed. Run: playwright install chromium")
        return False

    original_url = job.get("url")
    if not original_url:
        _logger.warning("⚠️  No URL for job.")
        return False

    # Import profile loading from sessions module
    import yaml
    profile_path = DATA_DIR / "profile.yaml"
    profile = {}
    if profile_path.exists():
        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            profile.update(data.get("personal_info", {}))
            profile.update(data.get("links", {}))
            profile.update(data.get("preferences", {}))
            profile["custom_responses"] = data.get("custom_responses", {})

    resume_path = _get_resume_path(job)
    debug_dir   = DATA_DIR / "debug"
    debug_dir.mkdir(exist_ok=True)
    job_id_short = job.get("id", "unknown")[:8]

    _logger.info("━" * 60)
    _logger.info("🤖 AUTO-APPLY STARTED")
    _logger.info("   Title   : %s", job.get("title"))
    _logger.info("   Company : %s", job.get("company"))
    _logger.info("   Score   : %s/10", job.get("score"))
    _logger.info("   Mode    : %s", "🔵 DRY RUN (no submit)" if dry_run else "🔴 LIVE — WILL SUBMIT!")
    _logger.info("━" * 60)

    with sync_playwright() as p:
        _logger.info("🌐 Launching browser...")
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(DATA_DIR / "browser_profile"),
            headless=False,
            user_agent=STEALTH_UA,
            viewport={"width": 1280, "height": 800},
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = context.new_page()

        # Hide webdriver flag for basic anti-bot evasion
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            platform  = detect_platform(original_url)
            apply_url = original_url

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

            # ── Load saved session for this platform if available ──
            elif platform not in ("greenhouse", "lever", "ashby"):
                session_state = load_session(platform)
                if session_state:
                    context.add_cookies(session_state.get("cookies", []))
                    _logger.info("🔑 Loaded %s session.", platform)

            # ── Update DB: running ──
            if attempt_id:
                update_apply_status(attempt_id, "running", job_board=platform)

            # ── Navigate + screenshot before ──
            _logger.info("🌍 Navigating to: %s", apply_url)

            # ── Build payload ──
            payload = ApplyPayload(
                job_id      = job.get("id", ""),
                job_url     = original_url,
                apply_url   = apply_url,
                job_board   = platform,
                profile     = profile,
                resume_path = resume_path,
            )

            # ── Run strategy ──
            strategy = get_strategy(platform)
            _logger.info("📝 Running %s strategy...", platform.upper())

            result: ApplyResult = strategy.apply(page, payload, dry_run=dry_run)

            # ── Screenshot after ──
            screenshot_path = str(debug_dir / f"{job_id_short}_result.png")
            try:
                page.screenshot(path=screenshot_path)
                _logger.info("📸 Screenshot: %s", screenshot_path)
            except Exception:
                screenshot_path = None

            # ── Log result ──
            if result.success:
                _logger.info("✅ Application complete! (status=%s)", result.status)
                with open(APPLIED_LOG, "a", encoding="utf-8") as f:
                    mode = "DRY RUN" if dry_run else "APPLIED"
                    f.write(
                        f"{mode} | {time.strftime('%Y-%m-%d %H:%M:%S')} | "
                        f"{job.get('company')} | {job.get('title')} | {apply_url}\n"
                    )
                if attempt_id:
                    update_apply_status(attempt_id, result.status, platform, screenshot=screenshot_path)
            else:
                _logger.error("❌ Application failed: %s", result.error_msg)
                if attempt_id:
                    update_apply_status(attempt_id, "failed", platform,
                                        error_msg=result.error_msg, screenshot=screenshot_path)

            _logger.info("━" * 60)
            return result.success

        except Exception as e:
            _logger.error("💥 Unexpected error: %s", e)
            screenshot_path = None
            try:
                sp = str(debug_dir / f"{job_id_short}_error.png")
                page.screenshot(path=sp)
                screenshot_path = sp
            except Exception:
                pass
            if attempt_id:
                update_apply_status(attempt_id, "failed", error_msg=str(e), screenshot=screenshot_path)
            return False

        finally:
            context.close()
            _logger.info("🔒 Browser closed.")


# ── Batch Runner ──────────────────────────────────────────────────────────────

def run_autonomous_applications(jobs: list[dict], dry_run: bool = True) -> None:
    """Apply to a list of jobs with rate-limiting delays between each."""
    applied_count = 0
    for job in jobs:
        if applied_count >= MAX_APPLICATIONS_PER_RUN:
            _logger.info("🛑 Reached max applications per run (%d).", MAX_APPLICATIONS_PER_RUN)
            break
        _logger.info("Starting auto-apply for: %s @ %s", job.get("title"), job.get("company"))
        if apply_to_job(job, dry_run=dry_run):
            applied_count += 1
        # Rate-limit: 30–60 second random delay between applications
        delay = random.uniform(30, 60)
        _logger.info("⏳ Waiting %.0fs before next application (rate limiting)...", delay)
        time.sleep(delay)
    _logger.info("🏁 Auto-apply run complete. Applied to %d job(s).", applied_count)
