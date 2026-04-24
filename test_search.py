from ajas.search import search_jobs
import sys

try:
    results = search_jobs("python")
    print(f"Search results for 'python': {len(results)}")
    if results:
        print(f"First result: {results[0]['title']} at {results[0]['company']}")
except Exception as e:
    print(f"Error during search: {e}")
