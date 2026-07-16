from fastapi.testclient import TestClient
import pytest

import app.api as api_module
import app.db as db_module
from app.auth import get_current_user


@pytest.fixture
def client():
    api_module.app.dependency_overrides[get_current_user] = lambda: "test-user"
    with TestClient(api_module.app) as test_client:
        yield test_client
    api_module.app.dependency_overrides.clear()


def test_stats_returns_persisted_discovery_run(client, monkeypatch):
    run = {
        "run_id": "run-1",
        "raw_scraped_count": 10,
        "filtered_count": 7,
        "inserted_count": 5,
        "scored_count": 4,
        "strong_count": 2,
        "maybe_count": 1,
        "failed_count": 1,
        "status": "completed",
        "timestamp": 123.0,
    }
    monkeypatch.setattr(api_module, "get_all_scored_jobs", lambda user_id: [
        {"score": 8}, {"score": 5}, {"score": 2}
    ])
    monkeypatch.setattr(api_module, "get_latest_discovery_run", lambda user_id: run)

    response = client.get("/stats")

    assert response.status_code == 200
    assert response.json()["last_discovery"] == run
    assert response.json()["avg_score"] == 5.0


def test_source_analytics_uses_authenticated_user(client, monkeypatch):
    seen = []
    monkeypatch.setattr(api_module, "get_source_analytics", lambda user_id: seen.append(user_id) or [])

    response = client.get("/analytics/sources")

    assert response.status_code == 200
    assert seen == ["test-user"]


def test_job_status_rejects_unknown_pipeline_stage(client):
    response = client.put("/jobs/job-1/status", json={"status": "invented-stage"})
    assert response.status_code == 422


def test_job_status_update_is_user_scoped(client, monkeypatch):
    updates = []
    monkeypatch.setattr(api_module, "get_job_by_id", lambda job_id, user_id: {"id": job_id})
    monkeypatch.setattr(
        db_module,
        "update_job_status",
        lambda job_id, status, user_id: updates.append((job_id, status, user_id)),
    )

    response = client.put("/jobs/job-1/status", json={"status": "interview"})

    assert response.status_code == 200
    assert response.json()["new_status"] == "interview"
    assert updates == [("job-1", "interview", "test-user")]


def test_job_response_keeps_pipeline_fields(client, monkeypatch):
    monkeypatch.setattr(api_module, "get_job_by_id", lambda job_id, user_id: {
        "id": job_id,
        "title": "Backend Engineer",
        "status": "rejected",
        "missing_skills": ["Kafka"],
        "found_skills": ["Python"],
        "required_skills": ["Python", "Kafka"],
        "interview_questions": [{"question": "Why us?"}],
        "skill_match_score": 50,
    })

    response = client.get("/jobs/job-1")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rejected"
    assert body["missing_skills"] == ["Kafka"]
    assert body["interview_questions"] == [{"question": "Why us?"}]

