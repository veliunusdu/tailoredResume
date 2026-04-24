import os
import smtplib
import uuid
from email.message import EmailMessage
from pathlib import Path

import yaml

from ajas.database import Database
from ajas.logger import log
from ajas.scorer import Scorer
from ajas.search import discover_new_jobs
from ajas.worker import generate_cv_task


def send_digest_email(drafts_queued, passed_jobs):
    """Sends a daily digest email containing the high-probability drafts."""
    if drafts_queued == 0:
        log.info("No drafts queued today. Skipping digest email.")
        return

    smtp_server = os.getenv("SMTP_SERVER", "localhost")
    smtp_port = int(os.getenv("SMTP_PORT", 1025))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    to_email = os.getenv("NOTIFICATION_EMAIL", "user@example.com")
    from_email = os.getenv("FROM_EMAIL", "ajas-scout@example.com")

    msg = EmailMessage()
    msg["Subject"] = f"AJAS Daily Scout: {drafts_queued} High-Probability Drafts Ready"
    msg["From"] = from_email
    msg["To"] = to_email

    body = f"Hello,\n\nThe AJAS Daily Scout has found {drafts_queued} new opportunities that matched your Master CV with a high similarity score.\n\n"
    body += (
        "The following jobs have had CVs and Cover Letters queued for generation:\n\n"
    )
    for job in passed_jobs:
        body += f"- {job['title']} at {job['company']}\n  URL: {job.get('url', 'N/A')}\n  FP: {job['fingerprint']}\n\n"

    body += "Please review the generated PDFs in your outputs folder.\n\nBest,\nAJAS Automation"
    msg.set_content(body)

    try:
        log.info(
            f"Sending email digest for {drafts_queued} queued drafts to {to_email}"
        )
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            if smtp_user and smtp_password:
                server.login(smtp_user, smtp_password)
            server.send_message(msg)
        log.info("Digest email sent successfully.")
    except Exception as e:
        log.error("Failed to send digest email", error=str(e))


def daily_scout():
    """
    Agentic daily scheduler. Finds new jobs from multiple sources,
    scores them against the master CV, and queues generation if >= 0.85.
    """
    log.info("Starting daily scout...")

    # 1. Discover new jobs from APIs
    new_count = discover_new_jobs()
    log.info(f"Discovery phase complete: {new_count} new potential jobs found.")

    db = Database()
    new_jobs = db.get_new_jobs(limit=100)

    if not new_jobs:
        log.info("No new jobs to process.")
        return

    # 2. Load Master CV
    master_path = "data/master.yaml"
    if not Path(master_path).exists():
        log.error("Master CV not found. Aborting scout.")
        return

    master_data = yaml.safe_load(Path(master_path).read_text(encoding="utf-8"))

    scorer = Scorer()
    master_text = (
        " ".join([exp["role"] for exp in master_data.get("experience", [])])
        + " "
        + " ".join(master_data.get("skills", []))
    )
    master_emb = scorer.get_embeddings([master_text])[0]

    drafts_queued = 0
    passed_jobs = []

    for job_row in new_jobs:
        job = dict(job_row)
        # Score job against master
        jd_text = f"{job['title']} {job['description']}"
        jd_emb = scorer.get_embeddings([jd_text])[0]

        # Cosine similarity
        import numpy as np

        def normalize(v):
            norm = np.linalg.norm(v)
            return v / (norm + 1e-9)

        sim = float(np.dot(normalize(master_emb), normalize(jd_emb)))

        log.info(
            f"Job {job['fingerprint']} ({job['title']} @ {job['company']}) scored {sim:.2f}"
        )

        # 3. The Gate (Lowered to 0.85 for broader matches)
        if sim >= 0.85:
            log.info("Job passed the gate! Queuing generation.")
            # Save job to temp file for worker
            job_file = f"data/temp_{job['fingerprint']}.txt"
            with open(job_file, "w", encoding="utf-8") as f:
                f.write(jd_text)

            trace_id = str(uuid.uuid4())
            # Queue draft generation
            generate_cv_task.delay(job_file, master_path, trace_id)

            db.update_job_status(job["fingerprint"], "queued", relevance_score=sim)
            drafts_queued += 1
            passed_jobs.append(job)
        else:
            db.update_job_status(job["fingerprint"], "skipped", relevance_score=sim)

    log.info(f"Daily scout complete. {drafts_queued} drafts queued for review.")
    send_digest_email(drafts_queued, passed_jobs)


if __name__ == "__main__":
    daily_scout()
