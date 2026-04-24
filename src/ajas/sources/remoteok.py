from datetime import datetime
from typing import Any, Dict, List

import requests

REMOTEOK_BASE = "https://remoteok.com/api"


def fetch_remoteok(tag: str = "", limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch jobs from RemoteOK. No API key; first element in response is metadata."""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"}
    try:
        r = requests.get(REMOTEOK_BASE, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        from ajas.logger import log
        log.warning(f"RemoteOK fetch failed: {e}")
        return []

    jobs = data[1:] if len(data) > 1 else []
    out: List[Dict[str, Any]] = []

    search_terms = tag.lower().split() if tag else []

    for j in jobs:
        # Match logic: if tag is provided, check if ANY word in tag matches position, tags or description
        text_to_search = (
            (j.get("position") or "") + " " + 
            " ".join(j.get("tags") or []) + " " + 
            (j.get("description") or "")
        ).lower()

        if search_terms:
            # Check if all search terms appear in the text (AND logic)
            if not all(term in text_to_search for term in search_terms):
                continue

        out.append({

                "source": "remoteok",
                "source_id": j.get("id") or j.get("slug"),
                "title": j.get("position") or j.get("title"),
                "company": j.get("company"),
                "location": j.get("location", "Remote"),
                "description": j.get("description"),
                "url": j.get("url") or j.get("redirect_url"),
                "posted_at": j.get("date") or datetime.utcnow().isoformat(),
                "raw": j,
            }
        )
        if len(out) >= limit:
            break
    return out
