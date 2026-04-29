from __future__ import annotations
import time
from app.strategies.base import ApplyStrategy, ApplyPayload, ApplyResult
from app.logger import get_logger
from app.strategies.qa import answer_question

_logger = get_logger(__name__)

class GreenhouseStrategy(ApplyStrategy):
    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        _logger.info("🟢 Greenhouse adapter starting...")
        
        try:
            page.goto(payload.job_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            return ApplyResult(False, "failed", "greenhouse", error_msg=f"Navigation failed: {e}")

        # Basic fields
        try:
            page.fill("input[name='job_application[first_name]']", payload.profile.get("first_name", ""))
            page.fill("input[name='job_application[last_name]']", payload.profile.get("last_name", ""))
            page.fill("input[name='job_application[email]']", payload.profile.get("email", ""))
            page.fill("input[name='job_application[phone]']", payload.profile.get("phone", ""))
        except Exception as e:
            _logger.warning("   ⚠️  Failed to fill some basic fields: %s", e)

        # Resume upload
        try:
            if payload.resume_path:
                page.set_input_files("input[type='file'][data-qa='resume-upload']", payload.resume_path)
                _logger.info("   📄 Resume uploaded.")
        except Exception as e:
            _logger.warning("   ⚠️  Resume upload failed: %s", e)

        # Custom Questions (QA)
        questions = page.locator(".custom-question, .question").all()
        for q in questions:
            label = q.locator("label").first
            if label.count() > 0:
                text = label.inner_text().strip()
                _logger.info("   ❓ Question found: %s", text[:40])
                
                # Try to answer via AI
                answer = answer_question(text, payload.profile)
                if answer != "CANNOT_ANSWER":
                    # Try to find input/textarea inside the question block
                    input_field = q.locator("input[type='text'], textarea").first
                    if input_field.count() > 0:
                        input_field.fill(answer)

        if dry_run:
            _logger.info("   🔵 DRY RUN — not clicking submit.")
            return ApplyResult(True, "success", "greenhouse")

        try:
            page.click("#submit_app")
            _logger.info("   🚀 Application submitted!")
            return ApplyResult(True, "success", "greenhouse")
        except Exception as e:
            return ApplyResult(False, "failed", "greenhouse", error_msg=f"Submit failed: {e}")
