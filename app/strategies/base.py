"""Abstract base class for all ATS apply strategies."""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ApplyPayload:
    job_id: str
    job_url: str
    apply_url: str
    job_board: str
    profile: dict
    resume_path: Path | None = None
    cover_letter: str | None = None
    session_state: dict | None = None


@dataclass
class ApplyResult:
    success: bool
    status: str                  # 'success' | 'failed' | 'manual_required'
    job_board: str = ""
    screenshot: str | None = None
    error_msg: str | None = None
    answered_questions: list[str] = field(default_factory=list)


class ApplyStrategy(ABC):
    """Base class every board adapter must implement."""

    @abstractmethod
    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        ...

    def fill_fields(self, page, profile: dict) -> None:
        """
        Generic visible-input filler using name/placeholder/aria-label heuristics.
        Strategies can call this as a first pass, then handle board-specific fields.
        """
        field_map = {
            ("first", "given"):                   profile.get("first_name", ""),
            ("last", "family", "surname"):         profile.get("last_name", ""),
            ("email",):                            profile.get("email", ""),
            ("phone", "mobile", "tel"):            profile.get("phone", ""),
            ("linkedin",):                         profile.get("linkedin", ""),
            ("github",):                           profile.get("github", ""),
            ("portfolio", "website", "personal"):  profile.get("portfolio", ""),
            ("location", "city", "address"):       profile.get("location", ""),
        }

        try:
            inputs = page.locator("input:visible").all()
        except Exception:
            return

        for inp in inputs:
            try:
                attr_name  = (inp.get_attribute("name")        or "").lower()
                attr_ph    = (inp.get_attribute("placeholder") or "").lower()
                attr_label = (inp.get_attribute("aria-label")  or "").lower()
                combined   = f"{attr_name} {attr_ph} {attr_label}"

                for keywords, value in field_map.items():
                    if value and any(kw in combined for kw in keywords):
                        inp.fill(value, timeout=3000)
                        break
            except Exception:
                continue

    def upload_resume(self, page, resume_path: Path) -> bool:
        """Attempt to upload the resume file. Returns True on success."""
        if not resume_path or not resume_path.exists():
            return False
        try:
            file_input = page.locator("input[type='file']").first
            file_input.set_input_files(str(resume_path.absolute()), timeout=5000)
            return True
        except Exception:
            return False
