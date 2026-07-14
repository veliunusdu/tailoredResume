"""
Thread-safe metrics collector for tracking job fetch, filter, and insert yields per source.
"""
import time
import uuid
import threading
from app.db import get_connection

class MetricsCollector:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.run_id = f"run_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        self.raw_counts = {}
        self.filtered_counts = {}
        self.inserted_counts = {}
        self.lock = threading.Lock()

    def add_raw(self, board: str, count: int):
        board = board.lower()
        with self.lock:
            self.raw_counts[board] = self.raw_counts.get(board, 0) + count

    def add_filtered(self, board: str, count: int):
        board = board.lower()
        with self.lock:
            self.filtered_counts[board] = self.filtered_counts.get(board, 0) + count

    def add_inserted(self, board: str, count: int):
        board = board.lower()
        with self.lock:
            self.inserted_counts[board] = self.inserted_counts.get(board, 0) + count

    def save_to_db(self):
        """Persist collected metrics to the source_metrics table."""
        now = time.time()
        # Collect all unique boards encountered
        with self.lock:
            all_boards = set(self.raw_counts.keys()) | set(self.filtered_counts.keys()) | set(self.inserted_counts.keys())
            
            with get_connection(self.user_id) as conn:
                cur = conn.cursor()
                for board in all_boards:
                    raw = self.raw_counts.get(board, 0)
                    filtered = self.filtered_counts.get(board, 0)
                    inserted = self.inserted_counts.get(board, 0)
                    
                    try:
                        cur.execute("""
                            INSERT INTO source_metrics 
                                (run_id, user_id, board, raw_count, filtered_count, inserted_count, fetched_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (self.run_id, self.user_id, board, raw, filtered, inserted, now))
                    except Exception:
                        pass
