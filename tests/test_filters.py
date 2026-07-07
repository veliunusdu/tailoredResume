import pytest
from app.filters import filter_jobs, _normalize

def test_normalize_basic():
    raw = {
        "title": "Software Engineer",
        "company_name": "Tech Corp",
        "candidate_required_location": "Remote",
        "url": "https://example.com",
        "publication_date": "2026-04-27T10:00:00Z",
        "salary": "$100k",
        "tags": ["python", "backend"],
        "description": "A great job."
    }
    normalized = _normalize(raw)
    assert normalized["title"] == "Software Engineer"
    assert normalized["company"] == "Tech Corp"
    assert normalized["date_posted"] == "2026-04-27"
    assert normalized["tags"] == ["python", "backend"]

def test_normalize_missing_fields():
    raw = {}
    normalized = _normalize(raw)
    assert normalized["title"] == "Unknown Title"
    assert normalized["company"] == "Unknown Company"
    assert normalized["location"] == "Remote"
    assert normalized["date_posted"] == ""
    assert isinstance(normalized["tags"], list)

def test_filter_jobs_allowlist(mocker):
    mocker.patch("app.filters.get_search_config", return_value={
        "queries": [{"query": "python"}, {"query": "intern"}, {"query": "data"}],
        "exclude_titles": []
    })
    jobs = [
        {"title": "Python Developer", "tags": ["backend"]},
        {"title": "Intern", "tags": []},
        {"title": "Java Developer", "tags": ["data"]}
    ]
    filtered = filter_jobs(jobs, "mock-user")
    assert len(filtered) == 3

def test_filter_jobs_blocklist(mocker):
    mocker.patch("app.filters.get_search_config", return_value={
        "queries": [{"query": "python"}, {"query": "engineer"}],
        "exclude_titles": ["senior", "lead"]
    })
    jobs = [
        {"title": "Senior Python Developer", "tags": ["backend"]},
        {"title": "Lead Engineer", "tags": ["python"]},
        {"title": "Junior Python Developer", "tags": ["backend"]}
    ]
    filtered = filter_jobs(jobs, "mock-user")
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Junior Python Developer"

def test_filter_jobs_case_insensitive(mocker):
    mocker.patch("app.filters.get_search_config", return_value={
        "queries": [{"query": "python"}],
        "exclude_titles": []
    })
    jobs = [{"title": "PYTHON DEVELOPER", "tags": ["BACKEND"]}]
    filtered = filter_jobs(jobs, "mock-user")
    assert len(filtered) == 1

def test_filter_jobs_empty_input(mocker):
    mocker.patch("app.filters.get_search_config", return_value={
        "queries": [],
        "exclude_titles": []
    })
    assert filter_jobs([], "mock-user") == []
    assert filter_jobs(None, "mock-user") == []

def test_filter_jobs_malformed_input(mocker):
    mocker.patch("app.filters.get_search_config", return_value={
        "queries": [],
        "exclude_titles": []
    })
    assert filter_jobs([None, {}, "string"], "mock-user") == []
