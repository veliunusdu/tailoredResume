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

def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    """
    Deduplicate jobs by normalized company, title, and location.
    If duplicates exist, keep the one with the longest description.
    """
    seen = {}
    for job in jobs:
        # Normalize strings for grouping
        c = str(job.get("company", "")).strip().lower()
        t = str(job.get("title", "")).strip().lower()
        l = str(job.get("location", "")).strip().lower()
        
        # Remove common noisy suffixes from titles (e.g. " - Remote", " (M/F)")
        t = t.split(" - ")[0].split(" (")[0].strip()
        
        key = (c, t, l)
        
        if key not in seen:
            seen[key] = job
        else:
            # Keep the job with the longest description
            existing_desc = len(str(seen[key].get("description", "")))
            new_desc = len(str(job.get("description", "")))
            if new_desc > existing_desc:
                seen[key] = job
                
    return list(seen.values())

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
        
        # Quality Filters: Drop jobs with empty or very short descriptions
        desc = norm_job.get("description", "").strip()
        if len(desc) < 200:
            continue
            
        filtered.append(norm_job)

    # Aggressive deduplication
    final_jobs = deduplicate_jobs(filtered)
    
    if collector:
        for j in final_jobs:
            collector.add_filtered(j["site"], 1)

    return final_jobs

