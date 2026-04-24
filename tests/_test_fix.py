import sys

sys.path.insert(0, "src")
# Simulate exactly what Gemini returned — mixed dict + string in suggested_projects
import json

from ajas.llm import TailoredCV

raw = json.dumps(
    {
        "summary": "Python developer with FastAPI experience.",
        "skills": ["Python", "FastAPI", "Docker"],
        "experience": [
            {
                "company": "Arch of Sigma",
                "role": "Intern",
                "bullets": [{"text": "Built APIs.", "impact": "High"}],
            }
        ],
        "suggested_projects": [
            {
                "name": "Containerized FastAPI",
                "description": "Improved deployment workflows.",
            },
            "Plain string project",
        ],
    }
)

cv = TailoredCV.model_validate_json(raw)
assert all(
    isinstance(p, str) for p in cv.suggested_projects
), f"Not all strings: {cv.suggested_projects}"
print("PASS: suggested_projects =", cv.suggested_projects)
print("PASS: summary =", cv.summary[:50])
print("ALL TESTS PASSED")
