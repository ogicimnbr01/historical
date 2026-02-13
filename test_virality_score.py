import sys
import os
import math

# Add lambda directory to path
sys.path.append(os.path.join(os.getcwd(), 'lambda', 'video_creator'))

from utils.analytics_score import calculate_virality_score

def test_virality_score():
    print("Testing Virality Score v2 (Retention-First)")
    print("Formula: base * (0.7 + 0.3*volume_factor) * rewatch_multiplier")
    print("=" * 70)
    
    test_cases = [
        {
            "name": "Viral Hit (10K views, 80% retention)",
            "data": {"views": 10000, "avg_view_percentage": 80.0, "swipe_rate": 0.3},
        },
        {
            "name": "Clickbait (50K views, 30% retention, 60% swipe)",
            "data": {"views": 50000, "avg_view_percentage": 30.0, "swipe_rate": 0.6},
        },
        {
            "name": "Niche Gem (150 views, 95% retention)",
            "data": {"views": 150, "avg_view_percentage": 95.0, "swipe_rate": 0.1},
        },
        {
            "name": "Perfect Loop (5K views, 130% retention = rewatch!)",
            "data": {"views": 5000, "avg_view_percentage": 130.0, "swipe_rate": 0.2},
        },
        {
            "name": "Extreme Loop (1K views, 200% retention)",
            "data": {"views": 1000, "avg_view_percentage": 200.0, "swipe_rate": 0.15},
        },
        {
            "name": "Too Few Views (30 views = below threshold)",
            "data": {"views": 30, "avg_view_percentage": 99.0, "swipe_rate": 0.0},
        },
        {
            "name": "Early Channel (60 views, 70% retention)",
            "data": {"views": 60, "avg_view_percentage": 70.0, "swipe_rate": 0.4},
        },
    ]
    
    for case in test_cases:
        score = calculate_virality_score(case['data'])
        d = case['data']
        
        # Calculate components manually for verification
        views = d['views']
        avg_pct = d['avg_view_percentage']
        swipe = d['swipe_rate']
        
        ret_score = avg_pct * 1.5
        stop_score = (1.0 - swipe) * 100.0 * 2.0
        base = ret_score + stop_score
        
        if views >= 50:
            vol_factor = min(1.0, max(0.0, (math.log10(views) - 1.7) / 3.0))
            vol_adjusted = base * (0.7 + 0.3 * vol_factor)
        else:
            vol_adjusted = 0.0
            vol_factor = 0.0
        
        rewatch = 1.0
        if avg_pct > 100:
            excess = (avg_pct - 100) / 10.0
            rewatch = min(2.0, 1.0 + excess * 0.15)
        
        expected = round(vol_adjusted * rewatch, 2)
        
        status = "PASS" if score == expected else "FAIL"
        
        print(f"\n[{status}] {case['name']}")
        print(f"  Views={views}, Retention={avg_pct}%, Swipe={swipe}")
        print(f"  base={base:.1f}, vol_factor={vol_factor:.3f}, rewatch={rewatch:.2f}x")
        print(f"  Score: {score} (expected: {expected})")
    
    # Comparison: show that retention matters more than views now
    print("\n" + "=" * 70)
    print("KEY COMPARISON: Does quality beat quantity?")
    
    quality_video = {"views": 500, "avg_view_percentage": 85.0, "swipe_rate": 0.2}
    quantity_video = {"views": 50000, "avg_view_percentage": 40.0, "swipe_rate": 0.5}
    
    q1 = calculate_virality_score(quality_video)
    q2 = calculate_virality_score(quantity_video)
    
    print(f"  Quality (500 views, 85% ret):  {q1}")
    print(f"  Quantity (50K views, 40% ret): {q2}")
    print(f"  Quality wins: {q1 > q2}")
    
    # Rewatch power demo
    print("\nREWATCH POWER:")
    normal = {"views": 3000, "avg_view_percentage": 75.0, "swipe_rate": 0.3}
    looped = {"views": 3000, "avg_view_percentage": 140.0, "swipe_rate": 0.3}
    
    n = calculate_virality_score(normal)
    l = calculate_virality_score(looped)
    
    print(f"  Normal (75% ret):   {n}")
    print(f"  Looped (140% ret):  {l}")
    print(f"  Loop bonus: {l/n:.2f}x")

if __name__ == "__main__":
    test_virality_score()
