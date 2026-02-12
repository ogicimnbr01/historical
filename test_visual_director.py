
import sys
import os

# Add lambda directory to path
sys.path.append(os.path.join(os.getcwd(), 'lambda', 'video_creator'))

# Mock boto3 to avoid AWS calls
import unittest.mock
sys.modules['boto3'] = unittest.mock.MagicMock()

try:
    from stock_fetcher import generate_cinematic_prompt, enhance_prompt_for_era, clean_text_for_visuals
    print("[OK] Successfully imported stock_fetcher")
except ImportError as e:
    print(f"[ERROR] Failed to import stock_fetcher: {e}")
    sys.exit(1)

def test_visual_director():
    print("\n[TEST] VISUAL DIRECTOR LOGIC")
    print("=" * 60)

    test_cases = [
        {
            "text": "Scene 1: Narrator: The janissaries marched into battle. [Sound of drums]",
            "era": "ottoman",
            "desc": "Basic Ottoman Action"
        },
        {
            "text": "Cut to: Julius Caesar crossing the Rubicon. (Dramatic music)",
            "era": "roman",
            "desc": "Roman Event"
        },
        {
            "text": "A dark muddy trench with soldiers wearing gas masks.",
            "era": "ww1",
            "desc": "WW1 Setting"
        },
        {
            "text": "Mehmed II commanding his troops before the walls of Constantinople.",
            "era": "ottoman",
            "desc": "Famous Figure (Mehmed II)"
        }
    ]

    for i, case in enumerate(test_cases):
        print(f"\n[Test Case {i+1}]: {case['desc']}")
        print(f"   Input: '{case['text']}' (Era: {case['era']})")
        
        # 1. Test Cleaning
        cleaned = clean_text_for_visuals(case['text'])
        print(f"   [Cleaned]: '{cleaned}'")
        
        # 2. Test Cinematic Prompt Generation (Layer 1-3)
        cinematic = generate_cinematic_prompt(case['text'], case['era'])
        print(f"   [Cinematic Layer]: {cinematic[:100]}...")
        
        # 3. Test Full Enhancement (Safety + Style)
        final = enhance_prompt_for_era(case['text'], case['era'])
        print(f"   [Final Prompt]: {final}")
        
        # Validation
        if "Scene 1" in final or "Narrator" in final:
            print("   [FAILED]: Script artifacts remained!")
        elif "vertical" not in final:
            print("   [FAILED]: Missing vertical aspect ratio!")
        else:
            print("   [PASSED]")

if __name__ == "__main__":
    test_visual_director()
