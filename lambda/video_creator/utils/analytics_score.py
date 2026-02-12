from typing import List, Dict, Optional
import math

def calculate_virality_score(video_data: Dict) -> float:
    """
    Calculate the "Virality Score" of a video based on Retention and Stopping Power.
    
    Formula:
    Final Score = (Retention Status * 1.5 + Stopping Power * 2.0) * log10(Views)
    
    - Likes are IGNORED (passive metric).
    - Retention (Avg View %) is weighted 1.5x.
    - Stopping Power (1 - Swipe Away Rate) is weighted 2.0x (CRITICAL).
    - Log(Views) acts as a multiplier to reward volume but prevent 1-view outliers.
    """
    try:
        views = int(video_data.get('views', 0))
        if views < 100:
            return 0.0
            
        # 1. Retention Score (The "Engagement" Engine)
        # avg_view_percentage is usually 0-100
        avg_view_pct = float(video_data.get('avg_view_percentage') or video_data.get('actual_retention') or 0.0)
        retention_score = avg_view_pct * 1.5
        
        # 2. Stopping Power (The "Hook" Engine)
        # viewed_vs_swiped is a new metric. If missing, assume 50% swipe rate (0.5).
        # We need "shownInFeed" to calc this, or rely on a stored 'swipe_rate'.
        # For now, if we don't have explicit 'swipe_rate', we use a default of 0.5 (50% stopped).
        # We assume 1.0 - swipe_rate = viewed_rate.
        swipe_rate = float(video_data.get('swipe_rate', 0.5))
        viewed_rate = max(0.0, 1.0 - swipe_rate) # Ensure non-negative
        stopping_power = viewed_rate * 100.0 * 2.0 # Scale to 0-100 then multiply by 2.0
        
        # 3. Volume Multiplier (The "Impact" Scaler)
        # log10(1000) = 3, log10(100,000) = 5. 
        # Limits the dominance of viral hits slightly compared to linear view count.
        volume_multiplier = math.log10(views) if views > 0 else 0
        
        final_score = (retention_score + stopping_power) * volume_multiplier
        
        return round(final_score, 2)
        
    except Exception as e:
        print(f"⚠️ Error calculating virality score: {e}")
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
