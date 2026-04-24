"""
Central job discovery coordinator.
Integrates multiple sources, handles normalization, and deduplicates.
"""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from ajas.database import Database
from ajas.logger import log
from ajas.sources.adzuna import fetch_adzuna
from ajas.sources.dice import fetch_dice
from ajas.sources.greenhouse import fetch_greenhouse
from ajas.sources.lever import fetch_lever
from ajas.sources.remoteok import fetch_remoteok
from ajas.sources.remotive import fetch_remotive
from ajas.sources.wellfound import fetch_wellfound


def search_jobs(query: str, location: str = "us", country: str = "us") -> List[Dict[str, Any]]:
    """
    Search for jobs using the Adzuna API (Legacy compatibility).
    Returns a list of job dicts: {title, company, description, url, location, id}.
    """
    results = fetch_adzuna(query, location, country)
    # Ensure ID key is present for app.py
    for r in results:
        r["id"] = r.get("source_id", "")
    return results



def discover_new_jobs(config_path: str = "data/sources.yaml"):
    """
    Coordinator: iterates through configured sources and queries,
    fetches results, normalizes, and stores new items in DB.
    """
    if not Path(config_path).exists():
        log.warning(f"Source config not found: {config_path}")
        return

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    db = Database()
    sources = config.get("sources", [])

    total_discovered = 0
    total_new = 0

    for src_cfg in sources:
        name = src_cfg.get("name")
        if not src_cfg.get("enabled", True):
            continue

        log.info(f"Processing source: {name}")
        queries = src_cfg.get("queries", [])

        for query in queries:
            results = []
            if name == "adzuna":
                results = fetch_adzuna(query)
            elif name == "remotive":
                # query can be a simple string or a dict with 'q'
                q = query if isinstance(query, str) else query.get("q", "")
                results = fetch_remotive(q)
            elif name == "remoteok":
                # support tag-based queries (query can be {'tag': 'python'})
                if isinstance(query, dict):
                    tag = query.get("tag") or query.get("q") or ""
                else:
                    tag = query
                results = fetch_remoteok(tag)
            elif name == "greenhouse":
                # query is expected to be a company slug or dict {'company': '<slug>'}
                company = (
                    query
                    if isinstance(query, str)
                    else query.get("company") or query.get("q") or ""
                )
                results = fetch_greenhouse(company)
            elif name == "lever":
                company = (
                    query
                    if isinstance(query, str)
                    else query.get("company") or query.get("q") or ""
                )
                results = fetch_lever(company)
            elif name == "wellfound":
                # disabled by default; set 'allow_scrape' in source config to True to enable
                allow_scrape = bool(src_cfg.get("allow_scrape", False))
                q = (
                    query
                    if isinstance(query, str)
                    else query.get("q") or query.get("company") or ""
                )
                results = fetch_wellfound(q, allow_scrape=allow_scrape)
            elif name == "dice":
                allow_scrape = bool(src_cfg.get("allow_scrape", False))
                q = query if isinstance(query, str) else query.get("q") or ""
                results = fetch_dice(q, allow_scrape=allow_scrape)

            total_discovered += len(results)

            for job in results:
                # 1. Normalize
                # Ensure fields are strings for fingerprinting and storage
                job["company"] = str(job.get("company") or "Unknown")
                job["title"] = str(job.get("title") or "Untitled")
                job["location"] = str(job.get("location") or "Remote")
                job["description"] = str(job.get("description") or "")

                # 2. Fingerprint
                fp = db.get_job_fingerprint(
                    job["company"], job["title"], job["location"]
                )
                job["fingerprint"] = fp

                # 3. Store (Database handles deduplication)
                is_new = db.add_discovered_job(job)
                if is_new:
                    total_new += 1

    log.info(
        f"Discovery cycle complete: {total_discovered} items seen, {total_new} new jobs added."
    )
    return total_new


def get_discovery_config(config_path: str = "data/sources.yaml") -> Dict[str, Any]:
    """Helper to read discovery config."""
    if not Path(config_path).exists():
        return {"sources": []}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def query_jobs(
    queries: List[str], sources: List[str] = None, limit_per_source: int = 20
) -> List[Dict[str, Any]]:
    """
    Search multiple queries across multiple sources and return a deduped list of results.
    Useful for "Find jobs matching my CV".
    """
    db = Database()
    all_results = []
    seen_fingerprints = set()

    # Use only enabled sources from config if not provided
    config = get_discovery_config()
    source_names = sources or [
        s["name"] for s in config.get("sources", []) if s.get("enabled", True)
    ]

    for name in source_names:
        log.info(f"Querying source: {name}")
        for q in queries:
            results = []
            if name == "adzuna":
                results = fetch_adzuna(q)
            elif name == "remotive":
                results = fetch_remotive(q, limit=limit_per_source)
            elif name == "remoteok":
                results = fetch_remoteok(q, limit=limit_per_source)
            elif name == "greenhouse":
                # If the 'query' looks like a single word, try it as a slug
                if " " not in q.strip():
                    results = fetch_greenhouse(q.strip(), limit=limit_per_source)
            elif name == "lever":
                if " " not in q.strip():
                    results = fetch_lever(q.strip(), limit=limit_per_source)

            for job in results:
                # 1. Normalize & Fingerprint
                job["company"] = str(job.get("company") or "Unknown")
                job["title"] = str(job.get("title") or "Untitled")
                job["location"] = str(job.get("location") or "Remote")
                job["description"] = str(job.get("description") or "")

                fp = db.get_job_fingerprint(
                    job["company"], job["title"], job["location"]
                )
                if fp not in seen_fingerprints:
                    job["fingerprint"] = fp
                    # Ensure 'id' exists for UI button keys
                    job["id"] = job.get("source_id") or fp
                    all_results.append(job)
                    seen_fingerprints.add(fp)

    log.info(
        f"Query completed: {len(all_results)} unique jobs found across {len(source_names)} sources."
    )
    return all_results
