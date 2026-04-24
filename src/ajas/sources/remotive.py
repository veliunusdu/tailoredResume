from datetime import datetime
from typing import Any, Dict, List

import requests

REMOTIVE_BASE = "https://remotive.io/api/remote-jobs"


def fetch_remotive(query: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch jobs from Remotive. No API key required.

    Returns a list of normalized job dicts.
    """
    params = {"search": query} if query else {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        r = requests.get(REMOTIVE_BASE, params=params, headers=headers, timeout=15)
        print(f"DEBUG Remotive: Status {r.status_code} for {r.url}")
        r.raise_for_status()
        data = r.json().get("jobs", [])
    except requests.RequestException:
        # transient failure or remote blocking; return empty list and let caller continue
        return []
    out: List[Dict[str, Any]] = []
    for j in data[:limit]:
        out.append(
            {
                "source": "remotive",
                "source_id": j.get("id"),
                "title": j.get("title"),
                "company": j.get("company_name"),
                "location": j.get("candidate_required_location"),
                "description": j.get("description"),
                "url": j.get("url"),
                "posted_at": j.get("publication_date") or datetime.utcnow().isoformat(),
                "raw": j,
            }
        )
    return out
