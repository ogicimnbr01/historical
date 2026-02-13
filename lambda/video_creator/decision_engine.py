"""
Decision Engine - Self-Learning Autopilot
==========================================
Uses Thompson Sampling bandit to optimize production parameters.
Runs daily at 23:30 UTC via EventBridge.

Guardrails:
1. Update only when n >= 3 complete videos in last 24h (or sliding window 20)
2. Winsorize rewards: clamp(actual, 10, 85) + decay for older data
3. Recovery preset when 5 consecutive videos < 15% retention
"""

import json
import os
import random
import math
import boto3  # pyre-ignore[21]
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Tuple, Optional
from utils.analytics_score import calculate_virality_score  # pyre-ignore[21]
from topic_selector import TOPIC_BUCKETS  # pyre-ignore[21]


# Configuration
METRICS_TABLE_NAME = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

# Guardrail thresholds
MIN_VIDEOS_FOR_UPDATE = 3        # Minimum videos in last 24h to update weights
SLIDING_WINDOW_SIZE = 20         # Alternative: use last N complete videos
CONSECUTIVE_FAIL_THRESHOLD = 5   # Trigger recovery mode after N consecutive <15%
FAIL_RETENTION_THRESHOLD = 15    # What counts as "fail" for consecutive check

# Reward normalization
REWARD_MIN = 10   # Winsorize: anything below becomes 10
REWARD_MAX = 85   # Winsorize: anything above becomes 85

# Decay weights for older data (days old -> weight)
DECAY_WEIGHTS = {
    7: 1.0,    # 0-7 days: full weight
    14: 0.5,   # 8-14 days: half weight
    21: 0.25,  # 15-21 days: quarter weight
    999: 0.1   # 22+ days: minimal weight
}

# Safety bounds for weights
WEIGHT_BOUNDS = {
    "mode": {"QUALITY": (0.3, 0.9), "FAST": (0.1, 0.5)},
    "title": {"bold": (0.2, 0.8), "safe": (0.1, 0.6), "experimental": (0.05, 0.4)},
    "hook_family": {
        "contradiction": (0.1, 0.5),
        "revelation": (0.1, 0.5),
        "challenge": (0.1, 0.5),
        "contrast": (0.1, 0.5)
    }
}

# Maximum daily change per weight
MAX_DAILY_CHANGE = 0.1

# Explore rate bounds
EXPLORE_RATE_MIN = 0.1
EXPLORE_RATE_MAX = 0.3

# Recovery preset (used when in "do no harm" mode)
RECOVERY_PRESET = {
    "mode_weights": {"QUALITY": 0.9, "FAST": 0.1},
    "title_weights": {"bold": 0.2, "safe": 0.7, "experimental": 0.1},
    "hook_family_weights": {
        "contradiction": 0.4,
        "revelation": 0.3,
        "challenge": 0.2,
        "contrast": 0.1
    }
}


# =============================================================================
# DYNAMODB OPERATIONS
# =============================================================================

def get_autopilot_config(region_name: Optional[str] = None) -> Dict:
    """Get current autopilot configuration."""
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        response = table.get_item(Key={"video_id": "autopilot_config"})
        if "Item" in response:
            return response["Item"]
    except Exception as e:
        print(f"[WARNING] Failed to get autopilot config: {e}")
    
    # Return default config
    return get_default_config()


def get_default_config() -> Dict:
    """Return default autopilot configuration."""
    return {
        "video_id": "autopilot_config",
        "mode_weights": {"QUALITY": 0.7, "FAST": 0.3},
        "mode_weights": {"QUALITY": 0.7, "FAST": 0.3},
        "title_weights": {"bold": 0.5, "safe": 0.3, "experimental": 0.2},
        "category_weights": {k: v["weight"] for k, v in TOPIC_BUCKETS.items()},  # Default from selector
        "hook_family_weights": {
            "contradiction": 0.3,
            "revelation": 0.25,
            "challenge": 0.25,
            "contrast": 0.2
        },
        "explore_rate": 0.2,
        "prompt_memory": {
            "do_examples": [],
            "dont_examples": []
        },
        "bandit_state": {},  # Beta parameters for each arm
        "recovery_mode": False,
        "recovery_videos_remaining": 0,
        "last_updated": datetime.now().isoformat(),
        "update_history": []
    }


