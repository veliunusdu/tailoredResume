"""
Session management for browser automation.
Now using Supabase to store sessions per user.
"""

import json
from app.logger import get_logger

_logger = get_logger(__name__)

PLATFORM_LOGIN_URLS = {
    "linkedin":  "https://www.linkedin.com/login",
    "workday":   "https://www.myworkdayjobs.com",
    "indeed":    "https://secure.indeed.com/account/login",
    "glassdoor": "https://www.glassdoor.com/profile/login_input.htm",
}


def session_exists(user_id: str, platform: str) -> bool:
    """Check whether a saved session exists for the user and platform."""
    from app.db import get_connection
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT 1 FROM user_sessions WHERE user_id = ? AND platform = ?",
                (user_id, platform)
            ).fetchone()
            return row is not None
    except Exception as e:
        _logger.error(f"Error checking session existence: {e}")
        return False


def save_session(user_id: str, platform: str, state: dict) -> None:
    """Persist a Playwright storage_state dict to local SQLite."""
    from app.db import get_connection
    cookies_json = json.dumps(state)
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO user_sessions (user_id, platform, cookies) VALUES (?, ?, ?)",
                (user_id, platform, cookies_json)
            )
            conn.commit()
        _logger.info("✅ Session saved locally for user %s, platform %s", user_id, platform)
    except Exception as e:
        _logger.error(f"Failed to save session locally: {e}")


def load_session(user_id: str, platform: str) -> dict | None:
    """Load a saved Playwright storage_state dict from SQLite. Returns None if missing."""
    from app.db import get_connection
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT cookies FROM user_sessions WHERE user_id = ? AND platform = ?",
                (user_id, platform)
            ).fetchone()
            if row and row["cookies"]:
                state = json.loads(row["cookies"])
                _logger.info("🔑 Loaded local session for %s (%d cookies)", platform, len(state.get("cookies", [])))
                return state
        return None
    except Exception as e:
        _logger.error(f"Failed to load session locally: {e}")
        return None


def delete_session(user_id: str, platform: str) -> bool:
    """Delete a saved session from SQLite."""
    from app.db import get_connection
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM user_sessions WHERE user_id = ? AND platform = ?",
                (user_id, platform)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        _logger.error(f"Failed to delete session: {e}")
        return False


def record_session(user_id: str, platform: str, timeout_seconds: int = 300) -> dict:
    """
    Open a visible browser, navigate to the login page, and poll every 2 seconds
    for the platform's auth cookie. Saves the session to Supabase as soon as login is detected.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"status": "error", "message": "Playwright not installed."}

    login_url = PLATFORM_LOGIN_URLS.get(platform)
    if not login_url:
        return {"status": "error", "message": f"Unknown platform: {platform}"}

    auth_cookie_map = {
        "linkedin":  "li_at",
        "indeed":    "INDEED_CSRF_TOKEN",
        "glassdoor": "gdId",
    }
    auth_cookie = auth_cookie_map.get(platform)

    _logger.info("━" * 60)
    _logger.info("🔑 SESSION RECORDING (USER: %s): %s", user_id, platform.upper())
    _logger.info("━" * 60)

    import time

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
            context.add_init_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )

            page = context.new_page()
            page.goto(login_url, wait_until="domcontentloaded", timeout=15000)
            _logger.info("🌐 Browser opened. Log in to %s, then wait — session saves automatically.", platform)

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
                        time.sleep(10)
                        found = True
                        break
                except Exception:
                    pass
                time.sleep(2)

            if not found:
                _logger.warning("⏰ Timeout (%ds) reached without detecting login.", timeout_seconds)

            state = context.storage_state()
            cookie_count = len(state.get("cookies", []))
            _logger.info("💾 Captured %d cookies.", cookie_count)

            browser.close()

        save_session(user_id, platform, state)

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
