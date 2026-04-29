from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

@dataclass
class ApplyPayload:
    job_url: str
    profile: Dict[str, Any]
    resume_path: str
    cover_letter: Optional[str] = None
    platform_data: Optional[Dict[str, Any]] = None

@dataclass
class ApplyResult:
    success: bool
    status: str  # success, failed, manual_required
    platform: str
    error_msg: Optional[str] = None
    screenshot_path: Optional[str] = None

class ApplyStrategy(ABC):
    @abstractmethod
    def apply(self, page, payload: ApplyPayload, dry_run: bool = True) -> ApplyResult:
        pass

    def fill_fields(self, page, profile: Dict[str, Any]):
        """Common field filling logic based on heuristic selectors."""
        # This will be used by adapters to fill basic info
        field_map = {
            "first_name": ["first_name", "firstName", "first-name"],
            "last_name":  ["last_name", "lastName", "last-name"],
            "email":      ["email", "email_address"],
            "phone":      ["phone", "mobile", "tel"],
            "location":   ["location", "address", "city"],
        }
        # Heuristic implementation...
        pass
