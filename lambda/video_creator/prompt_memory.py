"""
Prompt Memory Updater
=====================
Weekly update of DO/DON'T examples for writer/evaluator prompts.
Extracts hooks from top 5 and bottom 5 performers.

Rules:
- Keep examples short: hook + first sentence + 1-line reason
- Update weekly only (not daily to avoid prompt bloat)
- Store in autopilot_config for pipeline access
"""

import json
import os
import boto3
from datetime import datetime
from decimal import Decimal
from typing import Dict, List


# Configuration
METRICS_TABLE_NAME = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

# How many examples to keep
TOP_N = 5
BOTTOM_N = 5

# Maximum characters per example (keep prompts short)
MAX_EXAMPLE_LENGTH = 150


# =============================================================================
# DYNAMODB OPERATIONS
# =============================================================================

def get_autopilot_config(region_name: str = None) -> Dict:
    """Get current autopilot configuration."""
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        response = table.get_item(Key={"video_id": "autopilot_config"})
        return response.get("Item", {})
    except Exception as e:
        print(f"[WARNING] Failed to get autopilot config: {e}")
        return {}


def save_prompt_memory(do_examples: List[str], dont_examples: List[str], region_name: str = None) -> bool:
    """Save updated prompt memory to autopilot config."""
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        table.update_item(
            Key={"video_id": "autopilot_config"},
            UpdateExpression="SET prompt_memory = :pm, prompt_memory_updated = :ts",
            ExpressionAttributeValues={
                ":pm": {
                    "do_examples": do_examples,
                    "dont_examples": dont_examples
                },
                ":ts": datetime.now().isoformat()
            }
        )
        print(f"✅ Saved prompt memory: {len(do_examples)} DO, {len(dont_examples)} DON'T")
        return True
    except Exception as e:
        print(f"❌ Failed to save prompt memory: {e}")
        return False


def get_complete_videos(region_name: str = None, limit: int = 100) -> List[Dict]:
    """Get all completed, eligible videos sorted by retention."""
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        response = table.scan(
            FilterExpression="calibration_eligible = :eligible AND #st = :status",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":eligible": True,
                ":status": "complete"
            }
        )
        videos = response.get("Items", [])
        
        # Sort by actual_retention descending
        videos.sort(
            key=lambda x: float(x.get("actual_retention", 0)),
            reverse=True
        )
        
        return videos[:limit]
    except Exception as e:
        print(f"[ERROR] Failed to get complete videos: {e}")
        return []


# =============================================================================
# EXAMPLE EXTRACTION
# =============================================================================

def extract_example(video: Dict, is_success: bool) -> str:
    """
    Extract a concise example from a video.
    
    Format:
    "Hook text" (retention XX%) - 1-line analysis
    """
    hook = video.get("hook", "")
    actual = float(video.get("actual_retention", 0))
    
    # Get first sentence if hook is too long
    if len(hook) > 80:
        # Find first period or truncate
        period_idx = hook.find(". ")
        if period_idx > 0 and period_idx < 80:
            hook = hook[:period_idx + 1]
        else:
            hook = hook[:77] + "..."
    
    # Generate analysis based on KPI metrics
    kpi = video.get("hook_kpi", {})
    if isinstance(kpi, str):
        try:
            kpi = json.loads(kpi)
        except:
            kpi = {}
    
    clarity = kpi.get("instant_clarity", 5)
    curiosity = kpi.get("curiosity_gap", 5)
    swipe_risk = kpi.get("swipe_risk", 5)
    
    if is_success:
        # Why it worked
        if clarity >= 8:
            reason = "Clear premise instantly"
        elif curiosity >= 8:
            reason = "Strong curiosity trigger"
        else:
            reason = "Good hook-visual match"
    else:
        # Why it failed
        if clarity <= 5:
            reason = "Unclear premise"
        elif swipe_risk <= 4:
            reason = "High swipe risk / generic"
        else:
            reason = "Weak curiosity hook"
    
    example = f'"{hook}" ({actual:.0f}%) - {reason}'
    
    # Truncate if still too long
    if len(example) > MAX_EXAMPLE_LENGTH:
        example = example[:MAX_EXAMPLE_LENGTH - 3] + "..."
    
    return example


