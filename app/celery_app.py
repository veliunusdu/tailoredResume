from celery import Celery
import os
from dotenv import load_dotenv

load_dotenv()

# Use "redis://redis:6379/0" if running in Docker, "redis://localhost:6379/0" if local
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "tailoredresume",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["app.tasks"]
)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Allow Playwright to run in threads if needed, though Celery worker is better
    worker_prefetch_multiplier=1,
    task_acks_late=True,
)

if __name__ == "__main__":
    app.start()
