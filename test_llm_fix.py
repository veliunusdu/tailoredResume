import os
import litellm
from dotenv import load_dotenv

# Force clear any existing env var for testing
if "GEMINI_MODEL" in os.environ:
    del os.environ["GEMINI_MODEL"]

load_dotenv(override=True)

key = os.getenv("GEMINI_API_KEY")
model = "gemini-1.5-flash" # Force this one

print(f"Testing with model: {model}")
print(f"Key present: {'Yes' if key else 'No'}")

try:
    # Set both just in case
    os.environ["GEMINI_API_KEY"] = key
    os.environ["GOOGLE_API_KEY"] = key
    
    response = litellm.completion(
        model=f"gemini/{model}",
        messages=[{"role": "user", "content": "Hi, are you working?"}],
        api_key=key
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Failed: {e}")
