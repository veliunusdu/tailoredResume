"""
Supabase client — REMOVED.

This project now uses SQLite3 directly. Supabase is no longer used.
"""


def get_supabase():
    raise NotImplementedError(
        "Supabase has been removed from this project. "
        "All data is stored in SQLite (app.db). "
        "Use app.db functions directly instead."
    )
