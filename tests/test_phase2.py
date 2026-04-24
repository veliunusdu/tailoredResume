import pytest
from ajas.scorer import Scorer
from ajas.validator import HallucinationError, validate_no_hallucinations


def test_scorer_logic():
    scorer = Scorer()
    bullets = [
        {"text": "Python and FastAPI development", "weight": 10},
        {"text": "Frontend with React", "weight": 5},
    ]
    job_desc = "Looking for a backend Python developer"

    # In a real environment with sentence-transformers this would be more accurate
    # Here we just check if it runs and returns k results
    top_b = scorer.top_bullets(bullets, job_desc, k=1)
    assert len(top_b) == 1
    assert "text" in top_b[0]
    assert "relevance_score" in top_b[0]


def test_hallucination_guard():
    master_cv = {"skills": ["Python", "AWS"], "experience": [{"company": "Tech Corp"}]}

    # 1. Valid CV
    valid_cv = {
        "skills": ["Python"],
        "experience": [{"company": "Tech Corp", "bullets": []}],
    }
    assert validate_no_hallucinations(valid_cv, master_cv) is True

    # 2. Invalid Skills
    invalid_cv_skills = {
        "skills": ["Python", "Hacking"],
        "experience": [{"company": "Tech Corp", "bullets": []}],
    }
    with pytest.raises(HallucinationError, match="skills"):
        validate_no_hallucinations(invalid_cv_skills, master_cv)

    # 3. Invalid Company
    invalid_cv_company = {
        "skills": ["Python"],
        "experience": [{"company": "Fake Corp", "bullets": []}],
    }
    with pytest.raises(HallucinationError, match="companies"):
        validate_no_hallucinations(invalid_cv_company, master_cv)
