import sqlite3
import os
import uuid
import datetime
from supabase import create_client
from dotenv import load_dotenv

# Load environment variables
load_dotenv(r"c:\Codes\Projects\TailoredResume\.env")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SQLITE_DB_PATH = r"c:\Codes\Projects\TailoredResume\data\app.db"

def migrate(user_id):
    if not user_id:
        print("Error: user_id is required for migration.")
        return

    print(f"Starting migration to Supabase for User ID: {user_id}")
    
    # Connect to SQLite
    if not os.path.exists(SQLITE_DB_PATH):
        print(f"Error: SQLite database not found at {SQLITE_DB_PATH}")
        return
        
    conn = sqlite3.connect(SQLITE_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Connect to Supabase
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    # 1. Migrate Jobs
    print("Migrating 'jobs'...")
    cursor.execute("SELECT * FROM jobs")
    jobs = cursor.fetchall()
    
    jobs_data = []
    for job in jobs:
        # Convert fetched_at from REAL (seconds) to ISO string
        fetched_at = datetime.datetime.fromtimestamp(job["fetched_at"], datetime.timezone.utc).isoformat() if job["fetched_at"] else None
        
        jobs_data.append({
            "id": job["id"],
            "user_id": user_id,
            "title": job["title"],
            "company": job["company"],
            "location": job["location"],
            "url": job["url"],
            "date_posted": job["date_posted"],
            "salary": job["salary"],
            "description": job["description"],
            "site": job["site"],
            "tags": job["tags"] if isinstance(job["tags"], list) else (job["tags"].split(",") if job["tags"] else []),
            "fetched_at": fetched_at,
            "score": job["score"],
            "verdict": job["verdict"],
            "reason": job["reason"]
        })
        
    if jobs_data:
        try:
            # Batch upsert
            for i in range(0, len(jobs_data), 100):
                batch = jobs_data[i:i+100]
                supabase.table("jobs").upsert(batch).execute()
            print(f"✅ Migrated {len(jobs_data)} jobs.")
        except Exception as e:
            print(f"❌ Failed to migrate jobs: {e}")
    else:
        print("No jobs found in SQLite.")

    # 2. Migrate Apply Attempts
    print("Migrating 'apply_attempts'...")
    cursor.execute("SELECT * FROM apply_attempts")
    attempts = cursor.fetchall()
    
    attempts_data = []
    for att in attempts:
        # Convert timestamps
        created_at = datetime.datetime.fromtimestamp(att["created_at"], datetime.timezone.utc).isoformat() if att["created_at"] else None
        applied_at = datetime.datetime.fromtimestamp(att["applied_at"], datetime.timezone.utc).isoformat() if att["applied_at"] else None
        
        attempts_data.append({
            "id": att["id"],
            "user_id": user_id,
            "job_id": att["job_id"],
            "status": att["status"],
            "job_board": att["job_board"],
            "dry_run": bool(att["dry_run"]),
            "error_msg": att["error_msg"],
            "screenshot": att["screenshot"],
            "applied_at": applied_at,
            "created_at": created_at
        })
        
    if attempts_data:
        try:
            for i in range(0, len(attempts_data), 100):
                batch = attempts_data[i:i+100]
                supabase.table("apply_attempts").upsert(batch).execute()
            print(f"✅ Migrated {len(attempts_data)} apply attempts.")
        except Exception as e:
            print(f"❌ Failed to migrate apply attempts: {e}")
    else:
        print("No apply attempts found in SQLite.")

    # 3. Migrate User Settings
    print("Migrating 'user_settings'...")
    # SQLite didn't have user_settings table in the schema I saw, 
    # but let's check if it exists or create defaults.
    try:
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_settings'")
        if cursor.fetchone():
            cursor.execute("SELECT * FROM user_settings")
            settings = cursor.fetchall()
            for s in settings:
                supabase.table("user_settings").upsert({
                    "user_id": user_id,
                    "search_queries": s["search_queries"],
                    "locations": s["locations"]
                }).execute()
            print("✅ Migrated user settings.")
        else:
            # Create default settings from profile.yaml or just skip
            print("No 'user_settings' table in SQLite. Skipping.")
    except Exception as e:
        print(f"Failed to migrate settings: {e}")

    conn.close()
    print("Migration finished!")

if __name__ == "__main__":
    import sys
    target_user_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not target_user_id:
        print("Usage: python migrate_to_supabase.py <YOUR_SUPABASE_USER_ID>")
    else:
        migrate(target_user_id)
