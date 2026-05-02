import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv(override=True)
key = os.getenv("GEMINI_API_KEY")

print(f"Testing Google Generative AI directly...")
genai.configure(api_key=key)

try:
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content("Hi")
    print("Success!")
    print(response.text)
except Exception as e:
    print(f"Failed: {e}")
