from datetime import datetime
from typing import Any, Dict, List
from urllib.parse import quote_plus, urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

BASE = "https://wellfound.com"


def _robots_allows(path_url: str) -> bool:
    rp = RobotFileParser()
    rp.set_url(urljoin(BASE, "/robots.txt"))
    try:
        rp.read()
        return rp.can_fetch("*", path_url)
    except Exception:
        # If robots cannot be fetched, be conservative and deny
        return False


def fetch_wellfound(
    query: str = "", limit: int = 50, allow_scrape: bool = False
) -> List[Dict[str, Any]]:
    """Best-effort Wellfound (AngelList) connector.

    NOTE: Wellfound does not provide a stable public API for scraping. This
    function is disabled by default (returns []). Set `allow_scrape=True`
    and ensure you have reviewed the site's terms before enabling.
    """
    if not allow_scrape:
        return []

    search_url = f"{BASE}/jobs?q={quote_plus(query)}"
    if not _robots_allows(search_url):
        return []

    headers = {"User-Agent": "ajas-bot/1.0 (+https://example.com)"}
    try:
        r = requests.get(search_url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except Exception:
        return []

    out: List[Dict[str, Any]] = []
    seen = set()

    # Heuristic: find anchors that link to /jobs/ pages
    anchors = soup.select("a[href*='/jobs/']")
    for a in anchors:
        href = a.get("href")
        if not href:
            continue
        # Normalize url
        if href.startswith("/"):
            url = urljoin(BASE, href.split("?")[0])
        else:
            url = href
        if url in seen:
            continue
        seen.add(url)

        title = a.get_text(strip=True) or ""
        company = ""
        location = ""

        try:
            container = a.find_parent(["article", "li", "div"]) or a.parent
            if container:
                comp_el = container.select_one(".company, .company-name, .profile-name")
                if comp_el:
                    company = comp_el.get_text(strip=True)
                loc_el = container.select_one(".location, .job-location")
                if loc_el:
                    location = loc_el.get_text(strip=True)
        except Exception:
            pass

        out.append(
            {
                "source": "wellfound",
                "source_id": url,
                "title": title,
                "company": company,
                "location": location,
                "description": "",
                "url": url,
                "posted_at": datetime.utcnow().isoformat(),
                "raw": {},
            }
        )

        if len(out) >= limit:
            break

    return out
