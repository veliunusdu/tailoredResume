import argparse
import sys
from app.agent import run as run_agent
from app.init import run_init

def main():
    parser = argparse.ArgumentParser(description="Tailored Resume - 6-Stage Autonomous Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Run the interactive setup wizard")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run the job aggregation and application pipeline")
    
    args = parser.parse_args()
    
    if args.command == "init":
        run_init()
    elif args.command == "run":
        run_agent()

if __name__ == "__main__":
    main()

