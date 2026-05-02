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
        field_map = {
            "first_name": ["first_name", "firstName", "first-name", "given-name"],
            "last_name":  ["last_name", "lastName", "last-name", "family-name"],
            "email":      ["email", "email_address", "emailAddress"],
            "phone":      ["phone", "mobile", "tel", "phoneNumber"],
            "city":       ["city", "location", "address-level2"],
        }
        
        for field, keywords in field_map.items():
            val = profile.get(field)
            if not val: continue
            
            for kw in keywords:
                try:
                    selector = f"input[name*='{kw}'], input[id*='{kw}'], input[aria-label*='{kw}']"
                    element = page.locator(selector).first
                    if element.count() > 0 and element.is_visible() and not element.input_value():
                        element.fill(str(val), timeout=2000)
                        break
                except Exception:
                    continue

    def solve_tricky_field(self, page, profile: Dict[str, Any]) -> bool:
        """
        Scans for visible inputs that are empty and tries to solve them using Claude.
        Returns True if at least one field was solved.
        """
        from app.strategies.qa import answer_question, select_best_option, is_claude_available
        if not is_claude_available():
            return False

        solved_any = False
        
        # 1. Handle text inputs and textareas
        text_inputs = page.locator("input[type='text'], textarea, input:not([type])").all()
        for element in text_inputs:
            try:
                if not element.is_visible() or element.input_value():
                    continue
                
                # Try to find a label
                label_text = self._get_label_for_element(page, element)
                if not label_text: continue
                
                answer = answer_question(label_text, profile)
                if answer and answer != "CANNOT_ANSWER":
                    element.fill(answer)
                    solved_any = True
                    page.wait_for_timeout(500)
            except Exception:
                continue

        # 2. Handle dropdowns (select)
        selects = page.locator("select").all()
        for element in selects:
            try:
                if not element.is_visible() or element.input_value():
                    continue
                    
                label_text = self._get_label_for_element(page, element)
                if not label_text: continue
                
                # Get all non-empty options
                options = element.locator("option").all_inner_texts()
                options = [o.strip() for o in options if o.strip()]
                
                selection = select_best_option(label_text, options, profile)
                if selection:
                    element.select_option(label=selection)
                    solved_any = True
                    page.wait_for_timeout(500)
            except Exception:
                continue

        return solved_any

    def _get_label_for_element(self, page, element) -> str | None:
        """Heuristic to find the label text for an input element."""
        try:
            # 1. Try 'id' -> 'for'
            element_id = element.get_attribute("id")
            if element_id:
                label = page.locator(f"label[for='{element_id}']").first
                if label.count() > 0:
                    return label.inner_text().strip()
            
            # 2. Try parent container text
            parent = element.locator("xpath=..")
            parent_text = parent.inner_text().strip()
            # If parent text is too long, it might be the whole form. Clean it up.
            if 1 < len(parent_text) < 200:
                return parent_text.split('\n')[0]
                
            # 3. Try aria-label
            aria = element.get_attribute("aria-label")
            if aria: return aria.strip()
            
            # 4. Try placeholder
            placeholder = element.get_attribute("placeholder")
            if placeholder: return placeholder.strip()
            
        except Exception:
            pass
        return None
