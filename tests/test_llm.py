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
    # Mock the _call_llm_structured function to return a SingleJobEvaluation Pydantic model
    mock_eval = SingleJobEvaluation(verdict="yes", score=9, reason="Excellent")
    mocker.patch("app.llm._call_llm_structured", return_value=mock_eval)
    
    job = {"title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    result = score_job(job)
    assert result["score"] == 9
    assert result["verdict"] == "yes"

def test_score_job_failure(mocker):
    # Mock _call_llm_structured to raise an exception to test fallback behavior
    mocker.patch("app.llm._call_llm_structured", side_effect=Exception("API Error"))
    
    job = {"title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    result = score_job(job)
    assert result["verdict"] == "no"
    assert result["reason"] == "model unavailable"

def test_score_jobs_batch_success(mocker):
    # Mock _call_llm_structured to return BatchJobEvaluations Pydantic model
    mock_evals = BatchJobEvaluations(evaluations=[
        BatchJobEvaluationItem(id="0", verdict="yes", score=8, reason="Match 1"),
        BatchJobEvaluationItem(id="1", verdict="no", score=2, reason="Match 2")
    ])
    mocker.patch("app.llm._call_llm_structured", return_value=mock_evals)
    
    jobs = [
        {"title": "Job 1", "company": "C1", "location": "L1", "tags": [], "description": ""},
        {"title": "Job 2", "company": "C2", "location": "L2", "tags": [], "description": ""}
    ]
    results = score_jobs_batch(jobs)
    assert len(results) == 2
    assert results[0]["score"] == 8
    assert results[1]["score"] == 2
