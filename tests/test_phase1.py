import yaml
from ajas.cli import generate_cv
from ajas.parser import clean_html
from ajas.sanitizer import inject_pii, sanitise


def test_pii_lifecycle():
    """Verify PII is sanitized before LLM and injected after."""
    pii_data = {"[[EMAIL]]": "john@example.com"}
    raw_text = "Contact john@example.com"

    # 1. Sanitise
    sanitized = sanitise(raw_text)
    assert "john@example.com" not in sanitized
    assert "[[EMAIL]]" in sanitized

    # 2. Inject
    injected = inject_pii(sanitized, pii_data)
    assert injected == raw_text


def test_html_cleaning():
    """Verify HTML parser cleans tokens."""
    html = "<html><body><h1>Title</h1><script>alert(1)</script></body></html>"
    cleaned = clean_html(html)
    assert "alert(1)" not in cleaned
    assert "Title" in cleaned


def test_cli_smoke(tmp_path):
    """Full pipeline smoke test."""
    job_file = tmp_path / "job.txt"
    job_file.write_text("Need a Python Dev with AWS", encoding="utf-8")

    master_file = tmp_path / "master.yaml"
    master_content = {
        "pii": {"[[FULL_NAME]]": "Test User", "[[EMAIL]]": "test@user.com"},
        "experience": [
            {
                "company": "X",
                "role": "Dev",
                "bullets": [
                    {
                        "text": "Python",
                        "impact": "High",
                        "keywords": ["aws", "backend", "cloud", "ci/cd"],
                    }
                ],
            }
        ],
        "skills": [
            "Python",
            "AWS",
            "Backend Development",
            "Cloud Computing",
            "CI/CD Pipelines",
        ],
    }
    master_file.write_text(yaml.dump(master_content), encoding="utf-8")

    out_dir = tmp_path / "out"

    # Run pipeline
    generate_cv(str(job_file), str(master_file), str(out_dir))

    # Verify outputs
    # Since pandoc might be missing, we at least expect the .md file we added as fallback
    # Let's check if the directory exists and contains our base file
    output_files = list(out_dir.glob("tailored_cv_job.*"))
    assert len(output_files) > 0

    # Verify PII in the markdown fallback (if it exists)
    md_file = out_dir / "tailored_cv_job.md"
    if md_file.exists():
        content = md_file.read_text(encoding="utf-8")
        assert "[[EMAIL]]" not in content
        assert "test@user.com" in content
        assert "Test User" in content
