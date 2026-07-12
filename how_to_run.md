1. Main Application Commands
   The toolkit uses a central main.py entry point. Run these commands from the root directory:

Initialize the Setup Wizard:
python main.py init

Run the Ingestion Pipeline (Fetch, filter, and AI-score new jobs):
python main.py run

Start the Backend API Server:
python main.py api

Reset the Database Schema:
python main.py reset-db

2. Running Evaluation & Telemetry Scripts
   You can run the specialized scripts we updated or added using python directly:

Run the LLM Evaluation Suite (Outputs pass/fail and breakdown by category and difficulty):
python scripts/run_evals.py

View Yield Metrics & Analytics (Shows raw, filtered, and strong match counts per board):
python scripts/source_metrics.py <user_id>

Export Scored Jobs to Evals Dataset (Siphons evaluated jobs into evals_dataset.json):
python scripts/export_to_eval.py <user_id> [limit]

3. Running Tests
   To run all verification tests:
   python -m pytest tests/
