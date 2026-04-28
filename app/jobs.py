import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

try:
    from jobspy import scrape_jobs
except ImportError:
    scrape_jobs = None

from app.config import (
    HTTP_TIMEOUT_SEC,
    JOB_API_URL,
    JOB_CATEGORY,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_FACTOR,
    RETRY_INITIAL_DELAY_SEC,
    JOBSPY_SEARCH_TERM,
    JOBSPY_SITES,
    JOBSPY_LOCATION,
    JOBSPY_LIMIT,
    JOB_LIMIT,
    load_searches,
)
from app.logger import get_logger
from app.utils import retry

_logger = get_logger(__name__)


@retry(
    max_attempts=RETRY_ATTEMPTS,
    initial_delay_sec=RETRY_INITIAL_DELAY_SEC,
    backoff_factor=RETRY_BACKOFF_FACTOR,
    logger=_logger,
)
def _fetch_jobs_remote(search_term: str, limit: int) -> list[dict]:
    params = {
        "limit": limit, 
        "category": JOB_CATEGORY,
        "search": search_term
    }
    response = requests.get(JOB_API_URL, params=params, timeout=HTTP_TIMEOUT_SEC)
    response.raise_for_status()
    data = response.json().get("jobs", [])
    
    if not isinstance(data, list):
        raise ValueError("Unexpected jobs payload from API: expected a list of jobs")
    
    for job in data:
        if isinstance(job, dict):
            job["source_type"] = "remotive"
            
    return data


def _fetch_jobs_jobspy(search_term: str, location: str, sites: list[str], limit: int) -> list[dict]:
    if scrape_jobs is None:
        _logger.warning("python-jobspy not installed, skipping.")
        return []
    
    try:
        jobs_df = scrape_jobs(
            site_name=sites,
            search_term=search_term,
            location=location,
            results_wanted=limit,
            hours_old=72,
        )
        
        if jobs_df is None or jobs_df.empty:
            return []
            
        jobs = jobs_df.to_dict('records')
        for j in jobs:
            j["source_type"] = "jobspy"
        return jobs
    except Exception as e:
        _logger.error("JobSpy fetch failed for %s: %s", search_term, e)
        return []

def _process_single_search(search: dict, blocked_sites: list[str]) -> list[dict]:
    """Helper for parallel search execution."""
    search_results = []
    term = search.get("term", "")
    location = search.get("location", "")
    limit = search.get("limit", 20)
    platforms = search.get("platforms", [])
    
    platforms = [p for p in platforms if p not in blocked_sites]
    
    if "remotive" in platforms:
        try:
            r_jobs = _fetch_jobs_remote(term, limit)
            search_results.extend(r_jobs)
        except Exception:
            pass
            
    jobspy_sites = [p for p in platforms if p != "remotive"]
    if jobspy_sites:
        j_jobs = _fetch_jobs_jobspy(term, location, jobspy_sites, limit)
        search_results.extend(j_jobs)
        
    return search_results

def fetch_jobs() -> list[dict]:
    """Fetch raw job listings from all configured sources in parallel with progress bar."""
    from app.config import load_sites
    
    all_jobs = []
    searches = load_searches()
    
    if not searches:
        searches = [{
            "term": JOBSPY_SEARCH_TERM,
            "location": JOBSPY_LOCATION,
            "limit": JOBSPY_LIMIT,
            "platforms": JOBSPY_SITES + ["remotive"]
        }]
        
    sites_config = load_sites()
    blocked_sites = sites_config.get("blocked", {}).get("sites", [])
    
    _logger.info("Initializing search for %s combinations...", len(searches))
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_process_single_search, s, blocked_sites): s for s in searches}
        
        # tqdm progress bar for search combinations
        with tqdm(total=len(searches), desc="Searching Jobs", unit="comb") as pbar:
            for future in as_completed(futures):
                try:
                    results = future.result()
                    all_jobs.extend(results)
                except Exception as e:
                    _logger.error("Search task failed: %s", e)
                pbar.update(1)
            
    return all_jobs
