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
    
    # API command
    api_parser = subparsers.add_parser("api", help="Launch the FastAPI backend server")
    
    args = parser.parse_args()
    
    if args.command == "init":
        run_init()
    elif args.command == "run":
        run_agent()
    elif args.command == "api":
        from app.api import app
        import uvicorn
        from app.logger import get_logger
        _logger = get_logger("app.api")
        _logger.info("Starting API server via CLI...")
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    main()