def generate_prompt_memory(videos: List[Dict]) -> Dict[str, List[str]]:
    """
    Generate DO and DON'T examples from videos.
    
    Returns:
        {"do_examples": [...], "dont_examples": [...]}
    """
    if not videos:
        return {"do_examples": [], "dont_examples": []}
    
    # Videos are already sorted by retention (high to low)
    top_videos = videos[:TOP_N]
    bottom_videos = videos[-BOTTOM_N:] if len(videos) >= BOTTOM_N else videos
    
    # Extract examples
    do_examples = []
    for video in top_videos:
        if float(video.get("actual_retention", 0)) >= 30:  # Only truly good ones
            example = extract_example(video, is_success=True)
            do_examples.append(example)
    
    dont_examples = []
    for video in bottom_videos:
        if float(video.get("actual_retention", 100)) <= 25:  # Only truly bad ones
            example = extract_example(video, is_success=False)
            dont_examples.append(example)
    
    return {
        "do_examples": do_examples[:TOP_N],
        "dont_examples": dont_examples[:BOTTOM_N]
    }


def format_prompt_injection(do_examples: List[str], dont_examples: List[str]) -> str:
    """
    Format examples for injection into writer/evaluator prompts.
    
    This is what gets added to the prompt.
    """
    sections = []
    
    if do_examples:
        sections.append("✅ DO (high retention examples):")
        for ex in do_examples:
            sections.append(f"- {ex}")
    
    if dont_examples:
        sections.append("")
        sections.append("❌ DON'T (low retention examples):")
        for ex in dont_examples:
            sections.append(f"- {ex}")
    
    return "\n".join(sections)


# =============================================================================
# MAIN LOGIC
# =============================================================================

def update_prompt_memory(region_name: str = None) -> Dict:
    """
    Main function: Extract and update prompt memory.
    
    Returns:
        Summary of what was done
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    
    # Get complete videos
    videos = get_complete_videos(region)
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "total_videos": len(videos),
        "action": "none"
    }
    
    if len(videos) < 10:
        result["action"] = "insufficient_data"
        result["message"] = f"Only {len(videos)} complete videos (need 10+)"
        return result
    
    # Generate examples
    memory = generate_prompt_memory(videos)
    do_examples = memory["do_examples"]
    dont_examples = memory["dont_examples"]
    
    result["do_count"] = len(do_examples)
    result["dont_count"] = len(dont_examples)
    
    if not do_examples and not dont_examples:
        result["action"] = "no_valid_examples"
        result["message"] = "No videos qualified as clear success/failure"
        return result
    
    # Save to DynamoDB
    if save_prompt_memory(do_examples, dont_examples, region):
        result["action"] = "updated"
        result["do_examples"] = do_examples
        result["dont_examples"] = dont_examples
        
        # Send notification
        send_memory_update_notification(do_examples, dont_examples, region)
    else:
        result["action"] = "save_failed"
    
    return result


def send_memory_update_notification(do_examples: List[str], dont_examples: List[str], region_name: str = None):
    """Send notification about prompt memory update."""
    if not SNS_TOPIC_ARN:
        return
    
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    sns = boto3.client("sns", region_name=region)
    
    message = f"""🧠 PROMPT MEMORY GÜNCELLENDİ

📊 Sistem en iyi/kötü hook'ları analiz etti

✅ {len(do_examples)} DO örnek eklendi
❌ {len(dont_examples)} DON'T örnek eklendi

Bu örnekler artık yeni video üretiminde
writer/evaluator prompt'larına eklenecek.

---
Sistem kendini eğitmeye devam ediyor.
"""
    
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"🧠 Prompt Memory Güncellendi (+{len(do_examples)} DO, +{len(dont_examples)} DON'T)",
            Message=message
        )
        print(f"📧 Memory update notification sent")
    except Exception as e:
        print(f"⚠️ Failed to send notification: {e}")


# =============================================================================
# LAMBDA HANDLER
# =============================================================================

def lambda_handler(event, context):
    """
    Lambda entry point for prompt memory updater.
    Triggered weekly (Sunday 21:00 UTC).
    """
    print("[PROMPT_MEMORY] Starting weekly prompt memory update...")
    
    region = os.environ.get("AWS_REGION_NAME", "us-east-1")
    
    try:
        result = update_prompt_memory(region)
        print(f"[PROMPT_MEMORY] Result: {json.dumps(result, default=str)}")
        return {"statusCode": 200, "body": json.dumps(result, default=str)}
    except Exception as e:
        print(f"[ERROR] Prompt memory update failed: {e}")
        return {"statusCode": 500, "body": str(e)}


if __name__ == "__main__":
    # Test locally
    print("Testing Prompt Memory Updater...")
    result = update_prompt_memory()
    print(json.dumps(result, indent=2, default=str))
