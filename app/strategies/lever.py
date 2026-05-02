from __future__ import annotations
import time
from app.strategies.base import ApplyStrategy, ApplyPayload, ApplyResult
from app.logger import get_logger

_logger = get_logger(__name__)

class LeverStrategy(ApplyStrategy):
    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        _logger.info("🟠 Lever adapter starting...")
        
        try:
            page.goto(payload.job_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            return ApplyResult(False, "failed", "lever", error_msg=f"Navigation failed: {e}")

        # Click "Apply for this job" if it's the landing page
        try:
            apply_btn = page.locator("a:has-text('Apply for this job')").first
            if apply_btn.is_visible():
                apply_btn.click()
                page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass

        # Fill fields using heuristics and AI
        self.fill_fields(page, payload.profile)
        
        # Lever specific full name handling if separate fields didn't work
        try:
            name_input = page.locator("input[name='name']").first
            if name_input.count() > 0 and not name_input.input_value():
                name_input.fill(f"{payload.profile.get('first_name')} {payload.profile.get('last_name')}")
        except Exception:
            pass

        # Use Claude for screening questions
        _logger.info("   🧠 Solving screening questions with Claude...")
        self.solve_tricky_field(page, payload.profile)

        # Resume
        try:
            resume_input = page.locator("input[type='file'][id='resume-upload-input']").first
            if payload.resume_path and resume_input.count() > 0:
                resume_input.set_input_files(payload.resume_path)
                _logger.info("   📄 Resume uploaded.")
        except Exception as e:
            _logger.warning("   ⚠️  Resume upload failed: %s", e)

        if dry_run:
            _logger.info("   🔵 DRY RUN — not clicking submit.")
            return ApplyResult(True, "success", "lever")

        try:
            page.click("button#post-button")
            _logger.info("   🚀 Application submitted!")
            return ApplyResult(True, "success", "lever")
        except Exception as e:
            return ApplyResult(False, "failed", "lever", error_msg=f"Submit failed: {e}")
