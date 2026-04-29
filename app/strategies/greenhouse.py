"""Greenhouse ATS strategy — handles boards.greenhouse.io forms."""
from __future__ import annotations
import time
from app.strategies.base import ApplyStrategy, ApplyPayload, ApplyResult
from app.logger import get_logger

_logger = get_logger(__name__)


class GreenhouseStrategy(ApplyStrategy):

    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        _logger.info("🌱 Greenhouse adapter: navigating to %s", payload.apply_url)

        try:
            page.goto(payload.apply_url, wait_until="networkidle", timeout=20000)
        except Exception as e:
            return ApplyResult(False, "failed", "greenhouse", error_msg=f"Navigation failed: {e}")

        # 1. Fill standard fields using exact Greenhouse selectors first,
        #    then fall back to heuristic filler for anything else
        _logger.info("   📝 Filling standard fields...")
        self._fill_greenhouse_fields(page, payload.profile)
        self.fill_fields(page, payload.profile)  # heuristic fallback

        # 2. Cover letter
        if payload.cover_letter:
            try:
                cl_field = page.locator('textarea[name*="cover"], textarea[id*="cover"]').first
                if cl_field.count() > 0:
                    cl_field.fill(payload.cover_letter, timeout=3000)
                    _logger.info("   📄 Cover letter filled.")
            except Exception:
                pass

        # 3. Resume upload
        _logger.info("   📎 Uploading resume...")
        uploaded = self.upload_resume(page, payload.resume_path)
        _logger.info("   %s Resume upload %s", "✅" if uploaded else "⚠️", "successful" if uploaded else "skipped")

        # 4. Custom screening questions (AI-powered)
        answered = self._handle_custom_questions(page, payload)

        if dry_run:
            _logger.info("   🔵 DRY RUN — not clicking submit.")
            return ApplyResult(True, "success", "greenhouse", answered_questions=answered)

        # 5. Submit
        _logger.info("   🚀 Submitting application...")
        try:
            page.locator("button#submit_app, button[type='submit']").first.click(timeout=5000)
            page.wait_for_url(
                lambda url: any(x in url for x in ["confirmation", "thank", "applied", "success"]),
                timeout=10000
            )
            _logger.info("   ✅ Submitted successfully!")
            return ApplyResult(True, "success", "greenhouse", answered_questions=answered)
        except Exception as e:
            _logger.error("   ❌ Submit failed: %s", e)
            return ApplyResult(False, "failed", "greenhouse", error_msg=str(e), answered_questions=answered)

    def _fill_greenhouse_fields(self, page, profile: dict) -> None:
        """Use Greenhouse's known exact field names."""
        exact_fields = {
            '[name="first_name"]': profile.get("first_name", ""),
            '[name="last_name"]':  profile.get("last_name", ""),
            '[name="email"]':      profile.get("email", ""),
            '[name="phone"]':      profile.get("phone", ""),
        }
        for selector, value in exact_fields.items():
            if value:
                try:
                    el = page.locator(selector).first
                    if el.count() > 0:
                        el.fill(value, timeout=3000)
                except Exception:
                    pass

    def _handle_custom_questions(self, page, payload: ApplyPayload) -> list[str]:
        """Use AI to answer unknown screening questions."""
        from app.strategies.qa import answer_question
        answered = []

        try:
            # Find all visible question labels and their associated inputs
            labels = page.locator("label:visible").all()
            for label in labels:
                try:
                    question_text = label.text_content().strip()
                    if not question_text or len(question_text) < 5:
                        continue

                    for_id = label.get_attribute("for")
                    if not for_id:
                        continue

                    target = page.locator(f"#{for_id}")
                    tag = target.evaluate("el => el.tagName.toLowerCase()", timeout=2000)

                    if tag == "input":
                        answer = answer_question(question_text, payload.profile)
                        if answer:
                            target.fill(answer, timeout=2000)
                            answered.append(f"Q: {question_text[:60]} → A: {answer[:40]}")
                    elif tag == "select":
                        answer = answer_question(question_text, payload.profile)
                        if answer:
                            try:
                                target.select_option(label=answer, timeout=2000)
                                answered.append(f"Q: {question_text[:60]} → selected: {answer[:40]}")
                            except Exception:
                                pass
                    elif tag == "textarea":
                        answer = answer_question(question_text, payload.profile, long_form=True)
                        if answer:
                            target.fill(answer, timeout=2000)
                            answered.append(f"Q: {question_text[:60]} → A: {answer[:40]}")
                except Exception:
                    continue
        except Exception as e:
            _logger.warning("Custom question handling failed: %s", e)

        if answered:
            _logger.info("   🤖 Answered %d custom question(s).", len(answered))
            for a in answered:
                _logger.info("      %s", a)

        return answered
