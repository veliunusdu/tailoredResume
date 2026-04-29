import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API ───────────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).resolve().parents[1]
DATA_DIR         = BASE_DIR / "data"
CONFIG_DIR       = BASE_DIR / "config"
LOG_FILE         = DATA_DIR / "agent.log"

SEARCHES_YAML    = CONFIG_DIR / "searches.yaml"
SITES_YAML       = CONFIG_DIR / "sites.yaml"

# ── Legacy Env Fallbacks (To be removed) ──────────────────────────────────────
JOB_API_URL      = os.getenv("JOB_API_URL", "https://remotive.com/api/remote-jobs")
JOB_CATEGORY     = os.getenv("JOB_CATEGORY", "software-dev")
JOB_LIMIT        = int(os.getenv("JOB_LIMIT", "20"))
JOBSPY_SEARCH_TERM = os.getenv("JOBSPY_SEARCH_TERM", "Software Engineer")
JOBSPY_SITES       = os.getenv("JOBSPY_SITES", "linkedin, indeed, glassdoor").split(", ")
JOBSPY_LOCATION    = os.getenv("JOBSPY_LOCATION", "Remote")
JOBSPY_LIMIT       = int(os.getenv("JOBSPY_LIMIT", "20"))

# ── Scoring thresholds ────────────────────────────────────────────────────────
SCORE_STRONG     = int(os.getenv("SCORE_STRONG", "7"))
SCORE_MAYBE      = int(os.getenv("SCORE_MAYBE", "4"))

# ── Reliability settings ──────────────────────────────────────────────────────
RETRY_ATTEMPTS           = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_INITIAL_DELAY_SEC  = float(os.getenv("RETRY_INITIAL_DELAY_SEC", "1.0"))
RETRY_BACKOFF_FACTOR     = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))
HTTP_TIMEOUT_SEC         = float(os.getenv("HTTP_TIMEOUT_SEC", "15"))

# ── Cache behavior ────────────────────────────────────────────────────────────
JOBS_CACHE_TTL_SEC = int(os.getenv("JOBS_CACHE_TTL_SEC", str(30 * 60)))

# ── LLM Batching & Throttling ─────────────────────────────────────────────────
LLM_BATCH_SIZE              = int(os.getenv("LLM_BATCH_SIZE", "5"))
LLM_MAX_CONCURRENT_BATCHES  = int(os.getenv("LLM_MAX_CONCURRENT_BATCHES", "3"))
LLM_MIN_INTERVAL_SEC        = float(os.getenv("LLM_MIN_INTERVAL_SEC", "2.0"))
LLM_RATE_LIMIT_COOLDOWN_SEC = float(os.getenv("LLM_RATE_LIMIT_COOLDOWN_SEC", "60.0"))
LLM_MAX_DESC_CHARS          = int(os.getenv("LLM_MAX_DESC_CHARS", "600"))

# ── Config Loaders ────────────────────────────────────────────────────────────
def load_searches() -> list[dict]:
    if SEARCHES_YAML.exists():
        with open(SEARCHES_YAML, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            if "queries" in data and "locations" in data:
                queries = [q["query"] for q in data.get("queries", [])]
                locations = [loc["location"] for loc in data.get("locations", [])]
                boards = data.get("boards", [])
                limit = data.get("defaults", {}).get("results_per_site", 20)
                
                searches = []
                for term in queries:
                    for location in locations:
                        searches.append({
                            "term": term,
                            "location": location,
                            "limit": limit,
                            "platforms": boards
                        })
                return searches
            return data.get("searches", [])
    return []

def load_sites() -> dict:
    if SITES_YAML.exists():
        with open(SITES_YAML, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}

