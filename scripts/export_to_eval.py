#!/usr/bin/env python3
"""
CLI tool to export scored jobs from the database directly into the evaluation dataset format.
Usage: python scripts/export_to_eval.py <user_id> [limit]
"""
import sys
import os
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import get_connection

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/export_to_eval.py <user_id> [limit]")
        sys.exit(1)
        
    user_id = sys.argv[1]
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    
    query = """
    SELECT title, company, description, score, reason
    FROM jobs
    WHERE user_id = %s AND score IS NOT NULL
    ORDER BY fetched_at DESC
    LIMIT %s
    """
    
    exported = []
    with get_connection(user_id) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (user_id, limit))
            for row in cur.fetchall():
                title, company, description, score, reason = row
                
                # Determine expected verdict based on actual score (assuming correct)
                if score >= 7:
                    verdict = "yes"
                    min_score = 7
                    max_score = 10
                elif score >= 4:
                    verdict = "maybe"
                    min_score = 4
                    max_score = 6
                else:
                    verdict = "no"
                    min_score = 1
                    max_score = 3
                    
                exported.append({
                    "category": "auto-exported",
                    "difficulty": "medium",
                    "title": title,
                    "company": company,
                    "description": description,
                    "expected_verdict": verdict,
                    "min_score": min_score,
                    "max_score": max_score,
                    "reasoning_hint": reason
                })
                
    if not exported:
        print("No scored jobs found for this user.")
        return
        
    dataset_path = Path("app/evals_dataset.json")
    if dataset_path.exists():
        with open(dataset_path, "r", encoding="utf-8") as f:
            try:
                cases = json.load(f)
            except json.JSONDecodeError:
                cases = []
    else:
        cases = []
        
    cases.extend(exported)
    
    with open(dataset_path, "w", encoding="utf-8") as f:
        json.dump(cases, f, indent=2)
        
    print(f"Exported {len(exported)} scored jobs to {dataset_path}")

if __name__ == "__main__":
    main()
