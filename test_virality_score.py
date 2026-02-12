import sys
import os
import math

# Add lambda directory to path
sys.path.append(os.path.join(os.getcwd(), 'lambda', 'video_creator'))

from utils.analytics_score import calculate_virality_score

def test_virality_score():
    print("🧪 Testing Virality Score Formula...")
    print("Formula: (Retention*1.5 + Stopping*2.0) * log10(Views)")
    
    test_cases = [
        {
            "name": "Viral Hit (High Retention, High Stopping)",
            "data": {"views": 10000, "avg_view_percentage": 80.0, "swipe_rate": 0.3},
            "expected_ret": 80 * 1.5, # 120
            "expected_stop": (1.0 - 0.3) * 100 * 2.0, # 70 * 2 = 140
            "expected_base": 260,
            "multiplier": 4.0 # log10(10000)
        },
        {
            "name": "Clickbait (High Views, Low Retention, High Swipes)",
            "data": {"views": 50000, "avg_view_percentage": 30.0, "swipe_rate": 0.6},
            "expected_ret": 30 * 1.5, # 45
            "expected_stop": (1.0 - 0.6) * 100 * 2.0, # 40 * 2 = 80
            "expected_base": 125,
            "multiplier": 4.7 # log10(50000)
        },
        {
            "name": "Niche Gem (Low Views, Perfect Retention)",
            "data": {"views": 150, "avg_view_percentage": 95.0, "swipe_rate": 0.1},
            "expected_ret": 95 * 1.5, # 142.5
            "expected_stop": (1.0 - 0.1) * 100 * 2.0, # 90 * 2 = 180
            "expected_base": 322.5,
            "multiplier": 2.17 # log10(150)
        }
    ]
    
    for case in test_cases:
        score = calculate_virality_score(case['data'])
        print(f"\nCase: {case['name']}")
        print(f"  Views: {case['data']['views']}")
        print(f"  Retention: {case['data']['avg_view_percentage']}%")
        print(f"  Swipe Rate: {case['data']['swipe_rate']}")
        print(f"  🏆 Score: {score}")
        
        # Simple validation
        expected = (case['expected_ret'] + case['expected_stop']) * case['multiplier']
        print(f"  (Expected approx: {expected:.2f})")

if __name__ == "__main__":
    test_virality_score()
