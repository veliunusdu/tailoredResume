import pytest
import requests_mock
from app.jobs import fetch_jobs

def test_fetch_jobs_success(requests_mock, mocker):
    # Mock cache to return None
    mocker.patch("app.jobs.get_cached_jobs", return_value=None)
    mocker.patch("app.jobs.set_cached_jobs")
    
    url = "https://remotive.com/api/remote-jobs?limit=20&category=software-dev"
    requests_mock.get(url, json={"jobs": [{"title": "Job 1"}]})
    
    jobs = fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Job 1"

def test_fetch_jobs_cache_hit(mocker):
    # Mock cache hit
    mocker.patch("app.jobs.get_cached_jobs", return_value=[{"title": "Cached Job"}])
    
    jobs = fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Cached Job"

def test_fetch_jobs_api_failure_fallback(requests_mock, mocker):
    # Mock cache miss for fresh, but hit for stale
    mocker.patch("app.jobs.get_cached_jobs", side_effect=[None, [{"title": "Stale Job"}]])
    mocker.patch("app.jobs.set_cached_jobs")
    
    url = "https://remotive.com/api/remote-jobs?limit=20&category=software-dev"
    requests_mock.get(url, status_code=500)
    
    jobs = fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Stale Job"

def test_fetch_jobs_invalid_schema(requests_mock, mocker):
    mocker.patch("app.jobs.get_cached_jobs", return_value=None)
    
    url = "https://remotive.com/api/remote-jobs?limit=20&category=software-dev"
    # Return a list of strings instead of list of dicts
    requests_mock.get(url, json={"jobs": ["not a dict"]})
    
    with pytest.raises(ValueError, match="Job at index 0 is not a dictionary"):
        fetch_jobs()
