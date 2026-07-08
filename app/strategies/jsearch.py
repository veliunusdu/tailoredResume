import requests
import json
import urllib.parse
from app.config import JSEARCH_API_KEY, HTTP_TIMEOUT_SEC
from app.logger import get_logger

_logger = get_logger(__name__)

class JSearchStrategy:
    """
    Strategy for fetching jobs using the RapidAPI JSearch endpoint.
    """
    
    BASE_URL = "https://jsearch.p.rapidapi.com/search"

    def __init__(self):
        self.api_key = JSEARCH_API_KEY
        if not self.api_key:
            _logger.warning("JSEARCH_API_KEY is not set. JSearch API calls will likely fail.")

    def fetch_jobs(self, search_term: str, location: str, limit: int) -> list[dict]:
        """
        Fetch jobs from JSearch and map them to the unified schema.
        """
        if not self.api_key:
            return []

        # JSearch combines term and location in the 'query' parameter
        query = search_term
        if location and location.lower() != "remote":
            query = f"{search_term} in {location}"
        elif location and location.lower() == "remote":
            query = f"{search_term} remote"

        querystring = {
            "query": query,
            "page": "1",
            "num_pages": "1"
        }

        headers = {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
        }

        try:
            _logger.info(f"JSearch: Fetching jobs for query: '{query}'")
            response = requests.get(self.BASE_URL, headers=headers, params=querystring, timeout=HTTP_TIMEOUT_SEC)
            response.raise_for_status()
            
            data = response.json()
            raw_jobs = data.get("data", [])
            
            standardized_jobs = []
            for job in raw_jobs[:limit]:
                standardized_jobs.append(self._parse_job(job))
                
            _logger.info(f"JSearch: Successfully fetched {len(standardized_jobs)} jobs.")
            return standardized_jobs
            
        except Exception as e:
            _logger.error(f"JSearch fetch failed for query '{query}': {e}")
            return []

    def _parse_job(self, job: dict) -> dict:
        """
        Map a JSearch job object to the app's unified schema.
        """
        title = job.get("job_title", "Unknown Title")
        company = job.get("employer_name", "Unknown Company")
        job_city = job.get("job_city")
        job_state = job.get("job_state")
        job_country = job.get("job_country")
        
        location_parts = [p for p in [job_city, job_state, job_country] if p]
        location = ", ".join(location_parts) if location_parts else "Remote"
        
        # JSearch sometimes provides an apply link or a Google search link
        url = job.get("job_apply_link") or job.get("job_google_link") or ""
        
        date_posted = job.get("job_posted_at_datetime_utc", "")
        
        description = job.get("job_description", "")
        
        salary = "Not listed"
        min_salary = job.get("job_min_salary")
        max_salary = job.get("job_max_salary")
        salary_currency = job.get("job_salary_currency", "USD")
        salary_period = job.get("job_salary_period", "YEAR")
        
        if min_salary and max_salary:
            salary = f"{min_salary} - {max_salary} {salary_currency}/{salary_period.lower()}"
        elif min_salary:
            salary = f"From {min_salary} {salary_currency}/{salary_period.lower()}"
            
        return {
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "date_posted": date_posted,
            "site": job.get("job_publisher", "jsearch"),
            "source_type": "jsearch",
            "description": description,
            "tags": [],
            "salary": salary,
        }
