from datetime import datetime
from typing import Any, Dict, List

import requests

GREENHOUSE_BOARDS_API = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"


def fetch_greenhouse(company: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch jobs from Greenhouse public Boards API for a specific company slug.

    Example company slug: 'cymertek' -> https://boards-api.greenhouse.io/v1/boards/cymertek/jobs
    Returns a list of normalized job dicts. On any network error returns an empty list.
    """
    if not company:
        return []
    url = GREENHOUSE_BOARDS_API.format(company=company)
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
    except requests.RequestException:
        return []

    # Normalize different possible response shapes
    if isinstance(data, dict) and "jobs" in data:
        jobs = data.get("jobs") or []
    elif isinstance(data, list):
        jobs = data
    else:
        jobs = []

    out: List[Dict[str, Any]] = []
    for j in jobs[:limit]:
        # location handling
        location = ""
        if j.get("location"):
            loc = j.get("location")
            if isinstance(loc, dict):
                location = loc.get("name", "")
            else:
                location = str(loc)
        else:
            locs = j.get("locations") or []
            if isinstance(locs, list) and locs:
                first = locs[0]
                if isinstance(first, dict):
                    location = first.get("name", "")
                else:
                    location = str(first)

        description = (
            j.get("content") or j.get("description") or j.get("internal_job") or ""
        )
        out.append(
            {
                "source": "greenhouse",
                "source_id": j.get("id"),
                "title": j.get("title"),
                "company": company,
                "location": location,
                "description": description,
                "url": j.get("absolute_url") or j.get("url"),
                "posted_at": j.get("created_at")
                or j.get("updated_at")
                or datetime.utcnow().isoformat(),
                "raw": j,
            }
        )
    return out
