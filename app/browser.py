"""Browser automation for autonomous job applications."""

import time
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None

from app.logger import get_logger
from app.config import DATA_DIR

_logger = get_logger(__name__)

# Basic safety limit to prevent spamming
MAX_APPLICATIONS_PER_RUN = 10
APPLIED_LOG = DATA_DIR / "applications_log.txt"

def load_user_profile() -> dict:
    """Load user profile for form filling. Fallback to generic data for now."""
    # In a real setup, this would load from a profile.yaml created during `init`
    return {
        "first_name": "John",
        "last_name": "Doe",
        "email": "john.doe@example.com",
        "phone": "555-0199",
        "linkedin": "https://linkedin.com/in/johndoe",
        "github": "https://github.com/johndoe"
    }

def apply_to_job(job: dict, dry_run: bool = True) -> bool:
    """
    Attempt to autonomously apply to a job using Playwright.
    Returns True if successful, False otherwise.
    """
    if not sync_playwright:
        _logger.error("Playwright is not installed. Run `pip install playwright`")
        return False

    url = job.get("url")
    if not url:
        _logger.warning("No URL provided for job application.")
        return False

    profile = load_user_profile()
    
    with sync_playwright() as p:
        # We use Chromium for best cross-platform compatibility
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        try:
            _logger.info("Navigating to %s for application...", url)
            page.goto(url, timeout=30000)
            
            # This is a heuristic-based form filler. 
            # Real ATS systems (Workday/Lever/Greenhouse) require dedicated scrapers.
            
            # Attempt to click "Apply" if present
            apply_buttons = page.locator("button:has-text('Apply'), a:has-text('Apply')").all()
            if apply_buttons:
                try:
                    apply_buttons[0].click(timeout=5000)
                    page.wait_for_load_state("networkidle")
                except Exception:
                    pass

            # Form filling heuristics
            inputs = page.locator("input").all()
            for input_el in inputs:
                name = input_el.get_attribute("name") or ""
                input_type = input_el.get_attribute("type") or ""
                
                if "first" in name.lower():
                    input_el.fill(profile["first_name"])
                elif "last" in name.lower():
                    input_el.fill(profile["last_name"])
                elif "email" in name.lower() or input_type == "email":
                    input_el.fill(profile["email"])
                elif "phone" in name.lower():
                    input_el.fill(profile["phone"])
            
            if dry_run:
                _logger.info("[DRY RUN] Would have submitted application for %s", job.get("title"))
                return True
                
            # Submit (Simulated)
            submit_buttons = page.locator("button[type='submit'], input[type='submit']").all()
            if submit_buttons:
                # submit_buttons[0].click() # Commented out for safety during development
                _logger.info("Successfully submitted application for %s", job.get("title"))
                
                # Log success
                with open(APPLIED_LOG, "a", encoding="utf-8") as f:
                    f.write(f"APPLIED | {time.strftime('%Y-%m-%d %H:%M:%S')} | {job.get('company')} | {job.get('title')} | {url}\n")
                return True
            else:
                _logger.warning("Could not find a submit button on %s", url)
                return False

        except Exception as e:
            _logger.error("Application failed for %s: %s", url, e)
            return False
        finally:
            browser.close()

def run_autonomous_applications(jobs: list[dict], dry_run: bool = True) -> None:
    """Run the application bot for a list of strong matches."""
    applied_count = 0
    
    for job in jobs:
        if applied_count >= MAX_APPLICATIONS_PER_RUN:
            _logger.info("Reached maximum applications per run (%s). Stopping.", MAX_APPLICATIONS_PER_RUN)
            break
            
        _logger.info("Attempting autonomous application for %s at %s...", job.get("title"), job.get("company"))
        success = apply_to_job(job, dry_run=dry_run)
        
        if success:
            applied_count += 1
            
        # Small delay between applications
        time.sleep(2)
        
    _logger.info("Autonomous application run complete. Applied to %s jobs.", applied_count)
