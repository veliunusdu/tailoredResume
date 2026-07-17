import sys
import traceback
from fastapi.testclient import TestClient
from app.api import app
from app.auth import get_current_user

app.dependency_overrides[get_current_user] = lambda: "mock_user"

client = TestClient(app)
try:
    print("Sending request to /search-config...")
    response = client.get("/search-config")
    print("STATUS:", response.status_code)
    print("BODY:", response.text)
except Exception as e:
    print("EXCEPTION CAUGHT:")
    traceback.print_exc()

try:
    print("\nSending request to /jobs...")
    response = client.get("/jobs")
    print("STATUS:", response.status_code)
    print("BODY:", response.text)
except Exception as e:
    print("EXCEPTION CAUGHT:")
    traceback.print_exc()
