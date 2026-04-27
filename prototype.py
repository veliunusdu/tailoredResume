import os
import json
import requests
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-3-flash-preview")

# ── Filters ──────────────────────────────────────────────────────────────────

BLOCKLIST = ["senior", "lead", "manager", "director", "head of", "principal", "staff", "vp", "vice president"]
ALLOWLIST = ["python", "backend", "fullstack", "flask", "django", "fastapi", "data", "ml", "ai", "intern"]

def fetch_jobs():
    response = requests.get("https://remotive.com/api/remote-jobs?limit=20&category=software-dev")
    return response.json()["jobs"]

def filter_jobs(jobs):
    filtered = []
    for job in jobs:
        title = (job.get("title") or "").lower()
        if any(word in title for word in BLOCKLIST):
            continue
        tags = " ".join(job.get("tags") or []).lower()
        combined = title + " " + tags
        if not any(word in combined for word in ALLOWLIST):
            continue
        filtered.append({
            "title":       job.get("title"),
            "company":     job.get("company_name"),
            "location":    job.get("candidate_required_location") or "Remote",
            "url":         job.get("url"),
            "date_posted": job.get("publication_date", "")[:10],
            "salary":      job.get("salary") or "Not listed",
            "tags":        job.get("tags") or [],
            "description": job.get("description") or "",
        })
    return filtered

# ── LLM scoring ───────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """
You are a job fit evaluator for a university student with the following profile:

- Level: beginner / entry-level, currently learning
- Stack: Python, some experience with Flask and basic ML concepts
- Looking for: internships, junior roles, entry-level positions in backend, data, or AI/ML
- Location: open to fully remote worldwide
- Dealbreakers: requires 3+ years experience, requires degree already completed,
  senior/lead/principal roles, test/sample/fake postings

Evaluate the job and return ONLY valid JSON in this exact schema:
{
  "verdict": "yes" | "maybe" | "no",
  "score": <integer 0-10>,
  "reason": "<one sentence>"
}

Commit to a verdict first. Score 8-10 = strong match, 4-7 = possible, 0-3 = not suitable.
""".strip()

def score_job(job):
    user_prompt = f"""
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}
Tags: {', '.join(job['tags'][:10])}
Description (excerpt): {job['description'][:600]}
""".strip()

    try:
        response = model.generate_content(
            f"{SYSTEM_PROMPT}\n\n{user_prompt}",
        )
        raw = response.text.strip()

        # Strip markdown code fences if model wraps output
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)
        return result
    except Exception as e:
        print(f"  [!] Score failed for '{job['title']}': {e}")
        return {"verdict": "no", "score": 0, "reason": "parse error"}

# ── Main ──────────────────────────────────────────────────────────────────────

VERDICT_ICON = {"yes": "✅", "maybe": "🤔", "no": "❌"}

jobs      = fetch_jobs()
filtered  = filter_jobs(jobs)
strong, maybe = [], []

print(f"Fetched {len(jobs)} → rule-filtered {len(filtered)} → scoring with AI...\n")

for job in filtered:
    result = score_job(job)
    job.update(result)
    if result["score"] >= 7:
        strong.append(job)
    elif result["score"] >= 4:
        maybe.append(job)

def print_job(job):
    icon = VERDICT_ICON.get(job.get("verdict", "no"), "❓")
    print(f"{icon}  [{job['score']}/10] {job['title']} @ {job['company']}")
    print(f"     Location : {job['location']}")
    print(f"     Salary   : {job['salary']}")
    print(f"     Reason   : {job['reason']}")
    print(f"     URL      : {job['url']}")
    print()

print(f"{'='*55}")
print(f"  ✅ STRONG MATCHES ({len(strong)})")
print(f"{'='*55}")
for job in strong:
    print_job(job)

print(f"{'='*55}")
print(f"  🤔 MAYBE ({len(maybe)})")
print(f"{'='*55}")
for job in maybe:
    print_job(job)
