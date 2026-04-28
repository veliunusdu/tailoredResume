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

def test_filter_jobs_allowlist():
    jobs = [
        {"title": "Python Developer", "tags": ["backend"]},
        {"title": "Intern", "tags": []},
        {"title": "Java Developer", "tags": ["data"]}
    ]
    filtered = filter_jobs(jobs)
    # Python Developer matches "python"
    # Intern matches "intern"
    # Java Developer matches "data"
    assert len(filtered) == 3

def test_filter_jobs_blocklist():
    jobs = [
        {"title": "Senior Python Developer", "tags": ["backend"]},
        {"title": "Lead Engineer", "tags": ["python"]},
        {"title": "Junior Python Developer", "tags": ["backend"]}
    ]
    filtered = filter_jobs(jobs)
    # Senior and Lead should be blocked
    assert len(filtered) == 1
    assert filtered[0]["title"] == "Junior Python Developer"

def test_filter_jobs_case_insensitive():
    jobs = [{"title": "PYTHON DEVELOPER", "tags": ["BACKEND"]}]
    filtered = filter_jobs(jobs)
    assert len(filtered) == 1

def test_filter_jobs_empty_input():
    assert filter_jobs([]) == []
    assert filter_jobs(None) == []

def test_filter_jobs_malformed_input():
    assert filter_jobs([None, {}, "string"]) == []
