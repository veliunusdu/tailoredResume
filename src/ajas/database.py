import hashlib
import sqlite3
from datetime import datetime

from ajas.logger import log


class Database:
    def __init__(self, db_path: str = "data/ajas.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialise the database with applications and jobs tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Step 1 Milestone: "Resume version storage (critical)"
            conn.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id         TEXT PRIMARY KEY,
                job_hash   TEXT UNIQUE,
                company    TEXT NOT NULL,
                role       TEXT NOT NULL,
                cv_path    TEXT NOT NULL,   -- exact PDF sent
                cv_sha256  TEXT NOT NULL,   -- integrity check
                cl_path    TEXT,            -- cover letter sent
                ats_score  REAL,            -- ATS keyword score
                prompt_ver TEXT NOT NULL,
                applied_at TIMESTAMP,
                status     TEXT DEFAULT 'draft'
                           CHECK (status IN 
                           ('draft','applied','rejected','interview','offer'))
            )
            """)

            # Step 3 Milestone: "Token cost tracker"
            conn.execute("""
            CREATE TABLE IF NOT EXISTS llm_costs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                model        TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                cost_usd     REAL,
                timestamp    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            # Step 4: Discovered Jobs (Multi-source)
            conn.execute("""
            CREATE TABLE IF NOT EXISTS discovered_jobs (
                fingerprint TEXT PRIMARY KEY,
                source      TEXT NOT NULL,
                source_id   TEXT,
                title       TEXT NOT NULL,
                company     TEXT NOT NULL,
                location    TEXT,
                url         TEXT UNIQUE,
                description TEXT,
                discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                relevance_score REAL,
                status      TEXT DEFAULT 'new'
            )
            """)
            conn.commit()

    def get_job_fingerprint(self, company: str, role: str, location: str = "") -> str:
        """Step 2 Milestone: "Job deduplication"."""
        key = f"{company.lower()}-{role.lower()}-{location.lower()}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def log_cost(
        self, model: str, input_tokens: int, output_tokens: int, cost_usd: float
    ):
        """Log LLM usage cost."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
            INSERT INTO llm_costs (model, input_tokens, output_tokens, cost_usd)
            VALUES (?, ?, ?, ?)
            """,
                (model, input_tokens, output_tokens, cost_usd),
            )
            conn.commit()

    def get_daily_cost(self):
        """Get total cost for today."""
        with sqlite3.connect(self.db_path) as conn:
            res = conn.execute("""
            SELECT SUM(cost_usd) FROM llm_costs 
            WHERE date(timestamp) = date('now')
            """).fetchone()
            return res[0] if res[0] else 0.0

    def add_application(
        self,
        company,
        role,
        cv_path,
        cl_path=None,
        ats_score=0.0,
        prompt_ver="v1",
        job_hash=None,
    ):
        """Log a new application attempt with deduplication check."""
        # Calculate SHA256 of CV for integrity
        sha256 = "N/A"
        try:
            with open(cv_path, "rb") as f:
                sha256 = hashlib.sha256(f.read()).hexdigest()
        except:
            pass

        app_id = f"{company}_{role}_{datetime.now().strftime('%Y%m%d_%H%M%S')}".lower().replace(
            " ", "_"
        )

        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    """
                INSERT INTO applications (id, job_hash, company, role, cv_path, cv_sha256, cl_path, ats_score, prompt_ver, applied_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        app_id,
                        job_hash,
                        company,
                        role,
                        cv_path,
                        sha256,
                        cl_path,
                        ats_score,
                        prompt_ver,
                        datetime.now(),
                        "draft",
                    ),
                )
                conn.commit()
                return app_id
            except sqlite3.IntegrityError:
                log.warning(
                    f"Duplicate job detected: {company} - {role}. Skipping log."
                )
                return None

    def update_status(self, app_id: str, status: str):
        """Update the status of an application."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE applications SET status = ? WHERE id = ?", (status, app_id)
            )
            conn.commit()

    def get_applications(self):
        """Fetch all applications for the dashboard."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM applications ORDER BY applied_at DESC"
            ).fetchall()

    def get_status_counts(self):
        """Get counts for the funnel chart."""
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("""
                SELECT status, COUNT(*) as count 
                FROM applications 
                GROUP BY status
            """).fetchall()

    def add_discovered_job(self, job_data: dict):
        """Add a newly discovered job to the DB. Returns True if new, False if duplicate."""
        fp = job_data.get("fingerprint")
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute(
                    """
                INSERT INTO discovered_jobs (fingerprint, source, source_id, title, company, location, url, description, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        fp,
                        job_data.get("source"),
                        job_data.get("source_id"),
                        job_data.get("title"),
                        job_data.get("company"),
                        job_data.get("location"),
                        job_data.get("url"),
                        job_data.get("description"),
                        job_data.get("relevance_score", 0.0),
                    ),
                )
                conn.commit()
                return True
            except sqlite3.IntegrityError:
                # log.debug(f"Job already exists in DB: {fp}")
                return False

    def get_new_jobs(self, limit: int = 50):
        """Fetch discovered jobs with status 'new'."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                """
                SELECT * FROM discovered_jobs 
                WHERE status = 'new' 
                ORDER BY discovered_at DESC 
                LIMIT ?
            """,
                (limit,),
            ).fetchall()

    def update_job_status(
        self, fingerprint: str, status: str, relevance_score: float = None
    ):
        """Update job status and optionally score."""
        with sqlite3.connect(self.db_path) as conn:
            if relevance_score is not None:
                conn.execute(
                    """
                    UPDATE discovered_jobs SET status = ?, relevance_score = ? 
                    WHERE fingerprint = ?
                """,
                    (status, relevance_score, fingerprint),
                )
            else:
                conn.execute(
                    """
                    UPDATE discovered_jobs SET status = ? 
                    WHERE fingerprint = ?
                """,
                    (status, fingerprint),
                )
            conn.commit()
