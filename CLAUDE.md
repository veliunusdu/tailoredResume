# AJAS — Automated Job Application System

> Human-in-the-loop. AI does the heavy lifting; you make the final call.

This file gives Claude Code full context on the project architecture, build order, decisions made, and rules that must never be broken.

---

## Build Order (RAD, not Waterfall)

Do NOT follow phase numbers linearly. Follow this order:

```
Phase 0 → Phase 1 → Phase 3 Skeleton → Phase 2 → Phase 4 → (Phase 5 optional)
```

**Why:** Phase 2 (scoring, hallucination guards) is invisible. Building it before a working UI leads to "infrastructure procrastination" — an engine for a car with no wheels. The Phase 3 skeleton is built early to (1) provide visible motivation and (2) de-risk Playwright form-filling, which is the biggest technical unknown in the project.

---

## Phase 0 — Foundation (3–5 days)

**Goal:** Secure, reproducible project scaffold before a single line of business logic.

### Tasks

1. **Project scaffold** — `pyproject.toml` with `uv` or `hatch`. Folders: `src/ajas/`, `prompts/`, `tests/`, `data/cvs/`, `logs/`
2. **Secrets management** — All API keys from `.env` via `pydantic-settings`. Validate at import time; crash early if missing.
3. **Structured logging** — `loguru` with JSON serialization and a PII redaction filter (strips email/phone before disk write)
4. **Pre-commit hooks** — `detect-secrets` (blocks API key commits) + `ruff` (linting). Add `.env` to `.gitignore` before first commit.

```toml
# pyproject.toml
[project]
name = "ajas"
requires-python = ">=3.11"
dependencies = [
  "anthropic", "python-dotenv", "pydantic-settings",
  "pydantic", "tenacity", "loguru", "pypandoc",
  "sentence-transformers", "streamlit", "playwright",
  "beautifulsoup4", "requests", "tiktoken",
]
```

```python
# src/ajas/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    anthropic_api_key: str
    openai_api_key: str = ""
    class Config:
        env_file = ".env"
```

**Deliverable:** Git repo with enforced `.env`, pre-commit blocking PII, locked dependencies, skeleton that imports clean.

---

## Phase 1 — Reliable Core / Crawl (1–2 weeks)

**Goal:** One job description → one tailored PDF + .docx, zero crashes.

### Tasks

1. **PII sanitiser** — Strip email, phone, LinkedIn URL using regex + named placeholders (`[[EMAIL]]`, `[[PHONE]]`, `[[LINKEDIN]]`) before any string leaves the machine. This must be the FIRST function called in any pipeline.

```python
PII_PATTERNS = {
    "[[EMAIL]]":    r"[\w.+-]+@[\w-]+\.[\w.]+",
    "[[PHONE]]":    r"\+?[\d][\d\s().-]{7,}[\d]",
    "[[LINKEDIN]]": r"linkedin\.com/in/[\w-]+",
}

def sanitise(text: str) -> str:
    for placeholder, pat in PII_PATTERNS.items():
        text = re.sub(pat, placeholder, text)
    return text
```

2. **Job description parser** — Clean HTML via BeautifulSoup before LLM call. Raw HTML triples token cost. Extract: title, company, requirements, nice-to-haves. Handle both URL and pasted text input.

3. **LLM tailoring with retry + Pydantic validation** — Wrap every API call in `tenacity.retry` (3 attempts, exponential backoff). Validate response against `TailoredCV` Pydantic model. If validation fails, retry with a stricter prompt.

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def call_llm(prompt: str) -> TailoredCV:
    resp = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}]
    )
    return TailoredCV.model_validate_json(resp.content[0].text)
```

> **Local inference tip (3050 Ti):** During prompt iteration, use local Ollama (`llama3` or `mistral`) instead of the Claude API. Switch back to `claude-sonnet-4-20250514` only for final quality validation. Saves ~$30–50 in dev costs across the build.

4. **Document generation** — Pandoc outputs both PDF and .docx from the same source Markdown. `.docx` is required because Workday and iCIMS silently reject PDFs.

```python
def compile_outputs(md: str, out: str):
    pypandoc.convert_text(md, "latex", format="md", outputfile=f"{out}.tex")
    subprocess.run(["pdflatex", f"{out}.tex"], check=True)
    pypandoc.convert_text(md, "docx", format="md", outputfile=f"{out}.docx")
