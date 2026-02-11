"""
Similarity Dampener for History YouTube Shorts
Prevents repetitive content by tracking video history and enforcing variation.

Architecture:
- S3 append-only events: history/YYYY/MM/DD/<ISO_TIMESTAMP>_<uuid>.json
- Reads last N videos, sorted by timestamp (deterministic)
- Dynamic thresholds based on available history count
- Generates "similarity policy" to inject into prompt

Thresholds (DYNAMIC based on history count n):
- Hook: ceil(0.3 * n) → ban
- Ending: ceil(0.2 * n) → penalize (2x) then ban (3x)
- Break: ceil(0.3 * n) → ban
"""

import os
import json
import boto3  # pyre-ignore[21]
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from collections import Counter
import uuid


# Base thresholds (will be dynamically adjusted based on history count)
# Hook: 30% of history → ban (e.g., 3/10, 2/6, 1/4)
# Ending: 20% of history → penalize, 30% → ban (allows brand mottos to persist)
# Break: 30% of history → ban
HOOK_BAN_RATIO = 0.3
ENDING_PENALIZE_RATIO = 0.2
ENDING_BAN_RATIO = 0.3
BREAK_BAN_RATIO = 0.3
HISTORY_WINDOW = 10     # Look at last N videos
MIN_HISTORY_FOR_BAN = 4  # Don't ban if less than 4 videos (too little data)


# Hook pattern families (for classification) with EXAMPLES for prompt
HOOK_FAMILIES = {
    "contradiction": {
        "patterns": ["was a lie", "never happened", "got this wrong", "wasn't what", "weren't what"],
        "example": "X was a lie. / This never happened."
    },
    "revelation": {
        "patterns": ["the truth is", "history lied", "didn't die", "didn't say"],
        "example": "The truth is... / History lied about X."
    },
    "challenge": {
        "patterns": ["everyone remembers.*wrong", "nobody knows", "they never tell"],
        "example": "Everyone remembers this wrong. / Nobody knows that..."
    },
    "contrast": {
        "patterns": ["conquered.*but", "most powerful.*but", "greatest.*but"],
        "example": "He conquered X, but... / The greatest Y, but..."
    },
}

# Ending pattern families with EXAMPLES
ENDING_FAMILIES = {
    "poetic": {
        "patterns": ["legends lie", "sources speak", "history remembers", "truth echoes"],
        "example": "Legends lie. Sources speak."
    },
    "question": {
        "patterns": [r"\?$", "would you", "could you", "what do you think"],
        "example": "Would you have done the same?"
    },
    "ellipsis": {
        "patterns": [r"\.\.\.$", "never forget", "always remember"],
        "example": "And history... never forgot."
    },
    "short": {
        "patterns": ["and that's the truth", "the end", "history"],
        "example": "And that's the truth."
    },
}

# Break line patterns (tempo kırılmaları)
BREAK_PATTERNS = [
    "but here's what they don't tell you",
    "but here's the part they hide",
    "this is where the story breaks",
    "and that changes everything",
    "the real story",
    "what history doesn't mention",
]


def get_s3_client(region_name: Optional[str] = None) -> boto3.client:
    """Get S3 client"""
    return boto3.client('s3', region_name=region_name or os.environ.get('AWS_REGION', 'us-east-1'))


def get_history_bucket() -> str:
    """Get the S3 bucket name for video storage (same as main bucket)"""
    return os.environ.get('S3_BUCKET_NAME', 'youtube-shorts-videos')


def save_video_metadata(
    script: dict,
    region_name: Optional[str] = None
) -> str:
    """
    Save video metadata to S3 for similarity tracking.
    Uses append-only pattern: history/YYYY/MM/DD/<uuid>.json
    
    Args:
        script: The generated script dict
        region_name: AWS region
        
    Returns:
        S3 key of saved metadata
    """
    s3 = get_s3_client(region_name)
    bucket = get_history_bucket()
    
    # Extract patterns from script
    metadata = extract_patterns(script)
    
    # Generate S3 key with ISO timestamp prefix for deterministic sorting
    now = datetime.now(timezone.utc)
    iso_timestamp = now.strftime('%Y%m%dT%H%M%SZ')  # e.g., 20260202T193012Z
    event_id = uuid.uuid4().hex[:8]  # pyre-ignore[16]
    s3_key = f"history/{now.strftime('%Y/%m/%d')}/{iso_timestamp}_{event_id}.json"
    
    try:
        s3.put_object(
            Bucket=bucket,
            Key=s3_key,
            Body=json.dumps(metadata, ensure_ascii=False),
            ContentType='application/json'
        )
        print(f"📊 SIMILARITY: Saved video metadata to {s3_key}")
        return s3_key
    except Exception as e:
        print(f"⚠️ SIMILARITY: Failed to save metadata: {e}")
        return None  # pyre-ignore[7]


