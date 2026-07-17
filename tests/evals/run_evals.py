import os
import sys
import json
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent.parent))

from app.tailor import generate_tailored_resume, verify_tailored_resume

DATASET = [
    {
        "id": "case_1",
        "job_desc": "Looking for a Backend Engineer. Must have 3+ years of Python, Django, and PostgreSQL. Experience with Docker and AWS is a plus.",
        "base_resume": "Software Engineer with 4 years of experience. Built REST APIs using Python and Django. Managed PostgreSQL databases. Deployed apps using Docker.",
        "expected_skills": ["Python", "Django", "PostgreSQL", "Docker"]
    },
    {
        "id": "case_2",
        "job_desc": "Frontend Developer needed. React, TypeScript, TailwindCSS. Mobile responsive design.",
        "base_resume": "Web Developer. 2 years experience with React and JS. Familiar with CSS.",
        "expected_skills": ["React"]
    }
]

def run_evals():
    print("Starting Evaluation Suite...")
    total_cases = len(DATASET)
    hallucinations_caught = 0
    format_failures = 0
    
    for case in DATASET:
        print(f"\n--- Running Eval: {case['id']} ---")
        
        # 1. Generate tailored resume
        print("Generating tailored resume...")
        tailored = generate_tailored_resume(case["job_desc"], case["base_resume"])
        if not tailored:
            print("Failed to generate.")
            format_failures += 1
            continue
            
        if not ("#" in tailored or "-" in tailored):
            print("Warning: Output may not be valid markdown.")
            format_failures += 1
            
        # 2. Run verification
        print("Running verification...")
        verification = verify_tailored_resume(case["base_resume"], tailored)
        
        has_h = verification.get("has_hallucinations", False)
        print(f"Hallucinations Detected: {has_h}")
        if has_h:
            print(f"Warnings: {verification.get('warnings')}")
            hallucinations_caught += 1
            
        # Optional: Recall calculation (e.g. are expected skills in the output?)
        missing = [s for s in case["expected_skills"] if s.lower() not in tailored.lower()]
        if missing:
            print(f"Warning: Expected skills missing from output: {missing}")
            
    print("\n=== EVALUATION RESULTS ===")
    print(f"Total Cases: {total_cases}")
    print(f"Hallucinations Detected: {hallucinations_caught}/{total_cases}")
    print(f"Format Failures: {format_failures}/{total_cases}")

if __name__ == "__main__":
    run_evals()