def save_autopilot_config(config: Dict, region_name: Optional[str] = None) -> bool:
    """Save updated autopilot configuration."""
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    # Convert floats to Decimal for DynamoDB
    config_cleaned = json.loads(json.dumps(config), parse_float=Decimal)
    config_cleaned["last_updated"] = datetime.now().isoformat()
    
    try:
        table.put_item(Item=config_cleaned)
        print(f"✅ Saved autopilot config")
        return True
    except Exception as e:
        print(f"❌ Failed to save autopilot config: {e}")
        return False


def get_complete_videos(region_name: Optional[str] = None, limit: int = 50) -> List[Dict]:
    """Get recently completed, eligible videos."""
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
        
        # Sort by analytics_fetched_at_utc descending
        videos.sort(
            key=lambda x: x.get("analytics_fetched_at_utc", ""),
            reverse=True
        )
        
        return videos[:limit]
    except Exception as e:
        print(f"[ERROR] Failed to get complete videos: {e}")
        return []


# =============================================================================
# REWARD CALCULATION
# =============================================================================

def calculate_reward(actual_retention: float, days_old: int) -> float:
    """
    Calculate normalized reward with winsorization and decay.
    
    Args:
        actual_retention: Raw retention percentage (0-100)
        days_old: How old the video is (for decay)
    
    Returns:
        Normalized reward (0-1)
    """
    # Winsorize: clamp to [10, 85]
    clamped = max(REWARD_MIN, min(REWARD_MAX, actual_retention))  # pyre-ignore[6]
    
    # Normalize to 0-1
    normalized = (clamped - REWARD_MIN) / (REWARD_MAX - REWARD_MIN)
    
    # Apply decay based on age
    decay = 0.1  # default for very old
    for days_threshold, weight in sorted(DECAY_WEIGHTS.items()):
        if days_old <= days_threshold:
            decay = weight
            break
    
    return normalized * decay


def get_video_age_days(video: Dict) -> int:
    """Calculate how many days old a video is."""
    fetch_date = video.get("analytics_fetched_at_utc", "")
    if not fetch_date:
        return 30  # Assume old if no date
    
    try:
        fetch_dt = datetime.fromisoformat(fetch_date.replace("Z", "+00:00"))
        now = datetime.now(fetch_dt.tzinfo) if fetch_dt.tzinfo else datetime.now()
        return (now - fetch_dt).days
    except:
        return 30


# =============================================================================
# THOMPSON SAMPLING BANDIT
# =============================================================================

def sample_beta(alpha: float, beta: float) -> float:
    """Sample from Beta distribution using Box-Muller approximation."""
    # Python's random doesn't have beta, so we approximate
    # For production, use numpy.random.beta if available
    try:
        import numpy as np  # pyre-ignore[21]
        return np.random.beta(alpha, beta)
    except ImportError:
        # Fallback: use gamma distribution relationship
        # Beta(a,b) = Gamma(a) / (Gamma(a) + Gamma(b))
        x = random.gammavariate(alpha, 1)
        y = random.gammavariate(beta, 1)
        return x / (x + y) if (x + y) > 0 else 0.5


def update_bandit_state(
    bandit_state: Dict,
    arm: str,
    reward: float
) -> Dict:
    """
    Update Beta parameters for an arm based on reward.
    
    Uses incremental update:
    alpha += reward * weight
    beta += (1 - reward) * weight
    """
    if arm not in bandit_state:
        bandit_state[arm] = {"alpha": 1.0, "beta": 1.0}
    
    bandit_state[arm]["alpha"] += reward
    bandit_state[arm]["beta"] += (1 - reward)
    
    return bandit_state


