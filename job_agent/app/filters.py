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
    return {
        "title":       raw.get("title"),
        "company":     raw.get("company_name"),
        "location":    raw.get("candidate_required_location") or "Remote",
        "url":         raw.get("url"),
        "date_posted": (raw.get("publication_date") or "")[:10],
        "salary":      raw.get("salary") or "Not listed",
        "tags":        raw.get("tags") or [],
        "description": raw.get("description") or "",
    }


def filter_jobs(jobs: list[dict]) -> list[dict]:
    """
    Apply rule-based filtering + field normalization.
    No AI involved — pure keyword matching.
    """
    filtered = []
    for job in jobs:
        title = (job.get("title") or "").lower()

        if any(word in title for word in BLOCKLIST):
            continue

        tags    = " ".join(job.get("tags") or []).lower()
        combined = title + " " + tags
        if not any(word in combined for word in ALLOWLIST):
            continue

        filtered.append(_normalize(job))

    return filtered
