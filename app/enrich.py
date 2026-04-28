"""Job Description Enrichment Module."""

import json
import requests
from bs4 import BeautifulSoup

from app.logger import get_logger
from app.config import HTTP_TIMEOUT_SEC
from app.utils import retry

_logger = get_logger(__name__)

# CSS Selectors commonly used for job descriptions
COMMON_SELECTORS = [
    ".job-description",
    "#job-description",
    ".job-details",
    "[data-test='job-description']",
    ".description",
    ".posting-requirements",
    ".show-more-less-html__markup",  # LinkedIn
    "#jobDescriptionText",           # Indeed
    ".desc",
]


@retry(
    max_attempts=2,
    initial_delay_sec=1.0,
    backoff_factor=2.0,
    logger=_logger,
)
def fetch_html(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_SEC)
    resp.raise_for_status()
    return resp.text


def extract_json_ld(soup: BeautifulSoup) -> str | None:
    """Tier 1: Extract description from schema.org JobPosting."""
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "JobPosting":
                desc = data.get("description")
                if desc:
                    return BeautifulSoup(desc, "html.parser").get_text(separator="\n", strip=True)
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and item.get("@type") == "JobPosting":
                        desc = item.get("description")
                        if desc:
                            return BeautifulSoup(desc, "html.parser").get_text(separator="\n", strip=True)
        except Exception:
            continue
    return None


def extract_css_selectors(soup: BeautifulSoup) -> str | None:
    """Tier 2: Extract description using common CSS selectors."""
    for selector in COMMON_SELECTORS:
        element = soup.select_one(selector)
        if element:
            text = element.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text
    return None


def extract_body_fallback(soup: BeautifulSoup) -> str | None:
    """Tier 3: Fallback to raw body text."""
    # Remove non-content elements
    for element in soup(["script", "style", "nav", "footer", "header", "aside"]):
        element.decompose()
        
    text = soup.get_text(separator="\n", strip=True)
    if len(text) > 200:
        return text
    return None


def enrich_description(url: str) -> str | None:
    """Attempt to extract the full job description from the given URL."""
    if not url or not url.startswith("http"):
        return None
        
    try:
        html = fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")
        
        # Tier 1: JSON-LD (Most reliable)
        desc = extract_json_ld(soup)
        if desc and len(desc) > 200:
            _logger.debug("Enriched via JSON-LD: %s", url)
            return desc
            
        # Tier 2: CSS Selectors
        desc = extract_css_selectors(soup)
        if desc and len(desc) > 200:
            _logger.debug("Enriched via CSS: %s", url)
            return desc
            
        # Tier 3: Body Fallback
        desc = extract_body_fallback(soup)
        if desc and len(desc) > 200:
            _logger.debug("Enriched via Body Fallback: %s", url)
            return desc
            
    except Exception as e:
        _logger.warning("Enrichment failed for %s: %s", url, e)
        
    return None
