import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel


class JobDescription(BaseModel):
    title: str = ""
    company: str = ""
    description: str = ""
    requirements: list[str] = []
    nice_to_haves: list[str] = []


def clean_html(html_content: str) -> str:
    """Remove script, style, and other unnecessary tags from HTML."""
    if not html_content:
        return ""
    soup = BeautifulSoup(html_content, "html.parser")
    # Remove script and style elements
    for script_or_style in soup(["script", "style"]):
        script_or_style.decompose()

    # Get text
    text = soup.get_text(separator="\n")

    # Break into lines and remove leading/trailing whitespace
    lines = (line.strip() for line in text.splitlines())
    # Break multi-headlines into a line each
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    # Drop blank lines
    text = "\n".join(chunk for chunk in chunks if chunk)
    return text


def parse_job_url(url: str) -> str:
    """Fetch and clean text from a job URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return clean_html(response.text)
    except Exception as e:
        from ajas.logger import log

        log.error(f"Failed to fetch URL {url}: {e}")
        return ""
