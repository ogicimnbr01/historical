import sys
import os

# Add lambda/video_creator to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../lambda/video_creator')))

from stock_fetcher import enhance_prompt_for_era, ERA_STYLE_SUFFIXES

def test_era_styling():
    """Test that era-specific styling is correctly applied to prompts"""
    test_cases = [
        {
            "name": "Ottoman Era Styling",
            "prompt": "Sultan Suleiman at breakfast",
            "era": "ottoman",
            "expected_contains": ["Ottoman", "oriental", "painting"],
        },
        {
            "name": "Early 20th Century (Black & White)",
            "prompt": "Atatürk at dinner table",
            "era": "early_20th",
            "expected_contains": ["black and white", "vintage", "photograph"],
        },
        {
            "name": "Medieval Era",
            "prompt": "Mehmed the Conqueror",
            "era": "medieval",
            "expected_contains": ["medieval", "oil painting"],
        },
        {
            "name": "Ancient Era",
            "prompt": "Julius Caesar in the Senate",
            "era": "ancient",
            "expected_contains": ["ancient", "classical"],
        },
        {
            "name": "WW2 Era",
            "prompt": "Soldiers in battle",
            "era": "ww2",
            "expected_contains": ["World War II", "black and white"],
        },
        {
            "name": "Default/Unknown Era",
            "prompt": "Historical scene",
            "era": "unknown_era",
            "expected_contains": ["vintage", "archive", "photograph"],
        },
        {
            "name": "Vertical Composition Added",
            "prompt": "Napoleon portrait",
            "era": "19th_century",
            "expected_contains": ["9:16", "vertical"],
        },
    ]

    print("Testing Era-Specific Prompt Styling...\n")
    
    all_passed = True
    
    for case in test_cases:
        print(f"Testing: {case['name']}")
        print(f"  Input: '{case['prompt']}' (era: {case['era']})")
        
        result = enhance_prompt_for_era(case['prompt'], case['era'])
        print(f"  Result: '{result[:80]}...'")
        
        passed = True
        for expected in case["expected_contains"]:
            if expected.lower() not in result.lower():
                print(f"  ❌ FAILED: Expected '{expected}' in result")
                passed = False
                all_passed = False
        
        if passed:
            print("  ✅ PASSED")
        print("-" * 50)
    
    return all_passed


def test_era_coverage():
    """Test that all eras have defined styles"""
    print("\nTesting Era Coverage...\n")
    
    expected_eras = [
        "ancient", "medieval", "ottoman", "renaissance",
        "18th_century", "19th_century", "early_20th", 
        "ww1", "ww2", "modern"
    ]
    
    all_covered = True
    
    for era in expected_eras:
        if era in ERA_STYLE_SUFFIXES:
            print(f"  ✅ {era}: defined")
        else:
            print(f"  ❌ {era}: MISSING!")
            all_covered = False
    
    return all_covered


def test_script_gen_import():
    """Test that script_gen module imports correctly with new structure"""
    print("\nTesting Script Generator Import...\n")
    
    try:
        from script_gen import (
            generate_history_script,
            ERA_VISUAL_STYLES,
            SAMPLE_TOPICS,
            SYSTEM_PROMPT
        )
        
        print("  ✅ generate_history_script imported")
        print(f"  ✅ ERA_VISUAL_STYLES: {len(ERA_VISUAL_STYLES)} eras defined")
        print(f"  ✅ SAMPLE_TOPICS: {len(SAMPLE_TOPICS)} topics defined")
        print(f"  ✅ SYSTEM_PROMPT: {len(SYSTEM_PROMPT)} chars")
        
        # Check backward compatibility
        from script_gen import generate_absurd_script, generate_calm_script
        print("  ✅ Backward compatible functions available")
        
        return True
        
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_music_presets():
    """Test that music presets are correctly defined"""
    print("\nTesting Music Presets...\n")
    
    try:
        from music_fetcher import MUSIC_PRESETS, MOOD_TO_MUSIC
        
        expected_styles = [
            "epic_orchestral", "war_drums", "nostalgic_piano",
            "dramatic_strings", "ottoman_oriental", "ancient_classical",
            "medieval_court"
        ]
        
        all_defined = True
        for style in expected_styles:
            if style in MUSIC_PRESETS:
                preset = MUSIC_PRESETS[style]
                print(f"  ✅ {style}: base={preset['base_freq']}Hz")
            else:
                print(f"  ❌ {style}: MISSING!")
                all_defined = False
        
        print(f"\n  Mood mappings: {len(MOOD_TO_MUSIC)} defined")
        
        return all_defined
        
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


def test_voice_moods():
    """Test that voice moods are correctly defined"""
    print("\nTesting Voice Moods...\n")
    
    try:
        from tts import VOICE_BY_MOOD, DEFAULT_VOICES
        
        expected_moods = ["documentary", "epic", "nostalgic", "dramatic"]
        
        all_defined = True
        for mood in expected_moods:
            if mood in VOICE_BY_MOOD:
                voices = VOICE_BY_MOOD[mood]
                voice_ids = [v['id'] for v in voices]
                print(f"  ✅ {mood}: {', '.join(voice_ids)}")
            else:
                print(f"  ❌ {mood}: MISSING!")
                all_defined = False
        
        print(f"\n  Default voices: {[v['id'] for v in DEFAULT_VOICES]}")
        
        return all_defined
        
    except ImportError as e:
        print(f"  ❌ Import failed: {e}")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("HISTORY SHORTS - MODULE TESTS")
    print("=" * 60)
    
    results = []
    
    results.append(("Era Styling", test_era_styling()))
    results.append(("Era Coverage", test_era_coverage()))
    results.append(("Script Generator", test_script_gen_import()))
    results.append(("Music Presets", test_music_presets()))
    results.append(("Voice Moods", test_voice_moods()))
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {name}: {status}")
    
    all_passed = all(r[1] for r in results)
    print("\n" + ("✅ ALL TESTS PASSED!" if all_passed else "❌ SOME TESTS FAILED"))
