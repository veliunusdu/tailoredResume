import app.db as db
from app.metrics import MetricsCollector
import pytest


@pytest.fixture
def temp_database(monkeypatch, tmp_path):
    original_path = db._DB_PATH
    if getattr(db._local, "conn", None) is not None:
        db._local.conn.close()
        db._local.conn = None
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "phase2.db")
    db.init_db()
    yield
    if getattr(db._local, "conn", None) is not None:
        db._local.conn.close()
        db._local.conn = None
    monkeypatch.setattr(db, "_DB_PATH", original_path)


def test_discovery_run_persists_exact_counts_and_is_user_scoped(temp_database):
    collector = MetricsCollector("user-a")
    collector.add_raw("LinkedIn", 12)
    collector.add_filtered("LinkedIn", 7)
    collector.add_inserted("LinkedIn", 5, job_id="job-1")
    collector.save_to_db(scored_count=4, strong_count=2, maybe_count=1, failed_count=1)

    latest = db.get_latest_discovery_run("user-a")
    assert latest is not None
    assert latest["run_id"] == collector.run_id
    assert latest["raw_scraped_count"] == 12
    assert latest["filtered_count"] == 7
    assert latest["inserted_count"] == 5
    assert latest["scored_count"] == 4
    assert latest["strong_count"] == 2
    assert latest["maybe_count"] == 1
    assert latest["failed_count"] == 1
    assert latest["status"] == "completed"
    assert db.get_latest_discovery_run("user-b") is None


def test_job_score_summary_uses_only_requested_user_jobs(temp_database):
    with db.get_connection() as conn:
        conn.executemany(
            "INSERT INTO jobs (id, user_id, title, score) VALUES (?, ?, ?, ?)",
            [
                ("strong", "user-a", "Strong", 8),
                ("maybe", "user-a", "Maybe", 5),
                ("pending", "user-a", "Pending", None),
                ("strong", "user-b", "Other user's job", 10),
            ],
        )

    summary = db.get_job_score_summary(["strong", "maybe", "pending"], "user-a")
    assert summary == {
        "scored_count": 2,
        "strong_count": 1,
        "maybe_count": 1,
        "failed_count": 1,
    }