def calculate_new_weights(
    bandit_state: Dict,
    arms: List[str],
    current_weights: Dict,
    explore_rate: float,
    bounds: Dict[str, Tuple[float, float]]
) -> Dict[str, float]:
    """
    Calculate new weights using Thompson Sampling.
    
    1. Sample from each arm's Beta distribution
    2. Apply softmax to get weights
    3. Mix with explore rate (uniform)
    4. Apply bounds
    5. Limit daily change
    """
    # Sample from each arm
    samples = {}
    for arm in arms:
        state = bandit_state.get(arm, {"alpha": 1.0, "beta": 1.0})
        samples[arm] = sample_beta(state["alpha"], state["beta"])
    
    # Softmax to convert samples to weights
    max_sample = max(samples.values())
    exp_samples = {k: math.exp(v - max_sample) for k, v in samples.items()}
    sum_exp = sum(exp_samples.values())
    softmax_weights = {k: v / sum_exp for k, v in exp_samples.items()}
    
    # Mix with uniform (explore)
    uniform_weight = 1.0 / len(arms)
    mixed_weights = {
        arm: (1 - explore_rate) * softmax_weights[arm] + explore_rate * uniform_weight
        for arm in arms
    }
    
    # Apply bounds and limit daily change
    final_weights = {}
    for arm in arms:
        min_bound, max_bound = bounds.get(arm, (0.0, 1.0))
        current = current_weights.get(arm, uniform_weight)
        new = mixed_weights[arm]
        
        # Limit daily change
        change = new - current
        if abs(change) > MAX_DAILY_CHANGE:
            change = MAX_DAILY_CHANGE if change > 0 else -MAX_DAILY_CHANGE
        
        clamped = max(min_bound, min(max_bound, current + change))
        final_weights[arm] = round(float(clamped), 3)  # pyre-ignore[6]
    
    # Normalize to sum to 1
    total = sum(final_weights.values())
    if total > 0:  # pyre-ignore[58]
        final_weights = {k: round(float(v) / total, 3) for k, v in final_weights.items()}  # pyre-ignore[6]
    
    return final_weights  # pyre-ignore[7]


# =============================================================================
# GUARDRAILS
# =============================================================================

def check_consecutive_failures(videos: List[Dict]) -> int:
    """Count consecutive videos with retention < threshold at the start."""
    count = 0
    for video in videos:
        try:
            actual = float(video.get("actual_retention", 100))
            if actual < FAIL_RETENTION_THRESHOLD:
                count += 1
            else:
                break  # Stop at first success
        except:
            break
    return count


def should_enter_recovery_mode(videos: List[Dict]) -> bool:
    """Check if we should enter recovery mode."""
    consecutive = check_consecutive_failures(videos)
    return consecutive >= CONSECUTIVE_FAIL_THRESHOLD


def get_videos_in_last_24h(videos: List[Dict]) -> List[Dict]:
    """Filter videos to only those completed in last 24 hours."""
    cutoff = datetime.now() - timedelta(hours=24)
    recent = []
    
    for video in videos:
        fetch_date = video.get("analytics_fetched_at_utc", "")
        if fetch_date:
            try:
                fetch_dt = datetime.fromisoformat(fetch_date.replace("Z", "+00:00"))
                if fetch_dt.replace(tzinfo=None) >= cutoff:
                    recent.append(video)
            except:
                pass
    
    return recent


# =============================================================================
# MAIN DECISION LOGIC
# =============================================================================

