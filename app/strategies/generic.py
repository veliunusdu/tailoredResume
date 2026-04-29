"""Generic fallback strategy using heuristic field detection."""
from __future__ import annotations
from app.strategies.base import ApplyStrategy, ApplyPayload, ApplyResult
from app.logger import get_logger

_logger = get_logger(__name__)


class GenericStrategy(ApplyStrategy):

    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        _logger.info("🔧 Generic adapter: navigating to %s", payload.apply_url)

        try:
            page.goto(payload.apply_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            return ApplyResult(False, "failed", "generic", error_msg=f"Navigation failed: {e}")

        # Click the primary apply button if it's a listing page
        try:
            btn = page.locator(
                "a:has-text('Apply'), button:has-text('Apply'), "
                "a:has-text('Apply Now'), button:has-text('Apply Now')"
            ).first
            if btn.count() > 0:
                btn.click(timeout=5000)
                page.wait_for_load_state("networkidle", timeout=10000)
                _logger.info("   🖱️  Clicked 'Apply' button.")
        except Exception:
            pass

        _logger.info("   📝 Filling fields (heuristic mode)...")
        self.fill_fields(page, payload.profile)
        self.upload_resume(page, payload.resume_path)

        if dry_run:
            _logger.info("   🔵 DRY RUN — not clicking submit.")
            return ApplyResult(True, "success", "generic")

        try:
            page.locator("button[type='submit'], input[type='submit']").first.click(timeout=5000)
            _logger.info("   ✅ Submit clicked.")
            return ApplyResult(True, "success", "generic")
        except Exception as e:
            _logger.error("   ❌ Submit failed: %s", e)
            return ApplyResult(False, "failed", "generic", error_msg=str(e))
