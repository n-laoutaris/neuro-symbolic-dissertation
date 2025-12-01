import json
import sys

# Read txt file into a string (used for prompts)
def read_txt(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
    
    
# Read a JSON file and return it as string or raw JSON
def read_json(path, raw = False):
    with open(path, "r") as f:
        json_file = json.load(f)
    if (raw):
        return json_file
    # Else, convert JSON to string 
    return json.dumps(json_file, indent=2)


def print_progress(message):
    """
    Clears the current line and prints a new message.
    Works like a loading bar text.
    """
    # \r = Return to start of line
    # \033[K = Clear to end of line (ANSI escape code)
    sys.stdout.write(f"\r\033[K{message}")
    sys.stdout.flush()
