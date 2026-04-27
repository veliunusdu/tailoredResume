import requests
import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

model = genai.GenerativeModel("gemini-3-flash-preview")


def fetch_jobs():
    url = "https://remoteok.com/api"
    response = requests.get(url)
    
    if response.status_code != 200:
        print("Failed to fetch jobs")
        return []
    
    data = response.json()
    
    # Skip first element (metadata)
    jobs = data[1:]
    
    return jobs


def main():
    jobs = fetch_jobs()
    
    filtered_jobs = filter_jobs_with_ai(jobs)

    if len(filtered_jobs) == 0:
        print("⚠️ No strong matches found. Showing potential matches instead...\n")
        filtered_jobs = jobs[:5]  # fallback

    else:
        print(f"\n🔥 AI found {len(filtered_jobs)} strong matches\n")

    for job in filtered_jobs:
        score = job.get("score", "N/A")
        print(f"🔥 Score: {score}/10")
        print("Company:", job.get("company"))
        print("Position:", job.get("position"))
        print("URL:", job.get("url"))
        print(f"Why this matches you: {job.get('explanation')}")
        print("-" * 40)


def filter_jobs(jobs):
    keywords = ["intern", "internship", "junior", "entry"]

    filtered = []

    for job in jobs:
        title = (job.get("position") or "").lower()
        tags = " ".join(job.get("tags") or []).lower()

        text = title + " " + tags

        if any(keyword in text for keyword in keywords):
            filtered.append(job)

    return filtered


def score_job(job):
    title = job.get("position", "")
    tags = ", ".join(job.get("tags") or [])

    prompt = f"""
    You are a strict job evaluator.

    Reject fake or test listings (like "TEST JOB", "sample", "dummy").

    Score this job for a university student seeking a real internship or entry-level tech job.

    Scoring:
    - 8-10 = real internship / strong entry-level tech job
    - 5-7 = unclear junior role
    - 0-4 = senior, irrelevant, or fake/test posting

    Job Title: {title}
    Tags: {tags}

    Return your response in the following format:
    Score: [0-10]
    Explanation: [1-2 sentences why it matches or doesn't]
    """

    response = model.generate_content(prompt)
    text = response.text.strip()

    # Simple parsing
    score = 0
    explanation = "No explanation provided."
    
    for line in text.split("\n"):
        if line.lower().startswith("score:"):
            try:
                score_str = line.split(":")[1].strip()
                # Handle cases like "8/10" or just "8"
                score = int(score_str.split("/")[0])
            except:
                score = 0
        elif line.lower().startswith("explanation:"):
            explanation = line.split(":")[1].strip()

    return score, explanation


def basic_filter(job):
    title = (job.get("position") or "").lower()

    bad_words = [
        "senior",
        "director",
        "manager",
        "lead",
        "test",
        "testing",
        "sample",
        "fake"
    ]

    return not any(word in title for word in bad_words)


def final_filter(job):
    title = (job.get("position") or "").lower()
    return "test" not in title and "fake" not in title



def filter_jobs_with_ai(jobs):
    filtered = []

    for job in jobs[:10]:
        if not basic_filter(job) or not final_filter(job):
            continue

        score, explanation = score_job(job)

        if score >= 6:
            job["score"] = score
            job["explanation"] = explanation
            filtered.append(job)

    return filtered

if __name__ == "__main__":
    main()
