import json
import re
from typing import Optional, Dict

def find_viral_angle(client, topic: str, wiki_text: str, invoke_bedrock_fn) -> Optional[Dict[str, str]]:
    """
    Scans encyclopedic text to find the most 'TikTok-style' hook/angle.
    Returns dict with 'angle' and 'reason', or None if failed.
    """
    if not wiki_text:
        return None

    prompt = f"""
    You are a Viral Content Strategist for YouTube Shorts.
    
    INPUT TEXT (Historical Facts):
    {wiki_text[:2000]}
    
    YOUR TASK:
    Find the single most shocking, ironic, specific, or "weird" fact in this text about '{topic}'.
    
    RULES:
    1. IGNORE general biography (birth dates, reign years). Boring!
    2. HUNT FOR: Betrayals, irony, insane luxury, disgusting habits, secret deaths, paradoxes.
    3. OUTPUT FORMAT: A single VALID JSON object with 'angle' and 'reason'.
    
    Example Output:
    {{
        "angle": "Suleiman executed his own son Mustafa because he feared a coup, watching it from behind a curtain.",
        "reason": "High drama, father-son conflict, tragic irony."
    }}
    
    Return ONLY valid JSON.
    """
    
    try:
        # Use existing invoke_bedrock function passed from pipeline
        response = invoke_bedrock_fn(client, prompt, temperature=0.7, max_tokens=300)
        
        # Clean response
        clean_text = response.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        elif clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        
        # Parse JSON
        data = json.loads(clean_text)
        if "angle" in data:
            return data
            
    except Exception as e:
        print(f"⚠️ Angle Hunter Error: {e}")
        # Fallback: try to just use the response text if it looks like a sentence
        if len(response) < 200:
             return {"angle": response, "reason": "Fallback extraction"}
        
    return None

def normalize_era(wiki_text: str, detected_era: str) -> str:
    """
    Fixes Era Mismatch by checking for specific years in the text.
    Overrides the detected era if hard evidence (dates) points to a specific period.
    """
    if not wiki_text:
        return detected_era
        
    text_lower = wiki_text.lower()
    
    # Check for Renaissance/Ottoman years (1400s, 1500s, 1600s)
    # Using regex to avoid matching "15 seconds" or "page 14"
    # Matches: 1400-1699, 14th-17th century
    has_renaissance_dates = re.search(r'\b(14|15|16)\d{2}\b', text_lower) or \
                           re.search(r'\b(15|16|17)th (century|c\.)', text_lower)
                           
    if has_renaissance_dates:
        # If currently marked as modern/early_20th, force correction
        if detected_era in ["early_20th", "modern", "19th_century"]:
            print(f"🕰️ Era Mismatch Fixed: Detected dates in 1400-1600s. Switched {detected_era} -> ottoman")
            return "ottoman"  # Defaulting to ottoman as per Suleiman context, or could be 'early_modern'
            
    return detected_era

