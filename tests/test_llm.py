import pytest
import json
from app.llm import (
    score_job, 
    score_jobs_batch, 
    _normalize_result,
    SingleJobEvaluation,
    BatchJobEvaluations,
    BatchJobEvaluationItem
)

def test_normalize_result_valid():
    res = {"verdict": "yes", "score": 8, "reason": "Good match"}
    norm = _normalize_result(res)
    assert norm["score"] == 8
    assert norm["verdict"] == "yes"

def test_normalize_result_invalid_score():
    res = {"verdict": "yes", "score": "high", "reason": "Good match"}
    norm = _normalize_result(res)
    assert norm["score"] == 0
    
    res = {"verdict": "yes", "score": 15, "reason": "Good match"}
    norm = _normalize_result(res)
    assert norm["score"] == 10

def test_normalize_result_missing_fields():
    res = {}
    norm = _normalize_result(res)
    assert norm["verdict"] == "no"
    assert norm["score"] == 0
    assert norm["reason"] == "No reason provided"

def test_score_job_success(mocker):
    # Mock the _call_llm_structured to return a Pydantic model
    mock_eval = SingleJobEvaluation(
        verdict="yes",
        technical_fit_score=9,
        experience_fit_score=9,
        overall_score=9,
        reason="Excellent"
    )
    mocker.patch("app.llm._call_llm_structured", return_value=mock_eval)
    
    job = {"title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    result = score_job(job)
    assert result["score"] == 9
    assert result["verdict"] == "yes"

def test_score_job_malformed_json(mocker):
    # When _call_llm_structured raises an exception, score_job should catch it and return fallback
    mocker.patch("app.llm._call_llm_structured", side_effect=Exception("API Error"))
    
    job = {"title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    result = score_job(job)
    assert result["verdict"] == "no"
    assert result["reason"] == "model unavailable"

def test_score_job_with_custom_profile(mocker):
    mock_eval = SingleJobEvaluation(
        verdict="maybe",
        technical_fit_score=5,
        experience_fit_score=5,
        overall_score=5,
        reason="OK"
    )
    mock_call = mocker.patch("app.llm._call_llm_structured", return_value=mock_eval)
    
    job = {"title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    user_profile = {"experience_level": "junior", "skills": ["Python"]}
    result = score_job(job, api_key="test-key", user_profile=user_profile)
    assert result["score"] == 5
    assert result["verdict"] == "maybe"
    
    # Verify the parameters passed to _call_llm_structured
    mock_call.assert_called_once()
    kwargs = mock_call.call_args[1]
    assert kwargs["api_key"] == "test-key"
    assert "junior" in kwargs["system_prompt"]

def test_score_jobs_batch_success(mocker):
    mock_evals = BatchJobEvaluations(
        evaluations=[
            BatchJobEvaluationItem(id="0", verdict="yes", technical_fit_score=8, experience_fit_score=8, overall_score=8, reason="Match 1"),
            BatchJobEvaluationItem(id="1", verdict="no", technical_fit_score=2, experience_fit_score=2, overall_score=2, reason="Match 2")
        ]
    )
    mocker.patch("app.llm._call_llm_structured", return_value=mock_evals)
    
    jobs = [
        {"title": "Job 1", "company": "C1", "location": "L1", "tags": [], "description": ""},
        {"title": "Job 2", "company": "C2", "location": "L2", "tags": [], "description": ""}
    ]
    results = score_jobs_batch(jobs)
    assert len(results) == 2
    assert results[0]["score"] == 8
    assert results[1]["score"] == 2
