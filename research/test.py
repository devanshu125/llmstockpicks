import json
import re

def extract_json_from_text(text):
    """
    Extracts JSON content from a given text. It handles both structured JSON (inside triple backticks)
    and inline JSON formats.
    
    :param text: The input text containing JSON.
    :return: Parsed JSON as a Python dictionary, or None if extraction fails.
    """
    try:
        # Attempt to extract JSON wrapped in triple backticks (```json ... ```)
        match = re.search(r"```json\s*([\s\S]+?)\s*```", text)
        
        if match:
            json_str = match.group(1).strip()  # Extract JSON part
        else:
            # Fallback: Extract inline JSON (first valid {...} block)
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                json_str = match.group().strip()
            else:
                return None  # No JSON found
        
        # Convert string to dictionary
        return json.loads(json_str)
    
    except json.JSONDecodeError:
        return None  # JSON extraction failed

# Example Usage
response_text = """
Here's the JSON output:

```json
{
  "score": 4,
  "thought_process": "The overall trend is upward, but recent behavior shows a potential downfall after peaking in late January. This requires further observation of the short-term volatility, especially considering an observed pull back, the current value looks like it is on a downward trend. Not enough to make a solid investable decision."
}
"""
parsed_json = extract_json_from_text(response_text)
print(parsed_json)