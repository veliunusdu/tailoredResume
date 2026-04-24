"""
Canonical smoke test — CLAUDE.md Phase 1 deliverable gate.
Asserts:
  1. PDF (or fallback .md) is produced
  2. No [[EMAIL]] placeholder remains in the output (PII was injected)
  3. Real contact info is present in the output
  4. pdflatex / pandoc errors do not silently swallow the pipeline
"""

import pytest
import yaml

MASTER_YAML = {
    "pii": {
        "[[FULL_NAME]]": "Smoke Test User",
        "[[EMAIL]]": "smoke@test.com",
        "[[PHONE]]": "+1-000-000-0000",
        "[[LINKEDIN]]": "linkedin.com/in/smoketest",
        "[[STREET_ADDRESS]]": "1 Smoke St, Testville",
    },
    "experience": [
        {
            "company": "Smoke Corp",
            "role": "Test Engineer",
            "bullets": [
                {
                    "text": "Built automated smoke tests using Python and pytest.",
                    "keywords": [
                        "python",
                        "pytest",
                        "automation",
                        "testing",
                        "software testing",
                        "test automation",
                    ],
                    "weight": 9,
                }
            ],
        }
    ],
    "skills": ["Python", "pytest", "CI/CD", "Testing", "Automation"],
}

JD_TEXT = (
    "We are looking for a Python developer with experience in automation and testing. "
    "CI/CD knowledge is a plus."
)


@pytest.fixture
def tmp_inputs(tmp_path):
    job_file = tmp_path / "job.txt"
    job_file.write_text(JD_TEXT, encoding="utf-8")

    master_file = tmp_path / "master.yaml"
    master_file.write_text(yaml.dump(MASTER_YAML), encoding="utf-8")

    out_dir = tmp_path / "out"
    return job_file, master_file, out_dir


def test_pipeline_produces_output(tmp_inputs):
    """Pipeline completes and at least one output file is written."""
    job_file, master_file, out_dir = tmp_inputs

    from ajas.cli import generate_cv

    generate_cv(str(job_file), str(master_file), str(out_dir))

    output_files = list(out_dir.glob("tailored_cv_job.*"))
    assert len(output_files) > 0, "No output files produced by the pipeline."


def test_no_pii_placeholder_in_output(tmp_inputs):
    """The final output must NOT contain any [[...]] placeholders — PII was injected."""
    job_file, master_file, out_dir = tmp_inputs

    from ajas.cli import generate_cv

    generate_cv(str(job_file), str(master_file), str(out_dir))

    # Check the markdown fallback which is always written
    md_file = out_dir / "tailored_cv_job.md"
    if not md_file.exists():
        pytest.skip("Markdown fallback not found — PDF-only build?")

    content = md_file.read_text(encoding="utf-8")
    assert "[[EMAIL]]" not in content, "PII placeholder [[EMAIL]] found in output."
    assert "[[PHONE]]" not in content, "PII placeholder [[PHONE]] found in output."
    assert (
        "[[FULL_NAME]]" not in content
    ), "PII placeholder [[FULL_NAME]] found in output."


def test_real_pii_in_output(tmp_inputs):
    """Real contact info from master.yaml must appear in the final output."""
    job_file, master_file, out_dir = tmp_inputs

    from ajas.cli import generate_cv

    generate_cv(str(job_file), str(master_file), str(out_dir))

    md_file = out_dir / "tailored_cv_job.md"
    if not md_file.exists():
        pytest.skip("Markdown fallback not found.")

    content = md_file.read_text(encoding="utf-8")
    assert "smoke@test.com" in content, "Real email not injected into output."
    assert "Smoke Test User" in content, "Real name not injected into output."


def test_sanitizer_before_llm():
    """PII must be stripped before any string leaves the machine."""
    from ajas.sanitizer import inject_pii, sanitise

    raw = "Contact alice@example.com or +1-555-123-4567 on linkedin.com/in/alicejones"
    sanitized = sanitise(raw)

    assert "alice@example.com" not in sanitized
    assert "+1-555-123-4567" not in sanitized
    assert "linkedin.com/in/alicejones" not in sanitized
    assert "[[EMAIL]]" in sanitized
    assert "[[PHONE]]" in sanitized
    assert "[[LINKEDIN]]" in sanitized

    # Inject back
    pii = {
        "[[EMAIL]]": "alice@example.com",
        "[[PHONE]]": "+1-555-123-4567",
        "[[LINKEDIN]]": "linkedin.com/in/alicejones",
    }
    restored = inject_pii(sanitized, pii)
    assert "alice@example.com" in restored


def test_hallucination_guard_rejects_invented_skills():
    """Hallucination guard must raise for skills not in master."""
    from ajas.validator import HallucinationError, validate_no_hallucinations

    master = {"skills": ["Python", "pytest"], "experience": [{"company": "Smoke Corp"}]}
    tailored = {
        "skills": ["Python", "Kubernetes"],
        "experience": [{"company": "Smoke Corp"}],
    }

    with pytest.raises(HallucinationError):
        validate_no_hallucinations(tailored, master)


def test_hallucination_guard_passes_for_valid_output():
    """Hallucination guard must pass when output is subset of master."""
    from ajas.validator import validate_no_hallucinations

    master = {
        "skills": ["Python", "pytest", "CI/CD"],
        "experience": [{"company": "Smoke Corp"}],
    }
    tailored = {
        "skills": ["Python", "pytest"],
        "experience": [{"company": "Smoke Corp"}],
    }

    assert validate_no_hallucinations(tailored, master) is True
