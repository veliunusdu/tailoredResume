1. Running with Docker Compose (Recommended)
   To spin up the entire stack (PostgreSQL, Redis, FastAPI backend, Celery worker/beat, Next.js frontend) at once, run:
   ```bash
   docker-compose up --build
   ```

2. Running Locally (Manual setup)
   Before running backend commands, ensure you activate your virtual environment:
   * Windows (PowerShell): `.venv\Scripts\Activate.ps1`
   * Windows (CMD): `.venv\Scripts\activate.bat`
   * Linux/macOS: `source .venv/bin/activate`

   Make sure Redis is running (e.g., using `docker-compose up -d redis postgres` to start the backing services).

   ### Main Application Commands
   Run these commands from the root directory:

   Initialize the Setup Wizard:
   python main.py init

   Run the Ingestion Pipeline (Fetch, filter, and AI-score new jobs):
   python main.py run <user_id>

   Start the Backend API Server:
   python main.py api

   Reset the Database Schema:
   python main.py reset-db

   ### Running Celery Workers
   * Run the Celery worker (Windows-compatible command):
     celery -A app.celery_app worker --loglevel=info -P solo
   * Run Celery Beat (for scheduled background tasks):
     celery -A app.celery_app beat --loglevel=info

3. Running Evaluation & Telemetry Scripts
   Run the specialized scripts using python directly:

   Run the LLM Evaluation Suite (Outputs pass/fail and breakdown by category and difficulty):
   python scripts/run_evals.py

   View Yield Metrics & Analytics (Shows raw, filtered, and strong match counts per board):
   python scripts/source_metrics.py <user_id>

   Export Scored Jobs to Evals Dataset (Siphons evaluated jobs into evals_dataset.json):
   python scripts/export_to_eval.py <user_id> [limit]

4. Running Tests
   To run all verification tests:
   python -m pytest tests/

