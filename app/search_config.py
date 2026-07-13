"""
Per-user search configuration stored in PostgreSQL.

Replaces config/searches.yaml with a database-backed, per-user config.
Provides CRUD functions and a helper that converts the DB config
into the same format that the job-fetching pipeline expects.
"""
from __future__ import annotations

import time

import psycopg2.extras

from app.db import get_connection
from app.logger import get_logger

_logger = get_logger(__name__)

# ── Default config (used when user has no saved config) ───────────────────────

DEFAULT_QUERIES = [
    {"query": "software engineer", "tier": 1},
    {"query": "backend engineer", "tier": 1},
    {"query": "full stack developer", "tier": 1},
]

DEFAULT_LOCATIONS = [
    {"location": "Remote", "remote": True},
    {"location": "San Francisco, CA", "remote": False},
    {"location": "Bay Area, CA", "remote": False},
]

DEFAULT_BOARDS = [
    "indeed",
    "linkedin",
    "glassdoor",
]

DEFAULT_EXCLUDE_TITLES = [
    "senior director", "VP ", "vice president", "chief",
    "intern", "internship", "co-op",
]

DEFAULT_RESULTS_PER_SITE = 20
DEFAULT_HOURS_OLD = 72
DEFAULT_REQUIRE_HUMAN_CONFIRMATION = 1


# ── CRUD ──────────────────────────────────────────────────────────────────────

def get_search_config(user_id: str) -> dict:
    """
    Return the search config for this user.
    If no config is saved, returns the system defaults.
    """
    with get_connection(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT * FROM user_search_config WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()

    if row:
        res = dict(row)
        import json
        for key in ["queries", "locations", "boards", "exclude_titles"]:
            if isinstance(res.get(key), str):
                try:
                    res[key] = json.loads(res[key])
                except Exception:
                    pass
        return res

    # Return defaults (don't save them — let the user explicitly save)
    return {
        "user_id": user_id,
        "queries": DEFAULT_QUERIES,
        "locations": DEFAULT_LOCATIONS,
        "boards": DEFAULT_BOARDS,
        "exclude_titles": DEFAULT_EXCLUDE_TITLES,
        "seniority_levels": [],
        "profile_notes": "",
        "results_per_site": DEFAULT_RESULTS_PER_SITE,
        "hours_old": DEFAULT_HOURS_OLD,
        "require_human_confirmation": DEFAULT_REQUIRE_HUMAN_CONFIRMATION,
        "updated_at": None,
    }


def save_search_config(user_id: str, config: dict) -> dict:
    """
    Upsert the search config for this user.
    Returns the saved config dict.
    """
    import json

    now = time.time()

    queries = json.dumps(config.get("queries", DEFAULT_QUERIES))
    locations = json.dumps(config.get("locations", DEFAULT_LOCATIONS))
    boards = json.dumps(config.get("boards", DEFAULT_BOARDS))
    exclude_titles = json.dumps(config.get("exclude_titles", DEFAULT_EXCLUDE_TITLES))
    seniority_levels = json.dumps(config.get("seniority_levels", []))
    profile_notes = config.get("profile_notes", "")
    results_per_site = int(config.get("results_per_site", DEFAULT_RESULTS_PER_SITE))
    hours_old = int(config.get("hours_old", DEFAULT_HOURS_OLD))
    require_human_confirmation = int(config.get("require_human_confirmation", DEFAULT_REQUIRE_HUMAN_CONFIRMATION))

    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO user_search_config
                    (user_id, queries, locations, boards, exclude_titles, seniority_levels, profile_notes,
                     results_per_site, hours_old, require_human_confirmation, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    queries          = EXCLUDED.queries,
                    locations        = EXCLUDED.locations,
                    boards           = EXCLUDED.boards,
                    exclude_titles   = EXCLUDED.exclude_titles,
                    seniority_levels = EXCLUDED.seniority_levels,
                    profile_notes    = EXCLUDED.profile_notes,
                    results_per_site = EXCLUDED.results_per_site,
                    hours_old        = EXCLUDED.hours_old,
                    require_human_confirmation = EXCLUDED.require_human_confirmation,
                    updated_at       = EXCLUDED.updated_at
            """, (
                user_id, queries, locations, boards, exclude_titles, seniority_levels, profile_notes,
                results_per_site, hours_old, require_human_confirmation, now,
            ))

    _logger.info("✅ Saved search config for user %s", user_id)
    return get_search_config(user_id)


def build_searches_for_user(user_id: str) -> list[dict]:
    """
    Convert the user's search config into the list-of-search-dicts format
    expected by the job-fetching pipeline (same shape as the old searches.yaml).
    """
    cfg = get_search_config(user_id)

    queries: list[dict] = cfg.get("queries") or DEFAULT_QUERIES
    locations: list[dict] = cfg.get("locations") or DEFAULT_LOCATIONS
    boards: list[str] = cfg.get("boards") or DEFAULT_BOARDS
    limit: int = cfg.get("results_per_site") or DEFAULT_RESULTS_PER_SITE

    searches = []
    for q in queries:
        for loc in locations:
            searches.append({
                "term": q["query"],
                "location": loc["location"],
                "limit": limit,
                "platforms": boards,
            })

    return searches


def get_scoring_profile(user_id: str) -> dict:
    """
    Builds the dynamic scoring profile by combining the user's search config
    with an excerpt from their primary resume.
    """
    from app.resumes import get_resumes, get_resume_by_id
    cfg = get_search_config(user_id)
    
    resume_summary = "No resume uploaded."
    structured_data = None
    
    resumes = get_resumes(user_id)
    if resumes:
        first_resume = get_resume_by_id(resumes[0]["id"], user_id)
        if first_resume:
            if first_resume.get("structured_data"):
                structured_data = first_resume["structured_data"]
            if first_resume.get("content"):
                resume_summary = first_resume["content"][:1500]

    locations = cfg.get("locations", [])
    loc_names = [loc["location"] for loc in locations if isinstance(loc, dict) and "location" in loc]
    is_remote = any(loc.get("remote", False) for loc in locations if isinstance(loc, dict))
    if is_remote and "Remote" not in loc_names:
        loc_names.append("Remote")

    return {
        "seniority_levels": cfg.get("seniority_levels", []),
        "exclude_titles": cfg.get("exclude_titles", []),
        "locations": loc_names,
        "profile_notes": cfg.get("profile_notes", ""),
        "resume_summary": resume_summary,
        "structured_data": structured_data
    }
