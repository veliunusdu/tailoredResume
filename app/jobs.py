import requests
import re
import json
from bs4 import BeautifulSoup
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
)
from app.search_config import build_searches_for_user
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

def _fetch_jobs_kariyer(search_term: str, location: str, limit: int) -> list[dict]:
    """
    Custom scraper for Kariyer.net using Playwright stealth browser.
    This bypasses Cloudflare/bot protection that blocks plain requests.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        _logger.warning("playwright not installed, skipping Kariyer.net.")
        return []

    results = []

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--no-sandbox"])
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="tr-TR",
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()

            for page_num in range(1, 4):
                if len(results) >= limit:
                    break

                url = f"https://www.kariyer.net/is-ilanlari?kw={search_term}&cp={page_num}"
                _logger.info("Kariyer.net → fetching page %s: %s", page_num, url)

                try:
                    page.goto(url, wait_until="networkidle", timeout=30_000)
                except PWTimeout:
                    _logger.warning("Kariyer.net page %s timed out, stopping.", page_num)
                    break

                # Extract __NUXT__ data from the page runtime
                nuxt_data = page.evaluate(
                    """
                    () => {
                        try { return window.__NUXT__; }
                        catch(e) { return null; }
                    }
                    """
                )

                if not nuxt_data:
                    _logger.warning("Kariyer.net: no __NUXT__ data found on page %s.", page_num)
                    break

                def _find_ads(obj):
                    if isinstance(obj, dict):
                        ads = obj.get("advertisement", {}).get("list")
                        if ads:
                            return ads
                        for v in obj.values():
                            found = _find_ads(v)
                            if found:
                                return found
                    elif isinstance(obj, list):
                        for item in obj:
                            found = _find_ads(item)
                            if found:
                                return found
                    return None

                ads = _find_ads(nuxt_data)
                if not ads:
                    _logger.info("Kariyer.net: no ads found on page %s, stopping.", page_num)
                    break

                for ad in ads:
                    job_url = (
                        f"https://www.kariyer.net{ad.get('url')}"
                        if ad.get("url")
                        else ""
                    )
                    results.append({
                        "title":       ad.get("title", "Unknown Title"),
                        "company":     ad.get("subTitle", "Unknown Company"),
                        "location":    ad.get("location", location or "Turkey"),
                        "url":         job_url,
                        "date_posted": str(ad.get("adDate", "")),
                        "site":        "kariyer.net",
                        "source_type": "kariyer",
                        "description": (
                            f"Position at {ad.get('subTitle')}. "
                            f"Location: {ad.get('location')}"
                        ),
                        "tags": [],
                        "salary": "Not listed",
                    })
                    if len(results) >= limit:
                        break

            browser.close()

        _logger.info("Kariyer.net fetched %s jobs for '%s'.", len(results), search_term)
    except Exception as e:
        _logger.error("Kariyer.net Playwright fetch failed: %s", e)

    return results


def _fetch_jobs_techcareer(search_term: str, location: str, limit: int) -> list[dict]:
    """Custom scraper for Techcareer.net."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    results = []
    page = 1
    
    try:
        while len(results) < limit and page <= 3:
            url = f"https://www.techcareer.net/jobs?filter={search_term}&page={page}"
            response = requests.get(url, headers=headers, timeout=HTTP_TIMEOUT_SEC)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            next_data_script = soup.find("script", id="__NEXT_DATA__")
            
            if not next_data_script:
                break
                
            data = json.loads(next_data_script.string)
            job_list = data.get("props", {}).get("pageProps", {}).get("initialJobList", {}).get("jobListItems", [])
            
            if not job_list:
                break
                
            for job in job_list:
                job_url = f"https://www.techcareer.net/jobs/{job.get('slug')}" if job.get('slug') else ""
                results.append({
                    "title": job.get("title", "Unknown Title"),
                    "company": job.get("owner", {}).get("name", "Unknown Company"),
                    "location": job.get("location", "Turkey"),
                    "url": job_url,
                    "date_posted": "", 
                    "site": "techcareer.net",
                    "source_type": "techcareer",
                    "description": f"Position at {job.get('owner', {}).get('name')}. Workplaces: {', '.join(job.get('workPlaces', []))}"
                })
                if len(results) >= limit:
                    break
                    
            page += 1
            
        return results
    except Exception as e:
        _logger.error("Techcareer.net fetch failed: %s", e)
        return results

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
    
    if "kariyer" in platforms:
        try:
            k_jobs = _fetch_jobs_kariyer(term, location, limit)
            search_results.extend(k_jobs)
        except Exception as e:
            _logger.error("Kariyer search failed: %s", e)

    if "techcareer" in platforms:
        try:
            t_jobs = _fetch_jobs_techcareer(term, location, limit)
            search_results.extend(t_jobs)
        except Exception as e:
            _logger.error("Techcareer search failed: %s", e)
            
    jobspy_sites = [p for p in platforms if p not in ("remotive", "kariyer", "techcareer")]
    if jobspy_sites:
        j_jobs = _fetch_jobs_jobspy(term, location, jobspy_sites, limit)
        search_results.extend(j_jobs)
        
    return search_results

def fetch_jobs(user_id: str) -> list[dict]:
    """Fetch raw job listings from all configured sources in parallel with progress bar."""
    from app.config import load_sites
    
    all_jobs = []
    searches = build_searches_for_user(user_id)
    
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
