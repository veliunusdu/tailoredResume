from datetime import datetime
from typing import Any, Dict, List

import requests

LEVER_API_COMPANY = "https://api.lever.co/v0/postings/{company}"


def fetch_lever(company: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch jobs from Lever public postings API for a specific company slug.

    Example: https://api.lever.co/v0/postings/<company>
    Returns normalized job dicts; returns [] on network errors.
    """
    if not company:
        return []
    url = LEVER_API_COMPANY.format(company=company)
    try:
        r = requests.get(url, params={"limit": limit}, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return []

    # Lever returns a list of postings
    jobs = data if isinstance(data, list) else []
    out: List[Dict[str, Any]] = []
    for p in jobs[:limit]:
        categories = p.get("categories") or {}
        title = p.get("text") or p.get("title") or p.get("role") or p.get("name")
        description = p.get("description") or p.get("text") or ""
        location = categories.get("location") or p.get("location") or ""
        url = p.get("applyUrl") or p.get("hostedUrl") or p.get("url")
        out.append(
            {
                "source": "lever",
                "source_id": p.get("id"),
                "title": title,
                "company": company,
                "location": location,
                "description": description,
                "url": url,
                "posted_at": p.get("createdAt")
                or p.get("date")
                or datetime.utcnow().isoformat(),
                "raw": p,
            }
        )
    return out
