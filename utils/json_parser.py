import re
import json
def json_parser(input_str: str):
    """Extract and parse JSON from a string."""
    pattern = r"\{.*\}"
    match = re.search(pattern, input_str, re.DOTALL)
    if match:
        json_string = match.group(0)
        try:
            json_out = json.loads(json_string)
            return json_out
        except json.JSONDecodeError:
            return json.JSONDecodeError(f"Failed to parse JSON: {json_string}")
    else:
        return None