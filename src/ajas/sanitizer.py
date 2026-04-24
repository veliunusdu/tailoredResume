import re

PII_PATTERNS = {
    "[[EMAIL]]": r"[\w.+-]+@[\w-]+\.[\w.]+",
    "[[PHONE]]": r"\+?[\d][\d\s().-]{7,}[\d]",
    "[[LINKEDIN]]": r"linkedin\.com/in/[\w-]+",
    "[[STREET_ADDRESS]]": r"\d+\s+[a-zA-Z0-9\s,]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Way|Plaza|Plz)\.?",
}


def sanitise(text: str) -> str:
    """Strip PII from text using named placeholders."""
    if not text:
        return ""
    for placeholder, pat in PII_PATTERNS.items():
        text = re.sub(pat, placeholder, text)
    return text


def inject_pii(text: str, pii_data: dict[str, str]) -> str:
    """Inject PII back into text from a dictionary."""
    if not text:
        return ""
    for placeholder, value in pii_data.items():
        text = text.replace(placeholder, value)
    return text
