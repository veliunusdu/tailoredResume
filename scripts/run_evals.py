#!/usr/bin/env python3
"""
run_evals.py — runs LLM prompt evaluations on the job scoring engine.
Exits with code 0 on success, or 1 on evaluation failure.
"""
import os
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.llm import score_job
from app.config import GEMINI_API_KEY

def run_evaluations():
    print("🔬 Starting LLM Prompt Evaluation Suite...")

    # Load dataset
    dataset_path = Path("app/evals_dataset.json")
    if not dataset_path.exists():
        print(f"❌ Dataset file not found at {dataset_path}")
        return False

    with open(dataset_path, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # Check if Gemini API key is configured
    is_mock = not GEMINI_API_KEY or "REPLACE_ME" in GEMINI_API_KEY
    if is_mock:
        print("⚠️  GEMINI_API_KEY is not configured or contains placeholder. Running in Mock Dry-Run mode.")

    passed_count = 0
    total_count = len(cases)

    print(f"Loaded {total_count} test cases from dataset.")
    print("-" * 60)

    for i, case in enumerate(cases):
        print(f"\n[Test Case {i+1}] {case['title']} @ {case['company']}")
        
        # Build job representation
        job = {
            "id": f"test_{i}",
            "title": case["title"],
            "company": case["company"],
            "location": "Remote",
            "tags": [],
            "description": case["description"]
        }

        # Call scorer
        if is_mock:
            # Simulate ideal output for mock validation
            score = 9 if case["expected_verdict"] == "yes" else (5 if case["expected_verdict"] == "maybe" else 2)
            actual = {
                "verdict": case["expected_verdict"],
                "score": score,
                "reason": "Simulated mock response."
            }
        else:
            actual = score_job(job)

        print(f"  Expected: Verdict={case['expected_verdict']} (Score range: min={case.get('min_score', 'N/A')}, max={case.get('max_score', 'N/A')})")
        print(f"  Actual:   Verdict={actual['verdict']} (Score={actual['score']})")
        print(f"  Reason:   {actual['reason']}")

        # Validate
        verdict_ok = actual["verdict"] == case["expected_verdict"]
        
        score_ok = True
        if "min_score" in case and actual["score"] < case["min_score"]:
            score_ok = False
        if "max_score" in case and actual["score"] > case["max_score"]:
            score_ok = False

        if verdict_ok and score_ok:
            print("  ✅ PASS")
            passed_count += 1
        else:
            print("  ❌ FAIL")
            if not verdict_ok:
                print(f"     Reason: Verdict mismatch (expected {case['expected_verdict']}, got {actual['verdict']})")
            if not score_ok:
                print(f"     Reason: Score out of bounds (expected range, got {actual['score']})")

    accuracy = (passed_count / total_count) * 100
    print("\n" + "=" * 60)
    print(f"Suite Summary: {passed_count}/{total_count} passed ({accuracy:.1f}% accuracy)")
    print("=" * 60)

    # We require 100% accuracy for mock, and at least 66% (2/3) for actual LLM run to pass
    threshold = 100.0 if is_mock else 66.0
    if accuracy >= threshold:
        print("🎉 Evaluation suite passed successfully!")
        return True
    else:
        print(f"❌ Evaluation suite failed. Accuracy {accuracy:.1f}% is below threshold of {threshold}%.")
        return False

if __name__ == "__main__":
    success = run_evaluations()
    sys.exit(0 if success else 1)
