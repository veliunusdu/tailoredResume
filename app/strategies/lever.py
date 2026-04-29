"""Lever ATS strategy — handles jobs.lever.co forms."""
from __future__ import annotations
from app.strategies.base import ApplyStrategy, ApplyPayload, ApplyResult
from app.logger import get_logger

_logger = get_logger(__name__)


class LeverStrategy(ApplyStrategy):

    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        _logger.info("⚙️  Lever adapter: navigating to %s", payload.apply_url)

        try:
            page.goto(payload.apply_url, wait_until="networkidle", timeout=20000)
        except Exception as e:
            return ApplyResult(False, "failed", "lever", error_msg=f"Navigation failed: {e}")

        _logger.info("   📝 Filling standard fields...")
        self._fill_lever_fields(page, payload.profile)
        self.fill_fields(page, payload.profile)

        # Cover letter
        if payload.cover_letter:
            try:
                cl = page.locator('textarea[name*="comments"], textarea[name*="cover"]').first
                if cl.count() > 0:
                    cl.fill(payload.cover_letter, timeout=3000)
                    _logger.info("   📄 Cover letter filled.")
            except Exception:
                pass

        # Resume upload
        _logger.info("   📎 Uploading resume...")
        uploaded = self.upload_resume(page, payload.resume_path)
        _logger.info("   %s Resume upload %s", "✅" if uploaded else "⚠️", "successful" if uploaded else "skipped")

        if dry_run:
            _logger.info("   🔵 DRY RUN — not clicking submit.")
            return ApplyResult(True, "success", "lever")

        # Submit
        _logger.info("   🚀 Submitting application...")
        try:
            page.locator("button[type='submit'], input[type='submit']").first.click(timeout=5000)
            page.wait_for_url(
                lambda url: any(x in url for x in ["confirmation", "thank", "applied"]),
                timeout=10000
            )
            _logger.info("   ✅ Submitted successfully!")
            return ApplyResult(True, "success", "lever")
        except Exception as e:
            _logger.error("   ❌ Submit failed: %s", e)
            return ApplyResult(False, "failed", "lever", error_msg=str(e))

    def _fill_lever_fields(self, page, profile: dict) -> None:
        """Lever uses data-qa attributes for reliable targeting."""
        exact_fields = {
            '[data-qa="name"]':    f"{profile.get('first_name', '')} {profile.get('last_name', '')}".strip(),
            '[data-qa="email"]':   profile.get("email", ""),
            '[data-qa="phone"]':   profile.get("phone", ""),
            '[data-qa="org"]':     "",  # Current company — leave blank
            '[data-qa="urls[LinkedIn]"]':  profile.get("linkedin", ""),
            '[data-qa="urls[Portfolio]"]': profile.get("portfolio", ""),
        }
        for selector, value in exact_fields.items():
            if value:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0:
                        el.fill(value, timeout=3000)
                except Exception:
                    pass
