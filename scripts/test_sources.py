import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(ROOT))

from ajas.sources.dice import fetch_dice
from ajas.sources.greenhouse import fetch_greenhouse
from ajas.sources.lever import fetch_lever
from ajas.sources.remoteok import fetch_remoteok
from ajas.sources.remotive import fetch_remotive
from ajas.sources.wellfound import fetch_wellfound


def safe_call(fn, arg):
    try:
        items = fn(arg, limit=5)
        print(f"{fn.__name__}: {len(items)} items")
    except Exception as e:
        print(f"{fn.__name__} error: {e!r}")


if __name__ == "__main__":
    safe_call(fetch_remotive, "python")
    safe_call(fetch_remoteok, "python")
    # Test company-specific fetches (may return [] if company has no public board)
    safe_call(fetch_greenhouse, "cymertek")
    safe_call(fetch_lever, "cymertek")
    # Wellfound / Dice connectors are disabled by default (allow_scrape=False)
    safe_call(fetch_wellfound, "software engineer")
    safe_call(fetch_dice, "software engineer")