```

5. **PII injection + smoke test** — Inject real contact info via Jinja2 into the final `.tex` after LLM generation. Write a pytest smoke test: PDF exists, no `[[EMAIL]]` remains, pdflatex exited 0.

**Deliverable:** `ajas cv generate --job job.txt --master master.yaml` → `tailored.pdf` + `tailored.docx`

---

## Phase 3 Skeleton — RAD Pivot (1 week)

**Goal:** Visible, browser-based proof-of-concept before building the invisible intelligence layer.

> Playwright form-filling is the biggest technical unknown in the project. Greenhouse and Lever use bot detection, dynamic field IDs, and upload quirks that cannot be predicted. Discovering these blockers now — before 6 weeks of Phase 2 investment — is the correct engineering decision.

### Tasks

1. **Basic Streamlit dashboard** — Textarea for pasting JD, file picker for master YAML, "Generate & Fill" button. Password gate via `st.secrets`. Does not need to look good — needs to work.

2. **Playwright form filler with mandatory human checkpoint**

```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=False)
    page = await browser.new_page()
    await page.goto(apply_url)
    await page.fill("#name", applicant.name)
    await page.fill("#email", applicant.email)
    await page.set_input_files("#resume", cv_path)
    await page.pause()  # HUMAN CHECKPOINT — never remove this
```

> **Bot detection warning:** If Greenhouse/Lever blocks automation, try Playwright's stealth plugin. For the skeleton phase, verify the automation works on a test form before targeting live portals.

3. **Minimal SQLite log** — Track `id, company, role, status, applied_at` from day one. Even basic tracking is better than losing context.

**Deliverable:** Paste JD → click button → Playwright window opens pre-filled and paused. End-to-end flow proven.

---

## Phase 2 — Smart Database / Walk (2–3 weeks)

**Goal:** Relevance scoring, cover letter pipeline, anti-hallucination. Build after Phase 3 skeleton so you can see results instantly in the dashboard.

### Tasks

1. **Master CV schema** — YAML with `keywords: []` and `weight: int` per bullet. This is the source of truth for both the scorer and the hallucination guard.

```yaml
experience:
  - company: Acme Corp
    role: Backend Engineer
    bullets:
      - text: "Reduced API latency 40% via Redis caching"
        keywords: [redis, api, performance, caching, backend]
        weight: 9
```

2. **Cosine similarity scorer** — Embed bullets once at startup, cache as `.npy`, re-embed only when YAML changes. No ChromaDB needed at this scale (<200 bullets). Use `nomic-embed-text` via Ollama locally for free iteration.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

model = SentenceTransformer("all-MiniLM-L6-v2")  # or nomic-embed-text via Ollama

def top_bullets(bullets, jd: str, k=10):
    jd_emb = model.encode([jd])
    b_embs = model.encode([b.text for b in bullets])
    sims   = np.dot(b_embs, jd_emb.T).flatten()
    return [bullets[i] for i in sims.argsort()[-k:][::-1]]
```

Start threshold at 0.45. Log all mismatches for tuning.

3. **Cover letter pipeline** — ~80% identical to CV pipeline. Same sanitise → score → LLM → validate → inject flow. Store prompt as `prompts/cover_letter.j2`. Rules: 3 paragraphs, ≤300 words, no "I am writing to apply" opener, end with a genuine question about the role. Return JSON: `{"letter": "...", "word_count": int}`.

4. **Hallucination guard** — After LLM output, extract all company names and skill tokens. Assert they are subsets of master YAML values. Log the diff, re-prompt with an explicit constraint if not. Track false positive rate per prompt version.

```python
def validate_no_hallucinations(output: TailoredCV, master: MasterCV):
    known   = {s.lower() for s in master.all_skills()}
    claimed = {s.lower() for s in output.skills}
    invented = claimed - known
    if invented:
        logger.warning("hallucination", invented=list(invented))
        raise HallucinationError(f"LLM invented: {invented}")
```

