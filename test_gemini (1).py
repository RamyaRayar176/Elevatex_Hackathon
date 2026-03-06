import os
import google.generativeai as genai
from dotenv import load_dotenv
load_dotenv()
api_key = os.getenv('GEMINI_API_KEY')
print(f"Key loaded: {api_key is not None}")
if api_key:
    genai.configure(api_key=api_key)
    try:
        model = genai.GenerativeModel('gemini-2.5-flash-lite')
        response = model.generate_content("Say hello in one sentence.")
        print(f"SUCCESS: {response.text}")
    except Exception as e:
        print(f"Error with gemini-2.5-flash-lite: {e}")
else:
    print("No key found in .env")
