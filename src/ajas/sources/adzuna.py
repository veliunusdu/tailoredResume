"""
Adzuna Job Source Fetcher.
"""
import httpx
from typing import List, Dict, Any
from ajas.config import settings
from ajas.logger import log


def fetch_adzuna(query: str, location: str = "us", country: str = "us") -> List[Dict[str, Any]]:
    """
    Fetch jobs from Adzuna API.
    Returns normalized job dicts for the discovery pipeline.
    """
    if not settings.adzuna_app_id or not settings.adzuna_app_key:
        log.warning("Adzuna API credentials missing. Skipping Adzuna.")
        return []

    url = f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
    params = {
        "app_id": settings.adzuna_app_id,
        "app_key": settings.adzuna_app_key,
        "what": query,
        "where": location,
        "content-type": "application/json",
        "results_per_page": 20
    }

    try:
        response = httpx.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        
        results = []
        for job in data.get("results", []):
            results.append({
                "source": "adzuna",
                "source_id": str(job.get("id")),
                "title": job.get("title", ""),
                "company": job.get("company", {}).get("display_name", ""),
                "description": job.get("description", ""),
                "url": job.get("redirect_url", ""),
                "location": job.get("location", {}).get("display_name", ""),
                "raw_data": job
            })
        return results
    except Exception as e:
        log.error(f"Adzuna fetch failed: {e}")
        return []
