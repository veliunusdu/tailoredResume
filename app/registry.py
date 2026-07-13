"""
Source registry that governs job board routing, capabilities, and fallback logic.
"""

from typing import Dict, Any

class SourceRegistry:
    # Map of all recognized boards to their fetch configuration
    SOURCES = {
        "weworkremotely": {
            "name": "We Work Remotely",
            "type": "direct",
            "status": "stable",
            "fallback": "google_fallback",
            "fallback_query": "site:weworkremotely.com/remote-jobs",
        },
        "wwr": {
            # Alias for weworkremotely
            "name": "We Work Remotely",
            "type": "direct",
            "status": "stable",
            "fallback": "google_fallback",
            "fallback_query": "site:weworkremotely.com/remote-jobs",
        },
        "builtin": {
            "name": "Built In",
            "type": "direct",
            "status": "stable",
            "fallback": "google_fallback",
            "fallback_query": "site:builtin.com/jobs",
        },
        "remotive": {
            "name": "Remotive",
            "type": "direct",
            "status": "stable",
            "fallback": None,
        },
        "jsearch": {
            "name": "JSearch",
            "type": "direct",
            "status": "stable",
            "fallback": None,
        },
        "kariyer": {
            "name": "Kariyer.net",
            "type": "direct",
            "status": "stable",
            "fallback": None,
        },
        "techcareer": {
            "name": "Techcareer.net",
            "type": "direct",
            "status": "stable",
            "fallback": None,
        },
        # JobSpy-routed sources
        "linkedin": {
            "name": "LinkedIn",
            "type": "jobspy",
            "status": "stable",
            "fallback": "google_fallback",
            "fallback_query": "site:linkedin.com/jobs",
        },
        "indeed": {
            "name": "Indeed",
            "type": "jobspy",
            "status": "stable",
            "fallback": "google_fallback",
            "fallback_query": "site:indeed.com/jobs",
        },
        "glassdoor": {
            "name": "Glassdoor",
            "type": "jobspy",
            "status": "fragile",
            "fallback": "google_fallback",
            "fallback_query": "site:glassdoor.com/Job",
        },
        "zip_recruiter": {
            "name": "ZipRecruiter",
            "type": "jobspy",
            "status": "stable",
            "fallback": "google_fallback",
            "fallback_query": "site:ziprecruiter.com/jobs",
        },
        "google": {
            "name": "Google",
            "type": "jobspy",
            "status": "stable",
            "fallback": None,
        },
        # Fallback-only / conditional sources
        "wellfound": {
            "name": "Wellfound",
            "type": "google_fallback",
            "status": "conditional",
            "fallback_query": "site:wellfound.com/jobs",
        },
        "flexjobs": {
            "name": "FlexJobs",
            "type": "google_fallback",
            "status": "conditional",
            "fallback_query": "site:flexjobs.com/jobs",
        },
        "dice": {
            "name": "Dice",
            "type": "google_fallback",
            "status": "conditional",
            "fallback_query": "site:dice.com/jobs",
        },
    }

    @classmethod
    def get_source(cls, board: str) -> Dict[str, Any] | None:
        """Get the configuration for a specific board."""
        return cls.SOURCES.get(board.lower())

    @classmethod
    def get_route(cls, board: str, has_stable_access: bool = False) -> str:
        """
        Determine the fetch path: 'direct', 'jobspy', or 'google_fallback'.
        For unknown sources, defaults to 'jobspy'.
        """
        src = cls.get_source(board)
        if not src:
            return "jobspy"

        status = src.get("status")
        src_type = src.get("type")

        # Route conditional sources to fallback if we lack stable access
        if status == "conditional" and not has_stable_access:
            return "google_fallback"

        return src_type

    @classmethod
    def get_fallback_query(cls, board: str) -> str | None:
        """Get the fallback site query if defined."""
        src = cls.get_source(board)
        return src.get("fallback_query") if src else None
