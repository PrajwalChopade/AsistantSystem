import os
import google.generativeai as genai
from app.config import settings

# Use API key from environment
genai.configure(api_key=settings.GEMINI_API_KEY)

print("✅ API key loaded:", bool(os.getenv("GEMINI_API_KEY")))
model = genai.GenerativeModel("models/gemini-1.5-flash")
response = model.generate_content("Say hello in one short sentence.")

print(response.text)