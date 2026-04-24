import argparse
import json
import sys
from pathlib import Path

import yaml

from ajas.generator import compile_outputs, render_cv
from ajas.llm import generate_cover_letter, tailor_cv
from ajas.logger import log
from ajas.models import MasterCV
from ajas.parser import parse_job_url
from ajas.sanitizer import inject_pii, sanitise
from ajas.scorer import Scorer
from ajas.validator import (
    HallucinationError,
    enforce_master_constraints,
    extract_master_constraints,
    validate_no_hallucinations,
)


def load_master_cv(path: str) -> MasterCV:
    """Load and validate the master CV YAML."""
    try:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        # This will raise an error if the schema is invalid
        return MasterCV.model_validate(data)
    except Exception as e:
        log.error(f"Failed to load or validate master CV: {e}")
        sys.exit(1)


def generate_cv_pipeline(job_path: str, master_path: str, output_dir: str = "data/outputs"):
    """Full pipeline: Score -> Select -> Sanitise -> LLM -> Validate -> Inject -> Compile."""
    log.info(f"Starting Intelligent CV generation for job: {job_path}")

    # 1. Load data
    if job_path.startswith("http"):
        job_text = parse_job_url(job_path)
    else:
        job_text = Path(job_path).read_text(encoding="utf-8")

    # Force master_path to string in case it came from a Path object (e.g. tests)
    master_path = str(master_path)
    master_cv = load_master_cv(master_path)

    master_data = master_cv.model_dump()
    master_constraints = extract_master_constraints(master_data)

    # 2. Relevance Scoring & Selection (Step 1 Milestone)
    log.info("Calculating relevance scores and selecting top bullets...")
    scorer = Scorer()

    all_bullets = []
    for exp in master_cv.experience:
        for b in exp.bullets:
            bullet_data = b.model_dump()
            bullet_data["company"] = exp.company
            bullet_data["role"] = exp.role
            all_bullets.append(bullet_data)

    # Select top 7 bullets as the most relevant context
    top_bullets = scorer.top_bullets(all_bullets, job_text, k=7)

    # LOG the selection as requested in the "Final Test"
    log.info("Selected Top 7 Relevant Bullets:")
    for b in top_bullets:
        log.info(
            f"Score: {b['relevance_score']:.3f} | {b['company']}: {b['text'][:50]}..."
        )

    # 3. Sanitisation
    # We pass the selected context + full master skills to the LLM
    context_str = json.dumps(
        {
            "relevant_experience": top_bullets,
            "all_available_skills": master_constraints["skills"],
            "allowed_companies": master_constraints["companies"],
        }
    )
    sanitized_context = sanitise(context_str)
    sanitized_job = sanitise(job_text)

    # 4. Tailor CV with LLM + retry once if hallucinations appear
    log.info("Tailoring CV with LLM using prompts/cv_template.md.j2 [v1]...")
    tailored_obj = tailor_cv(sanitized_job, sanitized_context, prompt_version="v1")
    tailored_dict = tailored_obj.model_dump()

    # 5. Hallucination Guard
    log.info("Checking for hallucinations against master data...")
    try:
        validate_no_hallucinations(tailored_dict, master_data)
    except HallucinationError as first_error:
        log.warning(f"Hallucination guard failed on first attempt: {first_error}")
        retry_context = json.dumps(
            {
                "relevant_experience": top_bullets,
                "all_available_skills": master_constraints["skills"],
                "allowed_companies": master_constraints["companies"],
                "hard_rules": [
                    "Use ONLY skills from all_available_skills",
                    "Use ONLY companies from allowed_companies",
                    "Do not add synonyms or new tools",
                ],
            }
        )
        strict_context = sanitise(retry_context)
        log.info("Retrying CV tailoring with stricter constraints [v1-retry]...")
        tailored_obj = tailor_cv(
            sanitized_job, strict_context, prompt_version="v1-retry"
        )
        tailored_dict = enforce_master_constraints(
            tailored_obj.model_dump(), master_data
        )
        validate_no_hallucinations(tailored_dict, master_data)

    # 6. Render & Post-Injection PII
    md_content = render_cv(tailored_dict)
    final_md = inject_pii(md_content, master_cv.pii)

    # 7. Compile
    job_name = Path(job_path).stem if not job_path.startswith("http") else "web_job"
    output_base = str(Path(output_dir) / f"tailored_cv_{job_name}")
    compile_outputs(final_md, output_base)
    log.info(f"CV Generation complete! Saved to {output_base}.*")