def run_decision_engine(region_name: Optional[str] = None) -> Dict:
    """
    Main decision engine logic.
    
    Returns:
        Dict with action taken and details
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    
    # Get current config
    config = get_autopilot_config(region)
    
    # Get complete videos
    all_videos = get_complete_videos(region, limit=SLIDING_WINDOW_SIZE)
    recent_videos = get_videos_in_last_24h(all_videos)
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "total_complete": len(all_videos),
        "recent_24h": len(recent_videos),
        "action": "none",
        "changes": {}
    }
    
    # Check if in recovery mode
    if config.get("recovery_mode", False):
        remaining = config.get("recovery_videos_remaining", 0)
        if remaining > 0:
            # Still in recovery mode
            config["recovery_videos_remaining"] = remaining - 1
            save_autopilot_config(config, region)
            result["action"] = "recovery_mode"
            result["recovery_remaining"] = remaining - 1
            
            if remaining - 1 == 0:
                # Exit recovery mode
                config["recovery_mode"] = False
                save_autopilot_config(config, region)
                result["message"] = "Exiting recovery mode, returning to bandit"
            
            return result
    
    # Check for consecutive failures -> enter recovery mode
    if should_enter_recovery_mode(all_videos):
        print(f"⚠️ {CONSECUTIVE_FAIL_THRESHOLD} consecutive failures detected, entering recovery mode")
        
        config["recovery_mode"] = True
        config["recovery_videos_remaining"] = 3  # 3 videos in recovery
        config["mode_weights"] = RECOVERY_PRESET["mode_weights"]
        config["title_weights"] = RECOVERY_PRESET["title_weights"]
        config["hook_family_weights"] = RECOVERY_PRESET["hook_family_weights"]
        
        save_autopilot_config(config, region)
        
        # Send critical alert
        send_critical_alert(all_videos[:5], region)  # pyre-ignore[16]
        
        result["action"] = "entered_recovery"
        result["message"] = f"Entered recovery mode after {CONSECUTIVE_FAIL_THRESHOLD} consecutive low performers"
        return result
    
    # Check minimum data requirement (24h window)
    if len(recent_videos) < MIN_VIDEOS_FOR_UPDATE and len(all_videos) < SLIDING_WINDOW_SIZE:
        result["action"] = "insufficient_data"
        result["message"] = f"Only {len(recent_videos)} videos in 24h (need {MIN_VIDEOS_FOR_UPDATE})"
        return result
    
    # Use sliding window if not enough recent videos
    videos_for_update = recent_videos if len(recent_videos) >= MIN_VIDEOS_FOR_UPDATE else all_videos[:SLIDING_WINDOW_SIZE]  # pyre-ignore[16]
    
    # --- LOG-ONLY (SHADOW) MODE ---
    # First 50 videos: observe and learn, but do NOT change weights.
    # Bandit state is updated so knowledge accumulates for when threshold is reached.
    MIN_TOTAL_VIDEOS_FOR_BANDIT = 50
    
    if len(all_videos) < MIN_TOTAL_VIDEOS_FOR_BANDIT:
        bandit_state = config.get("bandit_state", {})
        
        for video in videos_for_update:
            try:
                actual = float(video.get("actual_retention", 0))
                days_old = get_video_age_days(video)
                reward = calculate_reward(actual, days_old)
                mode = video.get("mode", "QUALITY")
                title_type = video.get("title_variant_type", "safe")
                bandit_state = update_bandit_state(bandit_state, f"mode_{mode}", reward)
                bandit_state = update_bandit_state(bandit_state, f"title_{title_type}", reward)
            except Exception as e:
                print(f"[WARNING] Failed to process video in log-only mode: {e}")
        
        config["bandit_state"] = bandit_state
        save_autopilot_config(config, region)
        
        result["action"] = "log_only"
        result["message"] = (
            f"Shadow mode: {len(all_videos)}/{MIN_TOTAL_VIDEOS_FOR_BANDIT} videos completed. "
            f"Learning from {len(videos_for_update)} videos but NOT updating weights yet."
        )
        return result
    
    # Update bandit state and weights
    bandit_state = config.get("bandit_state", {})
    old_mode_weights = dict(config.get("mode_weights", {}))
    old_title_weights = dict(config.get("title_weights", {}))
    bandit_state = config.get("bandit_state", {})
    old_mode_weights = dict(config.get("mode_weights", {}))
    old_title_weights = dict(config.get("title_weights", {}))
    old_category_weights = dict(config.get("category_weights", {k: v["weight"] for k, v in TOPIC_BUCKETS.items()}))
    old_hook_weights = dict(config.get("hook_family_weights", {}))
    
    # --- 1. CATEGORY CALIBRATION (The "Real Score" Check) ---
    # Group videos by category and calculate real score
    category_videos = {}
    for v in all_videos: # Use full history for stability
        cat = v.get("era_category", v.get("category", "unknown")) # Support legacy
        if cat not in category_videos: category_videos[cat] = []
        category_videos[cat].append(v)
        
    # Explicitly type the dictionary to avoid narrow inference violations
    old_cats: Dict[str, float] = {}
    for k, v in old_category_weights.items():
        if isinstance(v, (int, float)):
             old_cats[k] = float(v)
             
    new_category_weights: Dict[str, float] = old_cats.copy()
    category_changes_log = []
    
    for cat, videos in category_videos.items():
        if cat not in new_category_weights: continue
        
        # USE VIRALITY SCORE (Retention * 1.5 + Stopping Power * 2.0)
        virality_score = calculate_virality_score(videos[0] if videos else {}) 
        # Note: calculate_virality_score expects a single video dict, but here we might want average?
        # The previous calculate_real_score took a LIST. 
        # Let's adjust calculate_virality_score to take a list or handle it here.
        # Actually, let's look at analytics_score.py again. 
        # It takes a single Dict. We need to aggregate.
        
        # Aggregate metrics for the category (using sum for cleaner type inference)
        # s_val calculation needs to be safe
        valid_videos = [v for v in videos if int(v.get('views', 0)) > 100]
        
        cat_total_score = sum(float(calculate_virality_score(v)) * float(int(v.get('views', 0))) for v in valid_videos)
        cat_total_weight = sum(float(int(v.get('views', 0))) for v in valid_videos)
        
        avg_score = cat_total_score / cat_total_weight if cat_total_weight > 0.0 else 0.0
        
        cat_key = str(cat)
        if avg_score > 35.0:
            # BOOST
            if avg_score > 500:
                 current_weight = float(new_category_weights.get(cat_key, 0.2))
                 new_category_weights[cat_key] = min(0.6, current_weight + 0.05)
                 category_changes_log.append(f"🚀 BOOST {cat_key}: Score {avg_score:.0f} -> +5%")
            # NERF
            elif avg_score < 250 and avg_score > 0:
                 current_weight = float(new_category_weights.get(cat_key, 0.2))
                 new_category_weights[cat_key] = max(0.1, current_weight - 0.05)
                 category_changes_log.append(f"📉 NERF {cat_key}: Score {avg_score:.0f} -> -5%")
            else:
                 category_changes_log.append(f"⚖️ KEEP {cat_key}: Score {avg_score:.0f}")
                 
    # Normalize category weights
    total_cat_weight = sum(new_category_weights.values())
    if total_cat_weight > 0:
        new_category_weights = {k: float(v) / float(total_cat_weight) for k, v in new_category_weights.items()}

    # --- 2. BANDIT UPDATE FOR MODES & TITLES ---
    for video in videos_for_update:
        try:
            actual = float(video.get("actual_retention", 0))
            days_old = get_video_age_days(video)
            reward = calculate_reward(actual, days_old)
            
            # Get the arms used for this video
            mode = video.get("mode", "QUALITY")
            title_type = video.get("title_variant_type", "safe")
            # hook_family not tracked yet, skip for now
            
            # Update bandit state
            bandit_state = update_bandit_state(bandit_state, f"mode_{mode}", reward)
            bandit_state = update_bandit_state(bandit_state, f"title_{title_type}", reward)
            
        except Exception as e:
            print(f"[WARNING] Failed to process video: {e}")
    
    config["bandit_state"] = bandit_state
    explore_rate = float(config.get("explore_rate", 0.2))
    
    # Calculate new weights for modes
    mode_arms = list(old_mode_weights.keys())
    mode_bandit = {arm: bandit_state.get(f"mode_{arm}", {"alpha": 1, "beta": 1}) for arm in mode_arms}  # pyre-ignore[16]
    new_mode_weights = calculate_new_weights(
        mode_bandit, mode_arms, old_mode_weights, explore_rate, WEIGHT_BOUNDS["mode"]
    )
    
    # Calculate new weights for titles
    title_arms = list(old_title_weights.keys())
    title_bandit = {arm: bandit_state.get(f"title_{arm}", {"alpha": 1, "beta": 1}) for arm in title_arms}  # pyre-ignore[16]
    new_title_weights = calculate_new_weights(
        title_bandit, title_arms, old_title_weights, explore_rate, WEIGHT_BOUNDS["title"]
    )
    
    # Record changes
    changes = {}
    if new_mode_weights != old_mode_weights:
        changes["mode_weights"] = {"old": old_mode_weights, "new": new_mode_weights}
        config["mode_weights"] = new_mode_weights
    
    if new_title_weights != old_title_weights:
        changes["title_weights"] = {"old": old_title_weights, "new": new_title_weights}
        config["title_weights"] = new_title_weights

    if new_category_weights != old_category_weights:
        changes["category_weights"] = {"old": old_category_weights, "new": new_category_weights}
        config["category_weights"] = new_category_weights
    
    # Save updated config
    if changes:
        # Add to history (keep last 30)
        history = config.get("update_history", [])
        history.append({
            "timestamp": datetime.now().isoformat(),
            "changes": changes
        })
        config["update_history"] = history[-30:]
        
        save_autopilot_config(config, region)
        
        # Send update notification
        send_update_notification(changes, len(videos_for_update), region)
        
        result["action"] = "updated"
        result["changes"] = changes
    else:
        result["action"] = "no_change"
        result["message"] = "No significant weight changes"
    
    return result


# =============================================================================
# NOTIFICATIONS
# =============================================================================

def send_update_notification(changes: Dict, n_videos: int, region_name: Optional[str] = None):
    """Send 'system updated' notification (no demoralizing metrics)."""
    if not SNS_TOPIC_ARN:
        return
    
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    sns = boto3.client("sns", region_name=region)
    
    # Format changes
    change_lines = []
    for category, data in changes.items():
        old = data.get("old", {})
        new = data.get("new", {})
        for key in new:
            old_val = old.get(key, 0)
            new_val = new.get(key, 0)
            if old_val != new_val:
                direction = "↑" if new_val > old_val else "↓"
                direction = "↑" if new_val > old_val else "↓"
                change_lines.append(f"   • {category}/{key}: {old_val:.0%} → {new_val:.0%} {direction}")
    
    # Add category specific logs if any
    # (We could pass category_changes_log here but for now just show weights)
    
    message = f"""🤖 AUTOPILOT GÜNCELLEMESI

