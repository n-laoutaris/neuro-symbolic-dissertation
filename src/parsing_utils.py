import json

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