def extract_patterns(script: dict) -> dict:
    """
    Extract trackable patterns from a script.
    
    Returns:
        Dict with: timestamp, hook_pattern, ending_pattern, break_pattern, topic
    """
    metadata = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "title": script.get('title', ''),
        "topic": script.get('original_topic', ''),
        "hook_pattern": None,
        "hook_family": None,
        "ending_pattern": None,
        "ending_family": None,
        "break_pattern": None,
    }
    
    segments = script.get('segments', [])
    
    # Extract hook pattern from first segment
    if segments and len(segments) > 0:
        hook_text = segments[0].get('text', '').lower()
        metadata['hook_pattern'], metadata['hook_family'] = classify_hook(hook_text)
    
    # Extract ending pattern from last segment
    if segments and len(segments) > 0:
        ending_text = segments[-1].get('text', '').lower()
        metadata['ending_pattern'], metadata['ending_family'] = classify_ending(ending_text)
    
    # Extract break pattern from middle segments
    voiceover = script.get('voiceover_text', '').lower()
    metadata['break_pattern'] = classify_break(voiceover)
    
    return metadata


def classify_hook(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Classify hook text into pattern and family"""
    for family, family_data in HOOK_FAMILIES.items():
        for pattern in family_data["patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                return pattern, family
    return None, None


def classify_ending(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Classify ending text into pattern and family"""
    for family, family_data in ENDING_FAMILIES.items():
        for pattern in family_data["patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                return pattern, family
    return None, None


def classify_break(text: str) -> Optional[str]:
    """Find which break pattern is used"""
    for pattern in BREAK_PATTERNS:
        if pattern.lower() in text.lower():
            return pattern
    return None


def get_recent_history(
    limit: int = HISTORY_WINDOW,
    region_name: Optional[str] = None
) -> List[dict]:
    """
    Get the most recent video metadata from S3.
    Lists objects in history/ prefix and gets the most recent ones.
    
    Args:
        limit: Number of recent videos to retrieve
        region_name: AWS region
        
    Returns:
        List of metadata dicts, most recent first
    """
    s3 = get_s3_client(region_name)
    bucket = get_history_bucket()
    
    try:
        # List all history objects (sorted by key = chronological)
        response = s3.list_objects_v2(
            Bucket=bucket,
            Prefix='history/',
            MaxKeys=1000  # Get enough to find recent ones
        )
        
        if 'Contents' not in response:
            print("📊 SIMILARITY: No history found (first video)")
            return []
        
        # Sort by LastModified descending
        objects = sorted(
            response['Contents'],
            key=lambda x: x['LastModified'],
            reverse=True
        )[:limit]  # pyre-ignore[16]
        
        # Fetch each metadata file
        history = []
        for obj in objects:
            try:
                data = s3.get_object(Bucket=bucket, Key=obj['Key'])
                metadata = json.loads(data['Body'].read().decode('utf-8'))
                history.append(metadata)
            except Exception as e:
                print(f"⚠️ SIMILARITY: Failed to read {obj['Key']}: {e}")
        
        print(f"📊 SIMILARITY: Loaded {len(history)} recent videos")
        return history
        
    except Exception as e:
        print(f"⚠️ SIMILARITY: Failed to get history: {e}")
        return []


def analyze_similarity(history: List[dict]) -> dict:
    """
    Analyze history for overused patterns with DYNAMIC thresholds.
    
    Args:
        history: List of recent video metadata
        
    Returns:
        Analysis dict with counts, bans, penalizations, and escape hatch
    """
    n = len(history)
    
    # Empty result for no history
    if n == 0:
        return {
            "history_count": 0,
            "hook_counts": {},
            "ending_counts": {},
            "break_counts": {},
            "banned_hooks": [],
            "penalized_endings": [],  # New: soft warning
            "banned_endings": [],
            "banned_breaks": [],
            "preferred_hook_families": list(HOOK_FAMILIES.keys()),
            "preferred_ending_families": list(ENDING_FAMILIES.keys()),
            "escape_hatch": True,  # Allow anything if no history
        }
    
    # Calculate DYNAMIC thresholds based on history count
    import math
    hook_ban_threshold = max(1, math.ceil(HOOK_BAN_RATIO * n))
    ending_penalize_threshold = max(1, math.ceil(ENDING_PENALIZE_RATIO * n))
    ending_ban_threshold = max(2, math.ceil(ENDING_BAN_RATIO * n))
    break_ban_threshold = max(1, math.ceil(BREAK_BAN_RATIO * n))
    
    print(f"📊 SIMILARITY: Dynamic thresholds for n={n}: hook_ban={hook_ban_threshold}, ending_pen={ending_penalize_threshold}, ending_ban={ending_ban_threshold}, break_ban={break_ban_threshold}")
    
    # Count patterns
    hook_patterns = [h.get('hook_pattern') for h in history if h.get('hook_pattern')]
    ending_patterns = [h.get('ending_pattern') for h in history if h.get('ending_pattern')]
    break_patterns = [h.get('break_pattern') for h in history if h.get('break_pattern')]
    
    hook_counts = Counter(hook_patterns)  # pyre-ignore[6]
    ending_counts = Counter(ending_patterns)  # pyre-ignore[6]
    break_counts = Counter(break_patterns)  # pyre-ignore[6]
    
    # Determine bans and penalizations
    # Only ban if we have enough history (MIN_HISTORY_FOR_BAN)
    if n >= MIN_HISTORY_FOR_BAN:
        banned_hooks = [p for p, c in hook_counts.items() if c >= hook_ban_threshold]
        penalized_endings = [p for p, c in ending_counts.items() if ending_penalize_threshold <= c < ending_ban_threshold]
        banned_endings = [p for p, c in ending_counts.items() if c >= ending_ban_threshold]
        banned_breaks = [p for p, c in break_counts.items() if c >= break_ban_threshold]
        escape_hatch = False
    else:
        # Too little data - soft mode only
        print(f"📊 SIMILARITY: n={n} < {MIN_HISTORY_FOR_BAN}, using soft penalize only (no bans)")
        banned_hooks = []
        penalized_endings = [p for p, c in ending_counts.items() if c >= ending_penalize_threshold]
        banned_endings = []
        banned_breaks = []
        escape_hatch = True  # Allow fallback to banned patterns if needed
    
    # Find families that are underused (preferred)
    used_hook_families = [h.get('hook_family') for h in history if h.get('hook_family')]
    family_counts = Counter(used_hook_families)  # pyre-ignore[6]
    all_families = list(HOOK_FAMILIES.keys())
    preferred_hook_families = [f for f in all_families if family_counts.get(f, 0) < 2]
    if not preferred_hook_families:
        preferred_hook_families = all_families  # Reset if all used
    
    used_ending_families = [h.get('ending_family') for h in history if h.get('ending_family')]
    ending_family_counts = Counter(used_ending_families)  # pyre-ignore[6]
    all_ending_families = list(ENDING_FAMILIES.keys())
    preferred_ending_families = [f for f in all_ending_families if ending_family_counts.get(f, 0) < 2]
    if not preferred_ending_families:
        preferred_ending_families = all_ending_families
    
    return {
        "history_count": n,
        "hook_counts": dict(hook_counts),
        "ending_counts": dict(ending_counts),
        "break_counts": dict(break_counts),
        "banned_hooks": banned_hooks,
        "penalized_endings": penalized_endings,
        "banned_endings": banned_endings,
        "banned_breaks": banned_breaks,
        "preferred_hook_families": preferred_hook_families,
        "preferred_ending_families": preferred_ending_families,
        "escape_hatch": escape_hatch,
    }


def generate_similarity_policy(region_name: Optional[str] = None) -> dict:
    """
    Main function: Generate a similarity policy for the next video.
    
    Returns:
        Policy dict with banned patterns, penalizations, and recommendations
    """
    history = get_recent_history(region_name=region_name)
    analysis = analyze_similarity(history)
    
    n = analysis.get('history_count', 0)
    
    # Log analysis with dynamic info
    if analysis['banned_hooks']:
        print(f"🚫 SIMILARITY_ALERT: Banned hooks: {analysis['banned_hooks']}")
    if analysis.get('penalized_endings'):
        print(f"⚠️ SIMILARITY_WARN: Penalized endings (try to avoid): {analysis['penalized_endings']}")
    if analysis['banned_endings']:
        print(f"🚫 SIMILARITY_ALERT: Banned endings: {analysis['banned_endings']}")
    if analysis['banned_breaks']:
        print(f"🚫 SIMILARITY_ALERT: Banned breaks: {analysis['banned_breaks']}")
    
    print(f"✅ SIMILARITY: Preferred hook families: {analysis['preferred_hook_families']}")
    print(f"✅ SIMILARITY: Preferred ending families: {analysis['preferred_ending_families']}")
    
    if analysis.get('escape_hatch'):
        print(f"🔓 SIMILARITY: Escape hatch ACTIVE (n={n} < {MIN_HISTORY_FOR_BAN})")
    
    return analysis


def get_prompt_injection(policy: dict) -> str:
    """
    Generate prompt text to inject into Claude for similarity avoidance.
    Includes escape hatch for when banned patterns are the only option.
    
    Args:
        policy: The similarity policy from generate_similarity_policy()
        
    Returns:
        String to add to the prompt
    """
    lines = []
    
    # Banned patterns warning (hard ban)
    if policy.get('banned_hooks'):
        lines.append(f"🚫 BANNED HOOKS (do NOT use): {', '.join(policy['banned_hooks'])}")
    
    # Penalized endings (soft warning - try to avoid)
    if policy.get('penalized_endings'):
        lines.append(f"⚠️ OVERUSED ENDINGS (try to avoid): {', '.join(policy['penalized_endings'])}")
    
    if policy.get('banned_endings'):
        lines.append(f"🚫 BANNED ENDINGS (do NOT use): {', '.join(policy['banned_endings'])}")
    
    if policy.get('banned_breaks'):
        lines.append(f"🚫 BANNED BREAK LINES (do NOT use): {', '.join(policy['banned_breaks'])}")
    
    # Preferred families with EXAMPLES (key improvement)
    if policy.get('preferred_hook_families'):
        families = policy['preferred_hook_families'][:2]  # Top 2 preferred
        family_examples = []
        for fam in families:
            if fam in HOOK_FAMILIES:
                family_examples.append(f"{fam}: \"{HOOK_FAMILIES[fam]['example']}\"")  # pyre-ignore[6]
        if family_examples:
            lines.append(f"✅ USE THESE HOOK STYLES: " + " | ".join(family_examples))
    
    if policy.get('preferred_ending_families'):
        families = policy['preferred_ending_families'][:2]
        family_examples = []
        for fam in families:
            if fam in ENDING_FAMILIES:
                family_examples.append(f"{fam}: \"{ENDING_FAMILIES[fam]['example']}\"")  # pyre-ignore[6]
        if family_examples:
            lines.append(f"✅ USE THESE ENDING STYLES: " + " | ".join(family_examples))
    
    # Escape hatch - allow fallback if no good alternatives
    if policy.get('escape_hatch'):
        lines.append("🔓 ESCAPE HATCH: If banned patterns are the ONLY way to make a powerful hook, you may rewrite them into a different family while preserving meaning.")
    elif policy.get('banned_hooks') or policy.get('banned_endings'):
        # Even without escape hatch, provide fallback guidance
        lines.append("💡 If you cannot create a strong hook without banned patterns, rewrite the banned pattern using a DIFFERENT family's style.")
    
    if not lines:
        return ""  # No policy needed
    
    return "\n🎯 CONTENT VARIETY REQUIREMENTS:\n" + "\n".join(lines) + "\n"


# For testing
if __name__ == "__main__":
    print("Testing Similarity Dampener...")
    
    # Test pattern extraction
    test_script = {
        "title": "Test Video",
        "segments": [
            {"text": "Caesar's last words was a lie."},
            {"text": "Here's what history doesn't tell you."},
            {"text": "The senators attacked."},
            {"text": "Legends lie. Sources speak. Would you have trusted him?"},
        ],
        "voiceover_text": "Caesar's last words was a lie. Here's what history doesn't tell you. The senators attacked. Legends lie. Sources speak.",
        "original_topic": "Julius Caesar"
    }
    
    patterns = extract_patterns(test_script)
    print(f"Extracted patterns: {json.dumps(patterns, indent=2)}")
    
    # Test policy generation (will need S3)
    # policy = generate_similarity_policy()
    # print(f"Policy: {json.dumps(policy, indent=2)}")
