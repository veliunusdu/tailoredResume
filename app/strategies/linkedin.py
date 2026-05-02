"""LinkedIn Easy Apply strategy — handles linkedin.com/jobs/view/* with Easy Apply."""
from __future__ import annotations
import time
from app.strategies.base import ApplyStrategy, ApplyPayload, ApplyResult
from app.logger import get_logger

_logger = get_logger(__name__)


class LinkedInEasyApplyStrategy(ApplyStrategy):
    """
    Handles LinkedIn Easy Apply modal.
    Requires a saved LinkedIn session (cookies) — use POST /sessions/linkedin/record first.
    """

    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        _logger.info("🔵 LinkedIn Easy Apply adapter starting...")

        try:
            page.goto(payload.job_url, wait_until="domcontentloaded", timeout=20000)
        except Exception as e:
            return ApplyResult(False, "failed", "linkedin", error_msg=f"Navigation failed: {e}")

        # Check if we're logged in
        if "login" in page.url or "authwall" in page.url:
            _logger.error("❌ Not logged into LinkedIn. Run: POST /sessions/linkedin/record")
            return ApplyResult(False, "manual_required", "linkedin",
                               error_msg="LinkedIn session not found. Please record your session first.")

        # Click the Easy Apply button — use CSS class + aria-label, NOT text (works in any language)
        _logger.info("   🖱️  Clicking Easy Apply button...")
        try:
            easy_apply_btn = page.locator(
                "button.jobs-apply-button, "
                "button[aria-label*='Easy Apply'], "
                "button[aria-label*='Kolay Başvuru'], "
                "button[aria-label*='Einfach bewerben'], "
                "button[data-control-name*='apply'], "
                ".jobs-apply-button--top-card"
            ).first
            easy_apply_btn.click(timeout=10000)
            page.wait_for_selector(
                ".jobs-easy-apply-modal, .jobs-easy-apply-content, [data-test-modal]",
                timeout=8000
            )
            _logger.info("   ✅ Easy Apply modal opened.")
        except Exception as e:
            _logger.warning("   ⚠️  Could not open Easy Apply modal: %s", e)
            return ApplyResult(False, "failed", "linkedin", error_msg="Could not open Easy Apply modal (may not be an Easy Apply job).")

        # Multi-step modal navigation
        max_steps = 10
        for step in range(max_steps):
            _logger.info("   📂 Processing modal step %d...", step + 1)
            
            # Fill common fields
            self.fill_fields(page, payload.profile)
            
            # Use Claude to solve any remaining visible/empty tricky fields (screening questions, dropdowns)
            self.solve_tricky_field(page, payload.profile)

            # Handle phone field specifically (LinkedIn often has separate logic for this)
            try:
                phone_input = page.locator("input[id*='phoneNumber']").first
                if phone_input.count() > 0 and phone_input.is_visible():
                    phone_input.fill(payload.profile.get("phone", ""), timeout=2000)
            except Exception:
                pass

            # Handle "Follow company" checkbox
            try:
                follow_inputs = page.locator("input[id*='follow'][type='checkbox']").all()
                for cb in follow_inputs:
                    if cb.is_checked():
                        cb.uncheck()
            except Exception:
                pass

            # Navigation buttons
            submit_btn = page.locator(
                "button[aria-label*='Submit'], button[aria-label*='Gönder'], "
                "button[aria-label*='Başvuruyu gönder'], footer button:last-child"
            ).first
            review_btn = page.locator(
                "button[aria-label*='Review'], button[aria-label*='İncele'], "
                "button[aria-label*='Gözden geçir']"
            ).first
            next_btn = page.locator(
                "button[aria-label*='Next'], button[aria-label*='İleri'], "
                "button[aria-label*='Devam'], button[aria-label*='Continue'], "
                "footer button:last-child"
            ).first

            if submit_btn.count() > 0 and submit_btn.is_visible():
                if dry_run:
                    _logger.info("   🔵 DRY RUN — reached submit step. Not clicking Submit.")
                    return ApplyResult(True, "success", "linkedin")
                _logger.info("   🚀 Clicking Submit application...")
                submit_btn.click(timeout=5000)
                time.sleep(2)
                _logger.info("   ✅ LinkedIn Easy Apply submitted!")
                return ApplyResult(True, "success", "linkedin")

            elif review_btn.count() > 0 and review_btn.is_visible():
                _logger.info("   🔵 Clicking Review...")
                review_btn.click(timeout=5000)
                page.wait_for_timeout(1000)

            elif next_btn.count() > 0 and next_btn.is_visible():
                _logger.info("   ➡️  Clicking Next...")
                next_btn.click(timeout=5000)
                page.wait_for_timeout(1000)
            else:
                _logger.info("   ⏹️ No navigation buttons found. Might be finished or requires manual input.")
                break

        return ApplyResult(True, "success", "linkedin")
