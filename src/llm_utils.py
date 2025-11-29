from google import genai
import time
from pathlib import Path
from dotenv import load_dotenv
import os

# --- Module-Level Variables  ---
_CLIENT = None
_MODEL_NAME = None 

def initialize_gemini_client(model_name):
    global _CLIENT, _MODEL_NAME
    _CLIENT = genai.Client()
    _MODEL_NAME = model_name
    
    load_dotenv()
    GEMINI_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_KEY:
        raise RuntimeError("GEMINI_API_KEY not found. Add it to a .env file in the notebook root.")
    
# Text generation in general
def call_gemini(content):
    response = _CLIENT.models.generate_content(
        model = _MODEL_NAME,
        contents = content
        )

    return response.text

# Document understanding 
def call_gemini_pdf(content, file_name):    
    # Retrieve and encode the PDF byte
    file_path = Path(file_name)

    # Upload the PDF using the File API
    content_file = _CLIENT.files.upload(file = file_path)

    response = _CLIENT.models.generate_content(
        model = _MODEL_NAME,
        contents=[content_file, content]
        )

    return response.text

# JSON structured output
def call_gemini_json(content, schema):
    response = _CLIENT.models.generate_content(
        model = _MODEL_NAME,
        contents=content,
        config={
            "response_mime_type": "application/json",
            "response_schema": schema
            }
        )

    return response.text

# Retry wrapper to combat model overload errors
def with_retries(func, *args, base_delay=4.0):
    overloads = 0    
    exhaustions = 0
    while True:
        try:
            return func(*args)
        except Exception as e:
            msg = str(e).lower()
            overloaded = "overloaded" in msg
            exhausted = "exhausted" in msg            
            if overloaded:
                overloads += 1
                wait = base_delay * (2 ** overloads)
                print(f"Gemini overloaded {overloads} times, retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            elif exhausted:
                exhaustions +=1
                print(f"Gemini exhausted {exhaustions} times, waiting 1 minute and rerunning the code...")
                time.sleep(60) 
                overloads = 0                
                continue          
            # Anything else
            raise
