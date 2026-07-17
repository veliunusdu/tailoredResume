import pytest
from app.llm import (
    score_job, 
    score_jobs_batch, 
    _normalize_result, 
    SingleJobEvaluation, 
    BatchJobEvaluations, 
    BatchJobEvaluationItem
)

def test_normalize_result_valid():
    res = {"verdict": "yes", "role_match": 80, "recommendation": "Good match"}
    norm = _normalize_result(res)
    assert norm["role_match"] == 80
    assert norm["verdict"] == "yes"

def test_normalize_result_invalid_score():
    res = {"verdict": "yes", "role_match": "high", "recommendation": "Good match"}
    norm = _normalize_result(res)
    assert norm["role_match"] == 0

def test_normalize_result_missing_fields():
    res = {}
    norm = _normalize_result(res)
    assert norm["verdict"] == "no"
    assert norm["role_match"] == 0

def test_score_job_success(mocker):
    from app.llm import SingleJobEvaluation
    # Mock the _call_llm_structured function to return a SingleJobEvaluation Pydantic model
    mock_eval = SingleJobEvaluation(verdict="yes", role_match=90, skills_match=90, experience_match=90, education_match=90, recommendation="Excellent")
    mocker.patch("app.llm._call_llm_structured", return_value=mock_eval)
    
    job = {"id": "0", "title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    profile = {"seniority_levels": [], "exclude_titles": [], "locations": [], "resume_summary": ""}
    result = score_job(job, profile)
    assert result["verdict"] == "yes"
    assert result["role_match"] == 90

def test_score_job_failure(mocker):
    # Mock _call_llm_structured to raise an exception to test fallback behavior
    mocker.patch("app.llm._call_llm_structured", side_effect=Exception("API Error"))
    
    job = {"id": "0", "title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    profile = {"seniority_levels": [], "exclude_titles": [], "locations": [], "resume_summary": ""}
    result = score_job(job, profile)
    assert result["verdict"] == "no"
    assert result["recommendation"] == "model unavailable"

def test_score_jobs_batch_success(mocker):
    from app.llm import BatchJobEvaluations, BatchJobEvaluationItem
    # Mock _call_llm_structured to return BatchJobEvaluations Pydantic model
    mock_evals = BatchJobEvaluations(evaluations=[
        BatchJobEvaluationItem(id="0", verdict="yes", role_match=80, skills_match=80, experience_match=80, education_match=80, recommendation="Match 1"),
        BatchJobEvaluationItem(id="1", verdict="no", role_match=20, skills_match=20, experience_match=20, education_match=20, recommendation="Match 2")
    ])
    mocker.patch("app.llm._call_llm_structured", return_value=mock_evals)
    
    jobs = [
        {"id": "0", "title": "J0", "company": "C", "location": "L", "tags": [], "description": ""},
        {"id": "1", "title": "J1", "company": "C", "location": "L", "tags": [], "description": ""}
    ]
    profile = {"seniority_levels": [], "exclude_titles": [], "locations": [], "resume_summary": ""}
    results = score_jobs_batch(jobs, profile)
    assert len(results) == 2
    assert results[0]["verdict"] == "yes"
    assert results[0]["role_match"] == 80
