#!/usr/bin/env python3
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import get_source_analytics

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/source_metrics.py <user_id>")
        sys.exit(1)
        
    user_id = sys.argv[1]
    stats = get_source_analytics(user_id)
    
    if not stats:
        print(f"No metrics found for user {user_id}")
        return
        
    print(f"{'Board':<20} | {'Raw':<6} | {'Filtered':<8} | {'Inserted':<8} | {'Strong':<6} | {'Avg Score':<9}")
    print("-" * 65)
    
    for row in stats:
        board = row.get("board") or "Unknown"
        raw = row.get("total_raw", 0)
        filtered = row.get("total_filtered", 0)
        inserted = row.get("total_inserted", 0)
        strong = row.get("strong_matches", 0)
        avg = row.get("avg_score", 0.0)
        
        print(f"{board:<20} | {raw:<6} | {filtered:<8} | {inserted:<8} | {strong:<6} | {avg:.2f}")

if __name__ == "__main__":
    main()
