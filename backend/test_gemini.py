from google import genai
from google.genai import types
import os

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

resp = client.models.generate_content(
    model="gemini-2.0-flash",
    contents="Say Hi"
)

print(resp.text)
