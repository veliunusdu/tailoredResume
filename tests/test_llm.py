import pytest
import json
from app.llm import score_job, score_jobs_batch, _normalize_result

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
    # Mock the _model.generate_content
    mock_response = mocker.Mock()
    mock_response.text = json.dumps({"verdict": "yes", "score": 9, "reason": "Excellent"})
    mocker.patch("app.llm._model.generate_content", return_value=mock_response)
    
    job = {"title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    result = score_job(job)
    assert result["score"] == 9
    assert result["verdict"] == "yes"

def test_score_job_malformed_json(mocker):
    mock_response = mocker.Mock()
    mock_response.text = "This is not JSON"
    mocker.patch("app.llm._model.generate_content", return_value=mock_response)
    
    job = {"title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    # Should catch error and return fallback
    result = score_job(job)
    assert result["verdict"] == "no"
    assert result["reason"] == "model unavailable"

def test_score_job_markdown_json(mocker):
    mock_response = mocker.Mock()
    mock_response.text = "```json\n{\"verdict\": \"maybe\", \"score\": 5, \"reason\": \"OK\"}\n```"
    mocker.patch("app.llm._model.generate_content", return_value=mock_response)
    
    job = {"title": "Junior Python", "company": "Test", "location": "Remote", "tags": [], "description": ""}
    result = score_job(job)
    assert result["score"] == 5
    assert result["verdict"] == "maybe"

def test_score_jobs_batch_success(mocker):
    mock_response = mocker.Mock()
    mock_response.text = json.dumps([
        {"id": "0", "verdict": "yes", "score": 8, "reason": "Match 1"},
        {"id": "1", "verdict": "no", "score": 2, "reason": "Match 2"}
    ])
    mocker.patch("app.llm._model.generate_content", return_value=mock_response)
    
    jobs = [
        {"title": "Job 1", "company": "C1", "location": "L1", "tags": [], "description": ""},
        {"title": "Job 2", "company": "C2", "location": "L2", "tags": [], "description": ""}
    ]
    results = score_jobs_batch(jobs)
    assert len(results) == 2
    assert results[0]["score"] == 8
    assert results[1]["score"] == 2
