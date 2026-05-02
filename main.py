import argparse
import sys
import uvicorn
from app.agent import run as run_agent
from app.init import run_init

def main():
    parser = argparse.ArgumentParser(description="Tailored Resume - 6-Stage Autonomous Pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Run the interactive setup wizard")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Run the job aggregation and application pipeline")

    # Dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Start the Next.js backend API")
    dashboard_parser.add_argument("--port", type=int, default=8000, help="Port for the API")
    
    # API command (alias for dashboard)
    api_parser = subparsers.add_parser("api", help="Launch the FastAPI backend server (alias for dashboard)")
    api_parser.add_argument("--port", type=int, default=8000, help="Port for the API")
    
    args = parser.parse_args()
    
    if args.command == "init":
        run_init()
    elif args.command == "run":
        run_agent()
    elif args.command in ["dashboard", "api"]:
        # Import app here to avoid requiring all dependencies for other commands
        from app.api import app
        from app.logger import get_logger
        _logger = get_logger("app.api")
        _logger.info(f"🚀 Starting API server on http://localhost:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")

if __name__ == "__main__":
    main()
