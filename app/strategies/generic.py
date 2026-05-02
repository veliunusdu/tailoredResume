from __future__ import annotations
import time
from app.strategies.base import ApplyStrategy, ApplyPayload, ApplyResult
from app.logger import get_logger

_logger = get_logger(__name__)

class GenericStrategy(ApplyStrategy):
    """Fallback strategy using common field heuristics and Claude AI."""
    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        _logger.info("🔧 Generic adapter: navigating to %s", payload.job_url)
        
        try:
            page.goto(payload.job_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            return ApplyResult(False, "failed", "generic", error_msg=f"Navigation failed: {e}")

        _logger.info("   📝 Filling fields (heuristic + AI solver)...")
        
        # 1. Standard Heuristics
        self.fill_fields(page, payload.profile)
        
        # 2. Claude AI Solver for screening questions and dropdowns
        _logger.info("   🧠 Solving remaining fields with Claude...")
        self.solve_tricky_field(page, payload.profile)

        # 3. Handle Resume if input exists
        try:
            resume_input = page.locator("input[type='file'][name*='resume'], input[type='file'][id*='resume']").first
            if payload.resume_path and resume_input.count() > 0:
                resume_input.set_input_files(payload.resume_path)
                _logger.info("   📄 Resume uploaded.")
        except Exception:
            pass

        if dry_run:
            _logger.info("   🔵 DRY RUN — reached end of form. Not clicking submit.")
            return ApplyResult(True, "success", "generic")

        # Note: Generic strategy does NOT click submit automatically for safety, 
        # unless it finds a very specific button.
        _logger.warning("   ⚠️  Generic strategy reached end. Manual submission might be required.")
        return ApplyResult(True, "success", "generic")
