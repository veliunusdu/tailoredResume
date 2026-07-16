import argparse
import sys
import uvicorn
from app.init import run_init

def main():
    parser = argparse.ArgumentParser(description="Tailored Resume Career Toolkit")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Run the interactive setup wizard")

    # Reset DB command
    reset_parser = subparsers.add_parser("reset-db", help="Delete the local SQLite database to force a schema recreation")

    # Dashboard command
    dashboard_parser = subparsers.add_parser("dashboard", help="Start the Next.js backend API")
    dashboard_parser.add_argument("--port", type=int, default=8001, help="Port for the API")
    
    # API command (alias for dashboard)
    api_parser = subparsers.add_parser("api", help="Launch the FastAPI backend server (alias for dashboard)")
    api_parser.add_argument("--port", type=int, default=8001, help="Port for the API")
    
    # Run command
    run_parser = subparsers.add_parser("run", help="Fetch, filter, and score new jobs")
    run_parser.add_argument("user_id", help="The user ID to run ingestion for")
    
    args = parser.parse_args()
    
    if args.command == "init":
        run_init()
    elif args.command == "reset-db":
        import os
        from pathlib import Path
        print("⚠️ Deleting local SQLite database...")
        db_path = Path(__file__).resolve().parent / "app.db"
        try:
            if db_path.exists():
                os.remove(db_path)
                print("✅ Database reset complete. The schema will be recreated on the next run.")
            else:
                print("ℹ️ Database file does not exist. Nothing to reset.")
        except Exception as e:
            print(f"❌ Failed to reset database: {e}")
    elif args.command == "run":
        from app.agent import run as run_agent
        run_agent(args.user_id)
    elif args.command in ["dashboard", "api"]:
        # Import app here to avoid requiring all dependencies for other commands
        from app.api import app
        from app.logger import get_logger
        _logger = get_logger("app.api")
        _logger.info(f"🚀 Starting API server on http://localhost:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port, log_level="info")

if __name__ == "__main__":
    main()
