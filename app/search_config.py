"""
Per-user search configuration stored in SQLite.

Provides CRUD functions and a helper that converts the DB config
into the same format that the job-fetching pipeline expects.
"""
from __future__ import annotations

import json
import time

from app.db import get_connection
from app.logger import get_logger

_logger = get_logger(__name__)

# ── Default config ────────────────────────────────────────────────────────────

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

DEFAULT_BOARDS = ["indeed", "linkedin", "glassdoor"]

DEFAULT_EXCLUDE_TITLES = [
    "senior director", "VP ", "vice president", "chief",
]

DEFAULT_RESULTS_PER_SITE = 20
DEFAULT_HOURS_OLD = 72
DEFAULT_REQUIRE_HUMAN_CONFIRMATION = 1


# ── CRUD ──────────────────────────────────────────────────────────────────────

def get_search_config(user_id: str) -> dict:
    """Return the search config for this user. Returns defaults if none saved."""
    with get_connection(user_id) as conn:
        row = conn.execute(
            "SELECT * FROM user_search_config WHERE user_id = ?", (user_id,)
        ).fetchone()

    if row:
        res = dict(row)
        for key in ("queries", "locations", "boards", "exclude_titles", "seniority_levels",
                    "employment_types", "experience_levels", "target_countries",
                    "preferred_roles", "required_keywords", "excluded_keywords"):
            val = res.get(key)
            if isinstance(val, str):
                try:
                    res[key] = json.loads(val)
                except Exception:
                    pass
        
        # Ensure booleans/ints are properly cast if necessary
        for key in ("remote_only", "has_us_work_authorization", "requires_sponsorship", "student_status", "visa_sponsorship"):
            if key in res and res[key] is not None:
                res[key] = bool(res[key])
                
        return res

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
    """Upsert the search config for this user. Returns the saved config dict."""
    now = time.time()

    queries          = json.dumps(config.get("queries", DEFAULT_QUERIES))
    locations        = json.dumps(config.get("locations", DEFAULT_LOCATIONS))
    boards           = json.dumps(config.get("boards", DEFAULT_BOARDS))
    exclude_titles   = json.dumps(config.get("exclude_titles", DEFAULT_EXCLUDE_TITLES))
    seniority_levels = json.dumps(config.get("seniority_levels", []))
    profile_notes    = config.get("profile_notes", "")
    results_per_site = int(config.get("results_per_site", DEFAULT_RESULTS_PER_SITE))
    hours_old        = int(config.get("hours_old", DEFAULT_HOURS_OLD))
    require_human    = int(config.get("require_human_confirmation", DEFAULT_REQUIRE_HUMAN_CONFIRMATION))

    employment_types = json.dumps(config.get("employment_types", []))
    experience_levels = json.dumps(config.get("experience_levels", []))
    target_countries = json.dumps(config.get("target_countries", []))
    preferred_roles = json.dumps(config.get("preferred_roles", []))
    required_keywords = json.dumps(config.get("required_keywords", []))
    excluded_keywords = json.dumps(config.get("excluded_keywords", []))
    
    remote_only = int(config.get("remote_only") or 0)
    current_country = config.get("current_country", "")
    has_us_work_authorization = int(config.get("has_us_work_authorization") or 0)
    requires_sponsorship = int(config.get("requires_sponsorship") or 0)
    student_status = int(config.get("student_status") or 0)
    visa_sponsorship = int(config.get("visa_sponsorship") or 0)
    graduation_year = config.get("graduation_year")
    if graduation_year is not None:
        graduation_year = int(graduation_year)

    with get_connection(user_id) as conn:
        conn.execute("""
            INSERT INTO user_search_config
                (user_id, queries, locations, boards, exclude_titles, seniority_levels,
                 profile_notes, results_per_site, hours_old, require_human_confirmation,
                 employment_types, experience_levels, remote_only, target_countries,
                 current_country, has_us_work_authorization, requires_sponsorship,
                 student_status, graduation_year, preferred_roles, required_keywords,
                 excluded_keywords, visa_sponsorship, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                queries          = excluded.queries,
                locations        = excluded.locations,
                boards           = excluded.boards,
                exclude_titles   = excluded.exclude_titles,
                seniority_levels = excluded.seniority_levels,
                profile_notes    = excluded.profile_notes,
                results_per_site = excluded.results_per_site,
                hours_old        = excluded.hours_old,
                require_human_confirmation = excluded.require_human_confirmation,
                employment_types = excluded.employment_types,
                experience_levels = excluded.experience_levels,
                remote_only      = excluded.remote_only,
                target_countries = excluded.target_countries,
                current_country  = excluded.current_country,
                has_us_work_authorization = excluded.has_us_work_authorization,
                requires_sponsorship = excluded.requires_sponsorship,
                student_status   = excluded.student_status,
                graduation_year  = excluded.graduation_year,
                preferred_roles  = excluded.preferred_roles,
                required_keywords = excluded.required_keywords,
                excluded_keywords = excluded.excluded_keywords,
                visa_sponsorship = excluded.visa_sponsorship,
                updated_at       = excluded.updated_at
        """, (
            user_id, queries, locations, boards, exclude_titles, seniority_levels,
            profile_notes, results_per_site, hours_old, require_human,
            employment_types, experience_levels, remote_only, target_countries,
            current_country, has_us_work_authorization, requires_sponsorship,
            student_status, graduation_year, preferred_roles, required_keywords,
            excluded_keywords, visa_sponsorship, now,
        ))

    _logger.info("✅ Saved search config for user %s", user_id)
    return get_search_config(user_id)


