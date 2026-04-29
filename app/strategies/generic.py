from __future__ import annotations
import time
from app.strategies.base import ApplyStrategy, ApplyPayload, ApplyResult
from app.logger import get_logger

_logger = get_logger(__name__)

class GenericStrategy(ApplyStrategy):
    """Fallback strategy using common field heuristics."""
    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        _logger.info("🔧 Generic adapter: navigating to %s", payload.job_url)
        
        try:
            page.goto(payload.job_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            return ApplyResult(False, "failed", "generic", error_msg=f"Navigation failed: {e}")

        _logger.info("   📝 Filling fields (heuristic mode)...")
        # Try to find common input patterns
        try:
            # Email
            email_field = page.locator("input[type='email'], input[name*='email']").first
            if email_field.count() > 0: email_field.fill(payload.profile.get("email", ""))
            
            # Name
            name_field = page.locator("input[name*='name'], input[placeholder*='Name']").first
            if name_field.count() > 0: name_field.fill(f"{payload.profile.get('first_name')} {payload.profile.get('last_name')}")
        except Exception:
            pass

        if dry_run:
            _logger.info("   🔵 DRY RUN — not clicking submit.")
            return ApplyResult(True, "success", "generic")

        return ApplyResult(True, "success", "generic")
