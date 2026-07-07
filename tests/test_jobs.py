import pytest
import re
import requests_mock
from app.jobs import fetch_jobs, _fetch_jobs_remote

def test_fetch_jobs_success(requests_mock, mocker):
    # Mock user search configs
    mocker.patch("app.jobs.build_searches_for_user", return_value=[{
        "term": "Python developer",
        "location": "Remote",
        "limit": 20,
        "platforms": ["remotive"]
    }])
    
    # Mock jobspy and regional fetchers to avoid external requests or missing package failures
    mocker.patch("app.jobs._fetch_jobs_jobspy", return_value=[])
    mocker.patch("app.jobs._fetch_jobs_kariyer", return_value=[])
    mocker.patch("app.jobs._fetch_jobs_techcareer", return_value=[])

    # Intercept remotive API call using regex matching
    requests_mock.get(re.compile("remotive.com"), json={"jobs": [{"title": "Job 1", "company": "C1", "location": "Remote", "url": "http://job1"}]})

    jobs = fetch_jobs("mock-user-123")
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Job 1"
    assert jobs[0]["source_type"] == "remotive"

def test_fetch_jobs_api_failure(requests_mock, mocker):
    mocker.patch("app.jobs.build_searches_for_user", return_value=[{
        "term": "Python developer",
        "location": "Remote",
        "limit": 20,
        "platforms": ["remotive"]
    }])
    mocker.patch("app.jobs._fetch_jobs_jobspy", return_value=[])
    mocker.patch("app.jobs._fetch_jobs_kariyer", return_value=[])
    mocker.patch("app.jobs._fetch_jobs_techcareer", return_value=[])
    
    # Intercept remotive API and return 500 error
    requests_mock.get(re.compile("remotive.com"), status_code=500)
    
    # fetch_jobs catches search exceptions and returns whatever jobs were successfully scraped
    jobs = fetch_jobs("mock-user-123")
    assert jobs == []

def test_fetch_jobs_invalid_schema(requests_mock, mocker):
    mocker.patch("app.jobs.build_searches_for_user", return_value=[{
        "term": "Python developer",
        "location": "Remote",
        "limit": 20,
        "platforms": ["remotive"]
    }])
    mocker.patch("app.jobs._fetch_jobs_jobspy", return_value=[])
    mocker.patch("app.jobs._fetch_jobs_kariyer", return_value=[])
    mocker.patch("app.jobs._fetch_jobs_techcareer", return_value=[])
    
    # Return an invalid structure
    requests_mock.get(re.compile("remotive.com"), json={"jobs": "not a list"})
    
    jobs = fetch_jobs("mock-user-123")
    assert jobs == []

def test_fetch_jobs_invalid_schema_direct(requests_mock):
    # Directly test validation inside _fetch_jobs_remote
    requests_mock.get(re.compile("remotive.com"), json={"jobs": "not a list"})
    
    with pytest.raises(ValueError, match="Unexpected jobs payload from API: expected a list of jobs"):
        _fetch_jobs_remote("Python", 20)
