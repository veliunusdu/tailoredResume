BLOCKLIST = [
    "senior", "lead", "manager", "director",
    "head of", "principal", "staff", "vp", "vice president",
]

def _normalize(raw: dict) -> dict:
    """Map raw API fields to a consistent internal shape."""
    source = raw.get("source_type", "remotive")
    
    if source == "remotive":
        pub_date = raw.get("publication_date")
        date_posted = str(pub_date)[:10] if pub_date else ""
        return {
            "title":       str(raw.get("title") or "Unknown Title"),
            "company":     str(raw.get("company_name") or "Unknown Company"),
            "location":    str(raw.get("candidate_required_location") or "Remote"),
            "url":         str(raw.get("url") or ""),
            "date_posted": date_posted,
            "salary":      str(raw.get("salary") or "Not listed"),
            "tags":        list(raw.get("tags") or []),
            "description": str(raw.get("description") or ""),
            "site":        "Remotive",
        }
    else:
        # JobSpy normalization or other sources
        # Fields: title, company, location, job_url, date_posted, salary_source, description, site
        return {
            "title":       str(raw.get("title") or "Unknown Title"),
            "company":     str(raw.get("company") or "Unknown Company"),
            "location":    str(raw.get("location") or "Remote"),
            "url":         str(raw.get("job_url") or raw.get("url") or ""),
            "date_posted": str(raw.get("date_posted") or ""),
            "salary":      str(raw.get("salary_source") or raw.get("salary") or "Not listed"),
            "tags":        list(raw.get("tags") or []),
            "description": str(raw.get("description") or ""),
            "site":        str(raw.get("site") or "Web").title(),
        }



from typing import Any
from app.search_config import get_search_config

def filter_jobs(jobs: list[dict], user_id: str, collector: Any = None) -> list[dict]:
    """
    Apply rule-based filtering + field normalization.
    No AI involved — pure keyword matching.
    """
    if not isinstance(jobs, list):
        return []

    cfg = get_search_config(user_id)
    blocklist = [t.lower() for t in cfg.get("exclude_titles", [])]
    queries = [q["query"].lower() for q in cfg.get("queries", [])]

    filtered = []
    for job in jobs:
        if not isinstance(job, dict):
            continue

        title = str(job.get("title") or "").lower()
        if not title:
            continue

        if blocklist and any(word in title for word in blocklist):
            continue

        norm_job = _normalize(job)
        if collector:
            collector.add_filtered(norm_job["site"], 1)
        filtered.append(norm_job)

    return filtered

