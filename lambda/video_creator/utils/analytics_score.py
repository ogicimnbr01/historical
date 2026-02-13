from typing import List, Dict, Optional
import math

def calculate_virality_score(video_data: Dict) -> float:
    """
    Calculate the "Virality Score" of a video based on Retention and Stopping Power.
    
    Formula (v2 — Retention-First):
    base_score = (Retention * 1.5 + Stopping Power * 2.0)
    volume_factor = dampen(log10(views))  → 0.0 to 1.0
    final = base_score * (0.7 + 0.3 * volume_factor) * rewatch_multiplier
    
    Key changes from v1:
    - Views are a "consultant" not a "dictator" (max 30% influence via VOLUME_WEIGHT)
    - Rewatch bonus: avg_view_pct > 100% = video loops → up to 2x multiplier
    - Min views lowered from 100 to 50 for early-stage channels
    """
    # How much influence views have on the score (0.0 = none, 1.0 = full dictator)
    VOLUME_WEIGHT = 0.3
    
    try:
        views = int(video_data.get('views', 0))
        if views < 50:
            return 0.0
            
        # 1. Retention Score (The "Engagement" Engine)
        avg_view_pct = float(video_data.get('avg_view_percentage') or video_data.get('actual_retention') or 0.0)
        retention_score = avg_view_pct * 1.5
        
        # 2. Stopping Power (The "Hook" Engine)
        swipe_rate = float(video_data.get('swipe_rate', 0.5))
        viewed_rate = max(0.0, 1.0 - swipe_rate)
        stopping_power = viewed_rate * 100.0 * 2.0
        
        # 3. Volume Factor — dampened (no longer a raw multiplier)
        # Normalize log10(views) to 0-1 range:
        #   50 views  → ~0.0,  1K → ~0.33,  10K → ~0.67,  100K → ~1.0
        raw_log = math.log10(views) if views > 0 else 0
        volume_factor = min(1.0, max(0.0, (raw_log - 1.7) / 3.0))
        
        # Base score = pure quality (views-agnostic)
        base_score = retention_score + stopping_power
        
        # Apply dampened volume: score is 70-100% of base depending on views
        volume_adjusted = base_score * (1.0 - VOLUME_WEIGHT + VOLUME_WEIGHT * volume_factor)
        
        # 4. Rewatch Bonus — Perfect Loop reward
        # avg_view_percentage > 100 means viewers are looping the video
        rewatch_multiplier = 1.0
        if avg_view_pct > 100:
            # Every 10% above 100 = 15% bonus (e.g. 130% → 1.45x)
            excess = (avg_view_pct - 100) / 10.0
            rewatch_multiplier = min(2.0, 1.0 + excess * 0.15)
        
        final_score = volume_adjusted * rewatch_multiplier
        
        return round(final_score, 2)
        
    except Exception as e:
        print(f"Error calculating virality score: {e}")
        return 0.0

def calculate_weighted_average_retention(videos: List[Dict]) -> float:
    """Legacy helper for simple weighted retention if needed."""
    total_score = 0.0
    total_weight = 0.0
    for v in videos:
        views = int(v.get('views', 0))
        if views < 100: continue
        ret = float(v.get('actual_retention') or v.get('avg_view_percentage') or 0)
        total_score += ret * views
        total_weight += views
    return total_score / total_weight if total_weight > 0 else 0.0
