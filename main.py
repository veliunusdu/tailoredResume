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
    
    args = parser.parse_args()
    
    if args.command == "init":
        run_init()
    elif args.command == "reset-db":
        from pathlib import Path
        data_dir = Path("data")
        deleted = False
        if data_dir.exists():
            for ext in ["*.db", "*.sqlite3", "*.sqlite"]:
                for db_file in data_dir.glob(ext):
                    try:
                        db_file.unlink()
                        print(f"✅ Deleted {db_file}")
                        deleted = True
                    except Exception as e:
                        print(f"❌ Failed to delete {db_file}: {e}. Ensure the API and Celery workers are completely stopped.")
        if not deleted:
            print("ℹ️ No database files found to delete.")
        else:
            print("🔄 Database reset complete. The schema will be recreated on the next run.")
    elif args.command == "run":
        from app.agent import run as run_agent
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
