import argparse
import app.config as config
from app.agent import run

def main():
    parser = argparse.ArgumentParser(description="Tailored Resume - AI Job Agent")
    parser.add_argument("--category", type=str, default=config.JOB_CATEGORY, help="Job category to search for (e.g., software-dev, data)")
    parser.add_argument("--limit", type=int, default=config.JOB_LIMIT, help="Maximum number of jobs to fetch")
    
    args = parser.parse_args()
    
    # Override config with CLI arguments before running
    config.JOB_CATEGORY = args.category
    config.JOB_LIMIT = args.limit
    
    run()

if __name__ == "__main__":
    main()