def generate_cv(job_path: str, master_path: str, output_dir: str = "data/outputs"):
    """Compatibility wrapper for tests expecting `generate_cv`."""
    return generate_cv_pipeline(job_path, master_path, output_dir)


def generate_tailored_for_job(
    job_dict: dict, master_path: str, output_dir: str = "data/outputs"
):
    """
    Wrapper for single-click tailoring from a discovered job dictionary.
    Returns the path to the generated CV and the app_id.
    """
    db = Database()
    job_text = f"{job_dict['title']} {job_dict['description']}"

    # Save JD to a temporary file
    temp_job_file = f"data/temp_{job_dict.get('fingerprint', 'current')}.txt"
    with open(temp_job_file, "w", encoding="utf-8") as f:
        f.write(job_text)

    # Run the existing pipeline
    generate_cv_pipeline(temp_job_file, master_path, output_dir)

    # Locate the output file
    job_name = Path(temp_job_file).stem
    output_base = str(Path(output_dir) / f"tailored_cv_{job_name}")
    cv_path = f"{output_base}.md"  # Fallback/Primary MD path

    # Log to DB
    app_id = db.add_application(
        company=job_dict["company"],
        role=job_dict["title"],
        cv_path=cv_path,
        job_hash=job_dict.get("fingerprint"),
        ats_score=0.0,  # Will be updated if scorer runs
    )

    return cv_path, app_id


def generate_cl_pipeline(
    job_path: str, master_path: str, output_dir: str = "data/outputs"
):
    """Full pipeline for cover letter."""
    log.info(f"Starting Cover Letter generation for job: {job_path}")

    # 1. Load data
    if job_path.startswith("http"):
        job_text = parse_job_url(job_path)
    else:
        job_text = Path(job_path).read_text(encoding="utf-8")

    master_cv = load_master_cv(master_path)

    # 2. Selection for consistency (Step 2 Milestone)
    scorer = Scorer()
    all_bullets = []
    for exp in master_cv.experience:
        for b in exp.bullets:
            bullet_data = b.model_dump()
            bullet_data["company"] = exp.company
            all_bullets.append(bullet_data)

    # Use SAME top bullets for consistency
    top_bullets = scorer.top_bullets(all_bullets, job_text, k=5)

    # 3. Sanitisation
    context_str = json.dumps({"selected_bullets": top_bullets})
    sanitized_context = sanitise(context_str)
    sanitized_job = sanitise(job_text)

    # 4. Generate with LLM
    log.info("Generating Cover Letter with LLM [v1]...")
    cl_obj = generate_cover_letter(sanitized_job, sanitized_context)
    cl_dict = cl_obj.model_dump()

    # 5. Render & Inject
    import os

    from jinja2 import Environment, FileSystemLoader

    template_path = "prompts/cover_letter.md.j2"
    env = Environment(loader=FileSystemLoader(os.path.dirname(template_path)))
    template = env.get_template(os.path.basename(template_path))
    md_content = template.render(**cl_dict)
    final_md = inject_pii(md_content, master_cv.pii)

    # 6. Compile
    job_name = Path(job_path).stem if not job_path.startswith("http") else "web_job"
    output_base = str(Path(output_dir) / f"tailored_cl_{job_name}")
    compile_outputs(final_md, output_base)
    log.info(f"Cover Letter Generation complete! Saved to {output_base}.*")


def main():
    parser = argparse.ArgumentParser(description="AJAS CLI")
    subparsers = parser.add_subparsers(dest="command")

    cv_parser = subparsers.add_parser("cv")
    cv_subparsers = cv_parser.add_subparsers(dest="subcommand")
    cv_gen_parser = cv_subparsers.add_parser("generate")
    cv_gen_parser.add_argument("--job", required=True)
    cv_gen_parser.add_argument("--master", required=True)
    cv_gen_parser.add_argument("--out", default="data/outputs")

    cl_parser = subparsers.add_parser("cl")
    cl_subparsers = cl_parser.add_subparsers(dest="subcommand")
    cl_gen_parser = cl_subparsers.add_parser("generate")
    cl_gen_parser.add_argument("--job", required=True)
    cl_gen_parser.add_argument("--master", required=True)
    cl_gen_parser.add_argument("--out", default="data/outputs")

    args = parser.parse_args()

    if args.command == "cv" and args.subcommand == "generate":
        generate_cv_pipeline(args.job, args.master, args.out)
    elif args.command == "cl" and args.subcommand == "generate":
        generate_cl_pipeline(args.job, args.master, args.out)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