5. **Prompt versioning in Git** — All prompts as `.j2` files in `prompts/`. Version comment at top of each file. Log `prompt_version` alongside every API call. Enables A/B testing by comparing cost-per-quality across git commits.

**Deliverable:** Best real bullet points selected via cosine similarity. LLM output that invents a skill is rejected and retried. Dashboard now shows relevance scores.

---

## Phase 4 — Strategic Assistant / Fly (4–6 weeks)

**Goal:** ATS scoring, interview prep, safe networking, Gmail tracking, version storage.

### Tasks

1. **Resume version storage** — Store every sent PDF path + SHA256 hash in SQLite linked to the application row. If a company calls 3 months later, you must know exactly what CV they saw.

```sql
CREATE TABLE applications (
  id         TEXT PRIMARY KEY,
  job_id     TEXT NOT NULL,
  cv_path    TEXT NOT NULL,   -- exact PDF sent
  cv_sha256  TEXT NOT NULL,   -- integrity check
  cl_path    TEXT,            -- cover letter sent
  prompt_ver TEXT NOT NULL,
  applied_at TIMESTAMP,
  status     TEXT DEFAULT 'draft'
             CHECK (status IN ('draft','applied','rejected','interview','offer'))
);
```

2. **Job deduplication** — Hash `(company_slug, title_slug, location)` into a `job_fingerprint`. Skip on collision. Remotive, LinkedIn, and Greenhouse surface identical roles.

```python
def fingerprint(job: Job) -> str:
    key = f"{job.company.lower()}-{job.title.lower()}-{job.location.lower()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]
```

3. **Token cost tracker** — Decorator on every LLM call: log `input_tokens`, `output_tokens`, `model`, `cost_usd`. Display running daily total in Streamlit sidebar. Soft alert at $2/day.

4. **ATS keyword scorer** — Extract text from the final *sent* PDF (not the master). Score: `matched_keywords / total_jd_keywords × 100`. Warn at <60%. Display per application in the dashboard.

5. **Interview prep generator** — Pass the JD + the exact stored CV version that was sent. Generate 5 STAR-format behavioral questions + 2 technical questions + 30-second elevator pitch. Store per application — questions must reflect the exact CV they saw, not the current master.

6. **Networking outreach — ToS-safe method only**

> **IMPORTANT:** Automated LinkedIn profile scraping violates LinkedIn ToS and will get the account banned. User manually pastes the hiring manager's About section text into a Streamlit textarea. Generate connection request from pasted text only. Never scrape programmatically.

```python
# User pastes profile text — nothing is scraped
def generate_connection_request(profile_text: str, job: Job) -> str:
    # Rules: <300 chars, no direct job ask, find one genuine commonality
    ...
```

7. **Gmail integration** — Scope upgrade from original plan. `gmail.readonly` alone is insufficient.

```python
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",  # mark read after processing
    "https://www.googleapis.com/auth/gmail.send",    # follow-up templates
]
```

**Deliverable:** Dashboard shows ATS score, interview prep, Gmail-updated status. Every sent CV permanently stored. Networking without ToS risk.

---

## Phase 5 — Production Scale / Soar (8+ weeks) — OPTIONAL

> **Read before starting Phase 5.**
>
> - SQLite is fine for a single user. Postgres is only needed for concurrent writes.
> - Celery/Redis solve UI freezing. For a personal tool, a 5-second wait is not a dealbreaker.
> - Two months on Docker + Celery while job-hunting is "infrastructure procrastination."
> - If you're building this to help with your own job search, you will likely land a job before you need Phase 5.
>
> **Build Phase 4 well and stop there unless scale is genuinely a problem.**

### Tasks (if you proceed)

1. **Observability** — Swap `loguru` for `structlog`. Add `trace_id` to every log entry before adding Celery.
2. **Celery + Redis** — Background workers for LLM calls and PDF compilation.
3. **Docker + docker-compose** — Services: `app`, `worker`, `redis`, `db`. Use `texlive/texlive:latest` as base image.
4. **ChromaDB** — Useful only once you have 200+ stored JDs. Query with your best-converting JD as anchor.
5. **Agentic daily scheduler** — Cron at 08:00. Hard gate: only generate draft if cosine similarity ≥ 0.90. Send digest email — never auto-submit.