📊 Sistem son {n_videos} videoyu analiz etti

🔧 Ayarlanan parametreler:
{chr(10).join(change_lines)}

✅ Sistem öğrenmeye devam ediyor

---
Bu mesaj otomatik olarak oluşturuldu.
Sistem kendini optimize etmektedir.
"""
    
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"🤖 Autopilot Güncellendi ({len(change_lines)} değişiklik)",
            Message=message
        )
        print(f"📧 Update notification sent")
    except Exception as e:
        print(f"⚠️ Failed to send update notification: {e}")


def send_critical_alert(failed_videos: List[Dict], region_name: Optional[str] = None):
    """Send critical alert when entering recovery mode."""
    if not SNS_TOPIC_ARN:
        return
    
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    sns = boto3.client("sns", region_name=region)
    
    message = f"""⚠️ DİKKAT GEREKEBİLİR

Son {CONSECUTIVE_FAIL_THRESHOLD} video üst üste retention < {FAIL_RETENTION_THRESHOLD}%

Sistem recovery moduna girdi:
• QUALITY: %90 (güvenli mod)
• safe title: %70
• 3 video boyunca bu ayarlar korunacak

Bu durum şunlardan kaynaklanabilir:
1. YouTube algoritması değişikliği
2. Tema/format uyumsuzluğu
3. Görsel-senaryo uyumsuzluğu

Sistem 3 video sonra normal öğrenmeye dönecek.

---
Bu mesaj otomatik üretildi.
"""
    
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"⚠️ Recovery Mode - {CONSECUTIVE_FAIL_THRESHOLD} Düşük Video",
            Message=message
        )
        print(f"📧 Critical alert sent")
    except Exception as e:
        print(f"⚠️ Failed to send critical alert: {e}")


# =============================================================================
# LAMBDA HANDLER
# =============================================================================

def lambda_handler(event, context):
    """
    Lambda entry point for decision engine.
    Triggered daily at 23:30 UTC.
    """
    print("[DECISION_ENGINE] Starting daily decision run...")
    
    region = os.environ.get("AWS_REGION_NAME", "us-east-1")
    
    try:
        result = run_decision_engine(region)
        print(f"[DECISION_ENGINE] Result: {json.dumps(result, default=str)}")
        return {"statusCode": 200, "body": json.dumps(result, default=str)}
    except Exception as e:
        print(f"[ERROR] Decision engine failed: {e}")
        return {"statusCode": 500, "body": str(e)}


if __name__ == "__main__":
    # Test locally
    print("Testing Decision Engine...")
    result = run_decision_engine()
    print(json.dumps(result, indent=2, default=str))