def build_searches_for_user(user_id: str) -> list[dict]:
    """Convert the user's config into search-dict list for the job-fetching pipeline."""
    ctx = build_unified_context(user_id)
    cfg = get_search_config(user_id)
    # Triple the limit because we will filter aggressively later
    base_limit: int = cfg.get("results_per_site") or DEFAULT_RESULTS_PER_SITE
    limit = base_limit * 3

    base_roles = cfg.get("preferred_roles", [])
    if not base_roles:
        base_roles = ctx.queries if ctx.queries else [q["query"] for q in DEFAULT_QUERIES]

    employment_types = cfg.get("employment_types", [])
    experience_levels = cfg.get("experience_levels", [])
    
    modifiers = []
    for t in employment_types:
        # job boards do better with "part time" instead of "part-time"
        modifiers.append(t.replace("-", " "))
    for l in experience_levels:
        modifiers.append(l.replace("-", " "))
        
    focused_queries = []
    if not modifiers:
        focused_queries = base_roles
    else:
        for role in base_roles:
            for mod in modifiers:
                # e.g., "software engineer intern" or "backend developer part time"
                focused_queries.append(f"{role} {mod}".strip())
                
    # Deduplicate
    focused_queries = list(dict.fromkeys(focused_queries))

    locations = ctx.locations if ctx.locations else [l["location"] for l in DEFAULT_LOCATIONS]
    boards    = ctx.boards    if ctx.boards    else DEFAULT_BOARDS

    return [
        {"term": q, "location": loc, "limit": limit, "platforms": boards}
        for q in focused_queries
        for loc in locations
    ]


def get_scoring_profile(user_id: str) -> dict:
    """Build the dynamic scoring profile from search config + primary resume."""
    from app.services.resume import get_resumes, get_resume_by_id
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
        "exclude_titles":   cfg.get("exclude_titles", []),
        "locations":        loc_names,
        "profile_notes":    cfg.get("profile_notes", ""),
        "resume_summary":   resume_summary,
        "structured_data":  structured_data,
        "visa_sponsorship": cfg.get("visa_sponsorship", 0),
        "employment_types": cfg.get("employment_types", []),
        "has_us_work_authorization": cfg.get("has_us_work_authorization", 0),
        "requires_sponsorship": cfg.get("requires_sponsorship", 0),
        "student_status": cfg.get("student_status", 0),
        "target_countries": cfg.get("target_countries", []),
    }


def build_unified_context(user_id: str):
    """Merge user config + parsed resume into UnifiedSearchContext."""
    from app.services.resume import get_resumes, get_resume_by_id
    from app.schemas import UnifiedSearchContext

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

    queries = cfg.get("queries", [])
    query_names = [q["query"] for q in queries if isinstance(q, dict) and "query" in q]

    if not query_names and structured_data:
        role = structured_data.get("desired_role") or structured_data.get("role")
        if role:
            query_names = [role]

    return UnifiedSearchContext(
        user_id=user_id,
        resume_summary=resume_summary,
        structured_resume_data=structured_data,
        queries=query_names,
        locations=loc_names,
        is_remote=is_remote,
        boards=cfg.get("boards", []),
        exclude_titles=cfg.get("exclude_titles", []),
        seniority_levels=cfg.get("seniority_levels", []),
        profile_notes=cfg.get("profile_notes", ""),
    )
