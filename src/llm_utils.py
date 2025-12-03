from google import genai
import time
from pathlib import Path
from dotenv import load_dotenv
import os
from src.parsing_utils import read_txt

# --- Module-Level Variables  ---
_CLIENT = None
_MODEL_NAME = None 

class GeminiExhaustedException(Exception):
    """
    Raised when the Gemini API returns '429 Resource Exhausted' 
    too many times consecutively, indicating the daily quota is hit.
    """
    pass

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
                wait = min(base_delay * (2 ** overloads), 60.0)  # Exponential backoff, max 60s
                print(f"Gemini overloaded {overloads} times, retrying in {wait:.1f}s...")
                time.sleep(wait)
                continue
            
            elif exhausted:
                overloads = 0   
                exhaustions +=1
                if exhaustions >=5: # Stop everything
                    raise GeminiExhaustedException("Gemini daily quota likely exceeded (5x 429 errors).")
                # if <5 exhaustions, wait a fixed time and retry
                print(f"Gemini exhausted {exhaustions} times, waiting 1 minute and rerunning the code...")
                time.sleep(60)              
                continue          
            
            # Anything else, crash immediately
            raise e

# Reflexion loop
def reflect(original_content_list, previous_result, json_schema=None):
    """
    Asks the model to review its own work and fix potential errors.
    """
    # 1. Load the "Critique & Fix" instructions
    reflexion_prompt = read_txt(f'Prompts/Reflexion/reflexion.txt')
    
    # 2. Flatten the original input (which is a list of strings)
    flat_content = "\n\n".join([str(item) for item in original_content_list])
 
    # 3. Construct the "Review" payload
    new_content = [
        reflexion_prompt,
        f"--- [ORIGINAL INPUT DATA START] ---\n{flat_content}\n--- [ORIGINAL INPUT DATA END] ---",
        f"--- [DRAFT RESPONSE] ---\n{previous_result}"]

    # 4. Call API
    if json_schema:
        return with_retries(call_gemini_json, new_content, json_schema)
    else:
        return with_retries(call_gemini, new_content)