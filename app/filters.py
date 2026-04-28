BLOCKLIST = [
    "senior", "lead", "manager", "director",
    "head of", "principal", "staff", "vp", "vice president",
]

ALLOWLIST = [
    "python", "backend", "fullstack", "flask", "django",
    "fastapi", "data", "ml", "ai", "intern",
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
        # JobSpy normalization
        # Fields: title, company, location, job_url, date_posted, salary_source, description, site
        return {
            "title":       str(raw.get("title") or "Unknown Title"),
            "company":     str(raw.get("company") or "Unknown Company"),
            "location":    str(raw.get("location") or "Remote"),
            "url":         str(raw.get("job_url") or ""),
            "date_posted": str(raw.get("date_posted") or ""),
            "salary":      str(raw.get("salary_source") or "Not listed"),
            "tags":        [], # Jobspy doesn't provide consistent tags
            "description": str(raw.get("description") or ""),
            "site":        str(raw.get("site") or "Web").title(),
        }


def filter_jobs(jobs: list[dict]) -> list[dict]:
    """
    Apply rule-based filtering + field normalization.
    No AI involved — pure keyword matching.
    """
    if not isinstance(jobs, list):
        return []

    filtered = []
    for job in jobs:
        if not isinstance(job, dict):
            continue

        title = str(job.get("title") or "").lower()

        if any(word in title for word in BLOCKLIST):
            continue

        tags_list = job.get("tags") or []
        tags_str = " ".join(str(t) for t in tags_list).lower()
        
        combined = title + " " + tags_str
        if not any(word in combined for word in ALLOWLIST):
            continue

        filtered.append(_normalize(job))

    return filtered
