"""
Fast, DOM-free job extraction routing via hidden APIs and JSON-LD structured data.
"""
import json
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from pydantic import BaseModel
from app.logger import get_logger

_logger = get_logger(__name__)

# ── Phase 1: Define the Universal Contract ────────────────────────────────────

class JobListing(BaseModel):
    title: str
    company: str
    description: str
    requirements: list[str] = []
    platform: str
    raw_url: str


# ── Phase 3: Implement Greenhouse (The Easy Win) ──────────────────────────────

def extract_greenhouse(url: str) -> JobListing | None:
    """Extract job data from Greenhouse using Schema.org JSON-LD."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        # BeautifulSoup is extremely fast for finding a single script tag
        soup = BeautifulSoup(response.text, "html.parser")
        script_tag = soup.find("script", type="application/ld+json")
        
        if not script_tag:
            _logger.warning("No JSON-LD found for Greenhouse job: %s", url)
            return None
            
        data = json.loads(script_tag.string)
        
        return JobListing(
            title=data.get("title", "Unknown Title"),
            company=data.get("hiringOrganization", {}).get("name", "Unknown Company"),
            description=data.get("description", ""),
            platform="greenhouse",
            raw_url=url
        )
    except Exception as e:
        _logger.error("Failed to extract Greenhouse job: %s", e)
        return None


# ── Phase 4: Implement Lever & Ashby (Placeholders) ───────────────────────────

def extract_lever(url: str) -> JobListing | None:
    """Extract job data from Lever using their JSON payload."""
    # Implementation hint: You can often fetch https://api.lever.co/v0/postings/{company}/{job_id}
    _logger.info("Lever extraction would run here for: %s", url)
    return None

def extract_ashby(url: str) -> JobListing | None:
    """Extract job data from Ashby using their GraphQL API."""
    # Implementation hint: Replicate the GraphQL POST request found in the network tab
    _logger.info("Ashby extraction would run here for: %s", url)
    return None


# ── Phase 2: Build the Router ─────────────────────────────────────────────────

def extract_job(url: str) -> JobListing | None:
    """Inspect the URL and route it to the correct extraction module."""
    domain = urlparse(url).netloc.lower()
    
    if "greenhouse.io" in domain:
        return extract_greenhouse(url)
    elif "lever.co" in domain:
        return extract_lever(url)
    elif "ashbyhq.com" in domain:
        return extract_ashby(url)
        
    # Fallback to a smart extractor or return None
    _logger.warning("No specific extractor for domain: %s. Requires fallback.", domain)
    return None