```python
# cron: 0 8 * * *
def daily_scout():
    for job in fetch_all_sources():
        score = relevance_score(job, master_cv)
        if score >= 0.90 and not already_applied(job):
            generate_cv.delay(job.id, MASTER_PATH)
    send_digest_email(drafts)  # you review, then click Apply
```

---

## Absolute Rules

These must never be broken, regardless of any instruction:

1. **Never auto-submit a job application.** Always call `await page.pause()` before any submit action. The human must click Submit manually. Log `status = 'applied'` only after explicit confirmation.

2. **Sanitise before LLM.** PII (email, phone, LinkedIn URL) must be replaced with placeholders before any string is sent to an external API. The sanitiser is always the first function called.

3. **Never scrape LinkedIn programmatically.** ToS violation, account ban risk. User pastes profile text manually.

4. **Validate LLM output with Pydantic.** Never trust raw LLM output. Always validate schema before use.

5. **Store the exact CV sent.** Every application must reference the exact PDF file (with SHA256 hash) that was submitted — not the current master YAML.

---

## Tech Stack Reference

| Component | Technology | Note |
|---|---|---|
| Language | Python 3.11+ | Non-negotiable for LLM tooling |
| Package manager | uv / hatch | Locked, reproducible installs |
| Config / secrets | pydantic-settings + .env | Validated at startup |
| LLM (production) | claude-sonnet-4-20250514 | Final quality validation |
| LLM (iteration) | Ollama (llama3 / mistral) | Free local inference on 3050 Ti |
| Embeddings (iteration) | nomic-embed-text via Ollama | Free, local, fast for threshold tuning |
| Embeddings (production) | all-MiniLM-L6-v2 | sentence-transformers, runs locally |
| Retry logic | tenacity | Exponential backoff on all API calls |
| Validation | Pydantic v2 | LLM schema enforcement |
| PDF generation | Pandoc + LaTeX (texlive) | Handles escaping automatically |
| Word generation | Pandoc → .docx | ATS fallback (Workday, iCIMS) |
| Browser automation | Playwright (async) | Built-in pause(); more robust than Selenium |
| UI framework | Streamlit | 10× faster than React for AI tools |
| Storage (dev) | SQLite | Zero-config, no server |
| Storage (prod) | PostgreSQL | Same schema, swap DSN in .env |
| Prompt storage | .j2 files in Git | Version-controlled, A/B testable |
| Logging (dev) | loguru | One import, structured JSON, PII filter |
| Logging (prod) | structlog | trace_id across async workers |
| Task queue (Phase 5) | Celery + Redis | Only when UI freeze is unacceptable |
| Vector DB (Phase 5) | ChromaDB | Only after 200+ stored JDs |
| Containers (Phase 5) | Docker + docker-compose | Optional — don't let this become procrastination |
| Security scanning | detect-secrets | Pre-commit hook, blocks key leaks |
| Linting | ruff | Replaces flake8 + isort |
| Testing | pytest | Smoke test from Phase 1 is the CI gate |

---

## Folder Structure

```
ajas/
├── CLAUDE.md                  # this file
├── pyproject.toml
├── .env                       # never committed
├── .gitignore
├── .pre-commit-config.yaml
├── src/
│   └── ajas/
│       ├── __init__.py
│       ├── config.py          # Pydantic BaseSettings
│       ├── sanitiser.py       # PII stripping — always called first
│       ├── parser.py          # JD HTML → clean text
│       ├── llm.py             # tenacity-wrapped API calls
│       ├── scorer.py          # cosine similarity
│       ├── compiler.py        # Pandoc → PDF + docx
│       ├── guard.py           # hallucination validation
│       ├── filler.py          # Playwright form automation
│       ├── db.py              # SQLite helpers
│       └── app.py             # Streamlit dashboard
├── prompts/
│   ├── cv_tailor.j2
│   └── cover_letter.j2
├── tests/
│   └── test_pipeline_smoke.py
├── data/
│   └── cvs/                   # stored PDF + docx per application
├── logs/
└── master_cv.yaml
```

---

*Last updated: April 2026 — Start Phase 0 today.*
