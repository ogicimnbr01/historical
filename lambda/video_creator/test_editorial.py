import sys
import os
import json
from unittest.mock import MagicMock

# Add lambda directory to path
sys.path.append(os.path.abspath("lambda/video_creator"))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

from utils.editorial import find_viral_angle  # pyre-ignore[21]

def mock_invoke_bedrock(client, prompt, temperature, max_tokens):
    print(f"Mock Invoke: Prompt length {len(prompt)}")
    return json.dumps({
        "angle": "Suleiman executed his own son.",
        "reason": "Dramatic irony."
    })

def test_editorial():
    print("Testing editorial.find_viral_angle...")
    
    mock_client = MagicMock()
    wiki_text = "Suleiman the Magnificent was the tenth and longest-reigning Sultan of the Ottoman Empire..."
    
    result = find_viral_angle(mock_client, "Suleiman", wiki_text, mock_invoke_bedrock)
    
    if result and result["angle"] == "Suleiman executed his own son.":
        print("✅ Angle found correctly")
        print(f"Result: {result}")
    else:
        print("❌ Failed to find angle")
        print(f"Result: {result}")

if __name__ == "__main__":
    test_editorial()
