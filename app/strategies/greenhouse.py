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

        # Use base heuristics for basic fields
        self.fill_fields(page, payload.profile)

        # Resume upload
        try:
            resume_input = page.locator("input[type='file'][data-qa='resume-upload'], input[type='file'][id='resume_upload']").first
            if payload.resume_path and resume_input.count() > 0:
                resume_input.set_input_files(payload.resume_path)
                _logger.info("   📄 Resume uploaded.")
        except Exception as e:
            _logger.warning("   ⚠️  Resume upload failed: %s", e)

        # Custom Questions (AI Solver)
        _logger.info("   🧠 Solving screening questions with Claude...")
        self.solve_tricky_field(page, payload.profile)

        if dry_run:
            _logger.info("   🔵 DRY RUN — not clicking submit.")
            return ApplyResult(True, "success", "greenhouse")

        try:
            page.click("#submit_app")
            _logger.info("   🚀 Application submitted!")
            return ApplyResult(True, "success", "greenhouse")
        except Exception as e:
            return ApplyResult(False, "failed", "greenhouse", error_msg=f"Submit failed: {e}")
