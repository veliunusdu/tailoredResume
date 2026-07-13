import requests
import re
import json
from html import unescape
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from urllib.parse import quote_plus

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
    PROXY_URL,
)
from app.search_config import build_searches_for_user
from app.logger import get_logger
from app.utils import retry

_logger = get_logger(__name__)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value or "")).strip()


def _slice_job_description(text: str, start_markers: list[str], end_markers: list[str], fallback_limit: int = 8000) -> str:
    for start_marker in start_markers:
        start_index = text.find(start_marker)
        if start_index == -1:
            continue

        end_index = len(text)
        for end_marker in end_markers:
            candidate = text.find(end_marker, start_index + len(start_marker))
            if candidate != -1:
                end_index = min(end_index, candidate)

        return _clean_text(text[start_index:end_index])[:fallback_limit]

    return _clean_text(text)[:fallback_limit]


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


def _fetch_jobs_google_fallback(search_term: str, location: str, sites: list[str], limit: int, google_search_term: str) -> list[dict]:
    if scrape_jobs is None:
        _logger.warning("python-jobspy not installed, skipping Google fallback for %s.", sites)
        return []

    try:
        jobs_df = scrape_jobs(
            site_name="google",
            search_term=search_term,
            google_search_term=google_search_term,
            location=location,
            results_wanted=limit,
            hours_old=72,
            proxies=PROXY_URL if PROXY_URL else None,
        )

        if jobs_df is None or jobs_df.empty:
            return []

        jobs = jobs_df.to_dict("records")
        for job in jobs:
            job["source_type"] = sites[0] if sites else "google"
            job["site"] = sites[0] if sites else "google"
        return jobs
    except Exception as exc:
        _logger.error("Google fallback fetch failed for %s: %s", sites, exc)
        return []


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
            proxies=PROXY_URL if PROXY_URL else None,
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


def _fetch_jobs_weworkremotely(search_term: str, limit: int) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    search_url = f"https://weworkremotely.com/remote-jobs/search?term={quote_plus(search_term)}"

    try:
        response = requests.get(search_url, headers=headers, timeout=HTTP_TIMEOUT_SEC)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        job_links = []
        for anchor in soup.select('a[href^="/remote-jobs/"]'):
            href = anchor.get("href") or ""
            if "/remote-jobs/search" in href or href.startswith("/remote-jobs/find-your-plan"):
                continue
            if href not in job_links:
                job_links.append(href)

        results: list[dict] = []
        for href in job_links:
            if len(results) >= limit:
                break

            job_url = f"https://weworkremotely.com{href}"
            try:
                detail_response = requests.get(job_url, headers=headers, timeout=HTTP_TIMEOUT_SEC)
                detail_response.raise_for_status()
            except Exception:
                continue

            detail_soup = BeautifulSoup(detail_response.text, "html.parser")
            title = _clean_text(detail_soup.find("h1").get_text(" ", strip=True) if detail_soup.find("h1") else "")
            company_anchor = detail_soup.select_one('a[href*="/company/"]')
            company = _clean_text(company_anchor.get_text(" ", strip=True) if company_anchor else "")
            page_text = detail_soup.get_text("\n", strip=True)
            description = _slice_job_description(
                page_text,
                start_markers=["Posted", "About the job", "The Role:"],
                end_markers=["Related Jobs", "Additional Links"],
            )

            if not title:
                continue

            results.append({
                "title": title,
                "company": company or "Unknown Company",
                "location": "Remote",
                "url": job_url,
                "date_posted": "",
                "site": "weworkremotely",
                "source_type": "weworkremotely",
                "description": description,
                "tags": [],
                "salary": "Not listed",
            })

        return results
    except Exception as exc:
        _logger.error("We Work Remotely fetch failed for %s: %s", search_term, exc)
        return []


