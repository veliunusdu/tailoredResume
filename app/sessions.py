import json
from pathlib import Path
import time
from app.config import DATA_DIR
from app.logger import get_logger

_logger = get_logger(__name__)

SESSION_DIR = DATA_DIR / "sessions"
SESSION_DIR.mkdir(parents=True, exist_ok=True)

# Common login URLs for session recording
PLATFORM_LOGIN_URLS = {
    "linkedin": "https://www.linkedin.com/login",
    "workday": "https://myworkdayjobs.com", # General Workday login path varies, but this is a starting point
    "indeed": "https://secure.indeed.com/account/login",
    "glassdoor": "https://www.glassdoor.com/profile/login_input.htm",
}

def _session_path(platform: str) -> Path:
    return SESSION_DIR / f"{platform}.json"

def save_session(platform: str, state: dict):
    """Save Playwright storage state to disk."""
    path = _session_path(platform)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

def load_session(platform: str) -> dict | None:
    """Load Playwright storage state from disk."""
    path = _session_path(platform)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def session_exists(platform: str) -> bool:
    return _session_path(platform).exists()

def delete_session(platform: str) -> bool:
    path = _session_path(platform)
    if path.exists():
        path.unlink()
        return True
    return False

def record_session(platform: str, timeout_seconds: int = 300) -> dict:
    """
    Open a visible browser, navigate to the login page, and poll every 2 seconds
    for the platform's auth cookie. Saves the session as soon as login is detected.

    Returns: { "status": "saved" | "timeout" | "error" }
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "error", "message": "Playwright not installed."}

    login_url = PLATFORM_LOGIN_URLS.get(platform)
    if not login_url:
        return {"status": "error", "message": f"Unknown platform: {platform}"}

    # The specific cookie that confirms a real logged-in session
    auth_cookie_map = {
        "linkedin":  "li_at",
        "indeed":    "INDEED_CSRF_TOKEN",
        "glassdoor": "gdId",
    }
    auth_cookie = auth_cookie_map.get(platform)

    _logger.info("━" * 60)
    _logger.info("🔑 SESSION RECORDING: %s", platform.upper())
    _logger.info("   ➡️  A browser will open at: %s", login_url)
    _logger.info("   ➡️  Log in normally. The session saves AUTOMATICALLY once detected.")
    _logger.info("   ⏰  Timeout: %d seconds", timeout_seconds)
    _logger.info("━" * 60)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=False,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-first-run",
                    "--no-default-browser-check",
                ],
            )
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            # Hide webdriver flag
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded", timeout=15000)
            _logger.info("🌐 Browser opened. Log in to %s, then wait — session saves automatically.", platform)

            # Poll every 2 seconds for the auth cookie
            deadline = time.time() + timeout_seconds
            found = False
            while time.time() < deadline:
                try:
                    if auth_cookie:
                        all_cookies = context.cookies()
                        names = {c["name"] for c in all_cookies}
                        if auth_cookie in names:
                            _logger.info("✅ Auth cookie '%s' detected — logged in! Saving session...", auth_cookie)
                            found = True
                            break
                    else:
                        # For platforms without a known auth cookie, wait 10s then save
                        time.sleep(10)
                        found = True
                        break
                except Exception:
                    pass
                time.sleep(2)

            if not found:
                _logger.warning("⏰ Timeout (%ds) reached without detecting login.", timeout_seconds)

            # Capture storage state while context is still open
            state = context.storage_state()
            cookie_count = len(state.get("cookies", []))
            _logger.info("💾 Captured %d cookies.", cookie_count)

            browser.close()

        save_session(platform, state)

        if not found or cookie_count == 0:
            return {
                "status": "timeout",
                "platform": platform,
                "cookies": cookie_count,
                "message": f"Timeout reached. Make sure you fully log in to {platform} before the timer runs out.",
            }

        _logger.info("🎉 Session saved! %d cookies for %s.", cookie_count, platform)
        return {"status": "saved", "platform": platform, "cookies": cookie_count}

    except Exception as e:
        _logger.error("Session recording failed: %s", e)
        return {"status": "error", "message": str(e)}
