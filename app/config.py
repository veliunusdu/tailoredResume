import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── API ───────────────────────────────────────────────────────────────────────
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL     = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

# ── Job source ────────────────────────────────────────────────────────────────
JOB_API_URL      = os.getenv("JOB_API_URL", "https://remotive.com/api/remote-jobs")
JOB_CATEGORY     = os.getenv("JOB_CATEGORY", "software-dev")
JOB_LIMIT        = int(os.getenv("JOB_LIMIT", "20"))

# ── Scoring thresholds ────────────────────────────────────────────────────────
SCORE_STRONG     = int(os.getenv("SCORE_STRONG", "7"))
SCORE_MAYBE      = int(os.getenv("SCORE_MAYBE", "4"))

# ── Reliability settings ──────────────────────────────────────────────────────
RETRY_ATTEMPTS           = int(os.getenv("RETRY_ATTEMPTS", "3"))
RETRY_INITIAL_DELAY_SEC  = float(os.getenv("RETRY_INITIAL_DELAY_SEC", "1.0"))
RETRY_BACKOFF_FACTOR     = float(os.getenv("RETRY_BACKOFF_FACTOR", "2.0"))
HTTP_TIMEOUT_SEC         = float(os.getenv("HTTP_TIMEOUT_SEC", "15"))

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR         = Path(__file__).resolve().parents[1]
DATA_DIR         = BASE_DIR / "data"
LOG_FILE         = DATA_DIR / "agent.log"
JOBS_CACHE_FILE  = DATA_DIR / "jobs_cache.json"
LLM_CACHE_FILE   = DATA_DIR / "llm_cache.json"

# ── Cache behavior ────────────────────────────────────────────────────────────
JOBS_CACHE_TTL_SEC = int(os.getenv("JOBS_CACHE_TTL_SEC", str(30 * 60)))

# ── LLM Batching & Throttling ─────────────────────────────────────────────────
LLM_BATCH_SIZE              = int(os.getenv("LLM_BATCH_SIZE", "5"))
LLM_MAX_CONCURRENT_BATCHES  = int(os.getenv("LLM_MAX_CONCURRENT_BATCHES", "3"))
LLM_MIN_INTERVAL_SEC        = float(os.getenv("LLM_MIN_INTERVAL_SEC", "2.0"))
LLM_RATE_LIMIT_COOLDOWN_SEC = float(os.getenv("LLM_RATE_LIMIT_COOLDOWN_SEC", "60.0"))
LLM_MAX_DESC_CHARS          = int(os.getenv("LLM_MAX_DESC_CHARS", "600"))
