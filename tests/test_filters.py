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
        "queries": [{"query": "python"}, {"query": "django"}],
        "exclude_titles": []
    })
    
    dummy_desc = "x" * 201
    
    jobs = [
        {"title": "Python Developer", "tags": [], "description": dummy_desc},
        {"title": "Senior Django Eng", "tags": [], "description": dummy_desc},
        {"title": "Frontend React", "tags": ["python"], "description": dummy_desc},
        {"title": "Java Dev", "tags": [], "description": dummy_desc}
    ]
    
    filtered = filter_jobs(jobs, "mock-user")
    # All pass because allowlist is disabled
    assert len(filtered) == 4

def test_filter_jobs_blocklist(mocker):
    mocker.patch("app.filters.get_search_config", return_value={
        "queries": [],
        "exclude_titles": ["senior", "manager"]
    })
    
    dummy_desc = "x" * 201
    jobs = [
        {"title": "Python Developer", "tags": [], "description": dummy_desc},
        {"title": "Senior Python Eng", "tags": [], "description": dummy_desc},
        {"title": "Product Manager", "tags": [], "description": dummy_desc}
    ]
    
    filtered = filter_jobs(jobs, "mock-user")
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Python Developer"

def test_filter_jobs_case_insensitive(mocker):
    mocker.patch("app.filters.get_search_config", return_value={
        "queries": [{"query": "python"}],
        "exclude_titles": []
    })
    dummy_desc = "x" * 201
    jobs = [{"title": "PYTHON DEVELOPER", "tags": ["BACKEND"], "description": dummy_desc}]
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
