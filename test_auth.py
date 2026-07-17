import sys
import traceback
from fastapi.testclient import TestClient
from app.api import app

client = TestClient(app)
try:
    print("Sending request to /resumes with dummy token...")
    response = client.get("/resumes", headers={"Authorization": "Bearer dummy_token_abc123"})
    print("STATUS:", response.status_code)
    print("BODY:", response.text)
except Exception as e:
    print("EXCEPTION CAUGHT:")
    traceback.print_exc()
