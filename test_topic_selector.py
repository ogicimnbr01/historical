
import sys
import os
import random

# Add lambda directory to path
sys.path.append(os.path.join(os.getcwd(), 'lambda', 'video_creator'))

try:
    from topic_selector import select_next_topic, TOPIC_BUCKETS
    print("[OK] Successfully imported topic_selector")
except ImportError as e:
    print(f"[ERROR] Failed to import topic_selector: {e}")
    sys.exit(1)

def test_topic_selection():
    print("\n[TEST] TOPIC SELECTION & DIVERSITY")
    print("=" * 60)

    # 1. Verify Anthropology Category Exists
    print(f"\n[1] Checking 'anthropology_and_culture' existence...")
    if "anthropology_and_culture" in TOPIC_BUCKETS:
        print("   [PASS] Category found.")
        topics = TOPIC_BUCKETS["anthropology_and_culture"]["topics"]
        print(f"   [INFO] Found {len(topics)} topics (e.g., '{topics[0]['topic']}')")
    else:
        print("   [FAIL] Category NOT found!")

    # 2. Verify Forced Diversity
    print(f"\n[2] Testing Forced Diversity (Blocking 'modern_war')")
    
    # Force 'modern_war' to have high weight to see if it gets blocked
    test_weights = {
        "modern_war": 0.9,
        "ancient": 0.05,
        "medieval": 0.05
    }
    
    # Run 100 trials, blocking 'modern_war'
    violations = 0
    for _ in range(100):
        _, cat = select_next_topic([], category_weights=test_weights, last_category="modern_war")
        if cat == "modern_war":
            violations += 1
            
    if violations == 0:
        print("   [PASS] 0/100 trials selected 'modern_war' when it was last_category.")
    else:
        print(f"   [FAIL] {violations}/100 trials selected 'modern_war' despite blocking!")

    # 3. Verify Selection of Anthropology
    print(f"\n[3] Testing Selection of 'anthropology_and_culture'")
    
    # Give it 100% weight to ensure it can be picked
    anthro_weight = {"anthropology_and_culture": 1.0}
    
    topic, cat = select_next_topic([], category_weights=anthro_weight, last_category="ancient")
    
    print(f"   [Selected]: Category='{cat}', Topic='{topic['topic']}'")
    
    if cat == "anthropology_and_culture":
        print("   [PASS] Successfully selected Anthropology category.")
    else:
        print(f"   [FAIL] Selected '{cat}' instead of Anthropology.")

if __name__ == "__main__":
    test_topic_selection()