def _fetch_jobs_builtin(search_term: str, location: str, limit: int) -> list[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    search_url = f"https://builtin.com/jobs/search/{quote_plus(search_term)}"

    try:
        response = requests.get(search_url, headers=headers, timeout=HTTP_TIMEOUT_SEC)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        job_urls: list[str] = []
        for anchor in soup.select('a[href^="/job/"]'):
            href = anchor.get("href") or ""
            if href not in job_urls:
                job_urls.append(href)

        results: list[dict] = []
        for href in job_urls:
            if len(results) >= limit:
                break

            job_url = f"https://builtin.com{href}"
            try:
                detail_response = requests.get(job_url, headers=headers, timeout=HTTP_TIMEOUT_SEC)
                detail_response.raise_for_status()
            except Exception:
                continue

            detail_soup = BeautifulSoup(detail_response.text, "html.parser")
            json_ld_tags = detail_soup.select('script[type="application/ld+json"]')
            job_posting = None
            for tag in json_ld_tags:
                try:
                    payload = json.loads(tag.get_text())
                    graph = payload.get("@graph", []) if isinstance(payload, dict) else []
                    for item in graph:
                        if isinstance(item, dict) and item.get("@type") == "JobPosting":
                            job_posting = item
                            break
                    if job_posting:
                        break
                except Exception:
                    continue

            title = _clean_text(job_posting.get("title", "") if job_posting else (detail_soup.find("h1").get_text(" ", strip=True) if detail_soup.find("h1") else ""))
            company = "Unknown Company"
            if job_posting:
                hiring_org = job_posting.get("hiringOrganization") or {}
                company = _clean_text(hiring_org.get("name", "Unknown Company"))

            location_text = "Remote"
            if job_posting:
                locations = job_posting.get("jobLocation") or []
                if isinstance(locations, dict):
                    locations = [locations]
                elif not isinstance(locations, list):
                    locations = []
                location_parts = []
                for place in locations[:3]:
                    address = (place or {}).get("address", {}) if isinstance(place, dict) else {}
                    city = address.get("addressLocality")
                    region = address.get("addressRegion")
                    country = address.get("addressCountry")
                    piece = ", ".join([part for part in [city, region, country] if part])
                    if piece:
                        location_parts.append(piece)
                if location_parts:
                    location_text = "; ".join(location_parts)

            description = _clean_text(BeautifulSoup(job_posting.get("description", ""), "html.parser").get_text(" ", strip=True) if job_posting else detail_soup.get_text(" ", strip=True))

            if not title:
                continue

            results.append({
                "title": title,
                "company": company,
                "location": location_text or location,
                "url": job_url,
                "date_posted": str(job_posting.get("datePosted", "") if job_posting else ""),
                "site": "builtin",
                "source_type": "builtin",
                "description": description,
                "tags": [],
                "salary": "Not listed",
            })

        return results
    except Exception as exc:
        _logger.error("Built In fetch failed for %s: %s", search_term, exc)
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

from typing import Any
from app.registry import SourceRegistry

def _process_single_search(search: dict, blocked_sites: list[str], collector: Any = None) -> list[dict]:
    """Helper for parallel search execution."""
    search_results = []
    term = search.get("term", "")
    location = search.get("location", "")
    limit = search.get("limit", 20)
    platforms = search.get("platforms", [])
    
    platforms = [p for p in platforms if p not in blocked_sites]
    
    jobspy_sites = []

    for platform in platforms:
        route = SourceRegistry.get_route(platform, has_stable_access=False)
        jobs_fetched = []

        if route == "direct":
            if platform in ("weworkremotely", "wwr"):
                try:
                    jobs_fetched = _fetch_jobs_weworkremotely(term, limit)
                except Exception as e:
                    _logger.error("WWR search failed: %s", e)
                    fbq = SourceRegistry.get_fallback_query(platform)
                    if fbq:
                        jobs_fetched = _fetch_jobs_google_fallback(term, location, [platform], limit, f"{fbq} {term}")

            elif platform == "builtin":
                try:
                    jobs_fetched = _fetch_jobs_builtin(term, location, limit)
                except Exception as e:
                    _logger.error("Built In search failed: %s", e)
                    fbq = SourceRegistry.get_fallback_query(platform)
                    if fbq:
                        jobs_fetched = _fetch_jobs_google_fallback(term, location, [platform], limit, f"{fbq} {term}")

            elif platform == "remotive":
                try:
                    jobs_fetched = _fetch_jobs_remote(term, limit)
                except Exception:
                    pass

            elif platform == "jsearch":
                from app.strategies.jsearch import JSearchStrategy
                try:
                    strategy = JSearchStrategy()
                    jobs_fetched = strategy.fetch_jobs(term, location, limit)
                except Exception as e:
                    _logger.error("JSearch fetching failed: %s", e)

            elif platform == "kariyer":
                try:
                    jobs_fetched = _fetch_jobs_kariyer(term, location, limit)
                except Exception as e:
                    _logger.error("Kariyer search failed: %s", e)

            elif platform == "techcareer":
                try:
                    jobs_fetched = _fetch_jobs_techcareer(term, location, limit)
                except Exception as e:
                    _logger.error("Techcareer search failed: %s", e)

        elif route == "google_fallback":
            fbq = SourceRegistry.get_fallback_query(platform)
            if fbq:
                jobs_fetched = _fetch_jobs_google_fallback(term, location, [platform], limit, f"{fbq} {term}")

        elif route == "jobspy":
            jobspy_sites.append(platform)

        if jobs_fetched:
            search_results.extend(jobs_fetched)
            if collector:
                collector.add_raw(platform, len(jobs_fetched))

    if jobspy_sites:
        j_jobs = _fetch_jobs_jobspy(term, location, jobspy_sites, limit)
        if j_jobs:
            search_results.extend(j_jobs)
            if collector:
                from collections import Counter
                counts = Counter(j.get("site", "jobspy") for j in j_jobs)
                for s_name, count in counts.items():
                    collector.add_raw(s_name, count)
        
    return search_results


def fetch_jobs(user_id: str, collector: Any = None) -> list[dict]:
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
        futures = {executor.submit(_process_single_search, s, blocked_sites, collector): s for s in searches}
        
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
