
import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add lambda/video_creator to path
sys.path.append(os.path.join(os.getcwd(), 'lambda', 'video_creator'))

from utils.editorial import normalize_era

def test_era_fixer():
    print("Testing Era Fixer Logic...")
    
    test_cases = [
        # Case 1: Suleiman context (1520) - Should become ottoman
        ("Suleiman the Magnificent ruled from 1520 to 1566.", "early_20th", "ottoman"),
        
        # Case 2: Renaissance context (16th century) - Should become ottoman
        ("This happened in the 16th century in Europe.", "modern", "ottoman"),
        
        # Case 3: Already correct - Should remain ottoman
        ("Mehmed II conquered Constantinople in 1453.", "ottoman", "ottoman"),
        
        # Case 4: Modern context - Should remain modern
        ("The Cold War started in 1947.", "modern", "modern"),
        
        # Case 5: 1400s - Should become ottoman
        ("In 1492 Columbus sailed the ocean blue.", "early_20th", "ottoman"),
        
        # Case 6: False positive check (15 minutes) - Should NOT change
        ("The video lasts 15 minutes.", "modern", "modern"),
        
        # Case 7: False positive check (Page 14) - Should NOT change
        ("See page 14 for details.", "early_20th", "early_20th"),

        # Case 8: 15th century
        ("Late 15th century architecture.", "early_20th", "ottoman"),
    ]
    
    passed = 0
    total = len(test_cases)
    
    for text, input_era, expected_era in test_cases:
        result = normalize_era(text, input_era)
        if result == expected_era:
            print(f"✅ PASS: Input era '{input_era}' -> '{result}' | Text: '{text[:30]}...'")
            passed += 1
        else:
            print(f"❌ FAIL: Input era '{input_era}' -> '{result}' (Expected: '{expected_era}') | Text: '{text[:30]}...'")
            
    print(f"\nResults: {passed}/{total} passed.")

if __name__ == "__main__":
    test_era_fixer()
