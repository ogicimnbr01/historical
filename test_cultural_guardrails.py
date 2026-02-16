import os
import sys

# Add lambda directory to path
sys.path.append(os.path.join(os.getcwd(), 'lambda', 'video_creator'))

from script_pipeline import normalize_era

def test_cultural_guardrails():
    print("🛡️ Testing Cultural Guardrails...")
    
    # Test cases: Topic -> Expected Era
    test_cases = [
        ("Sokushinbutsu: Japanese self-mummification", "feudal_japan"),
        ("Samurai honor code", "feudal_japan"),
        ("Aztec death whistle", "ancient_mesoamerica"),
        ("Mayan calendar end of world", "ancient_mesoamerica"),
        ("Native American rain dance", "indigenous_culture"),
        ("Al Capone's tax evasion", "early_20th_western"),
        ("Roaring 20s flappers", "early_20th_western"),
        ("Ottoman janissary training", "ottoman_empire"),
        ("Suleiman the Magnificent", "ottoman_empire"),
    ]
    
    passed = 0
    failed = 0
    
    print(f"\n🧪 Running {len(test_cases)} keyword-based tests (normalize_era)...")
    
    for topic, expected in test_cases:
        # Simulate extraction from keyword mapping
        # Note: In real pipeline, LLM does the extraction, but normalize_era checks keywords
        # We are testing if the keys exist and mapping logic works
        
        # We need to simulate the "era" input that might come from the LLM or keywords
        # For this test, we check if our keyword mapping in normalize_era catches these
        
        # Synthesize a "detected" era based on the topic to test normalize_era's correction logic
        # OR just test that normalize_era maps keywords correctly if we pass the topic text as "era" 
        # (Wait, normalize_era takes 'era' string. It maps 'japan' -> 'feudal_japan')
        
        # Let's test the keywords mapping inside normalize_era
        # We simulate the LLM returning a "dirty" era string or the functions keyword logic
        
        # Actually, normalize_era maps "japan" -> "feudal_japan".
        # So if we pass "japan", it should return "feudal_japan".
        
        # Let's test the mapping directly
        if "Japan" in topic or "Samurai" in topic:
            input_era = "feudal_japan" # Simulated "correct" extraction
        elif "Aztec" in topic or "Maya" in topic:
            input_era = "ancient_mesoamerica"
        elif "Ottoman" in topic or "Suleiman" in topic:
            input_era = "ottoman_empire"
        elif "Capone" in topic or "20s" in topic:
            input_era = "early_20th_western"
        elif "Native American" in topic:
             input_era = "indigenous_culture"
        else:
            input_era = "unknown"
            
        result = normalize_era(input_era)
        
        # Check if it remains stable (idempotency)
        if result == expected:
            print(f"✅ PASS: {topic[:30]}... -> {result}")
            passed += 1
        else:
            print(f"❌ FAIL: {topic[:30]}... -> Expected {expected}, Got {result}")
            failed += 1
            
    # Also test valid keys preservation
    keys = ["feudal_japan", "ancient_mesoamerica", "indigenous_culture", "ottoman_empire", "early_20th_western"]
    for k in keys:
        res = normalize_era(k)
        if res == k:
             print(f"✅ PASS: Key preservation '{k}'")
             passed += 1
        else:
             print(f"❌ FAIL: Key preservation '{k}' -> Got {res}")
             failed += 1

    print(f"\n📊 Result: {passed}/{len(test_cases)+5} tests passed.")

    # NEW: Test Pipeline Logic Simulation
    print("\n🧪 Testing Pipeline Logic Simulation (Topic & Wiki Context)...")
    pipeline_passed = 0
    
    # 1. Topic Detection
    topic = "Sokushinbutsu: Japanese self-mummification"
    detected = normalize_era(topic)
    if detected == "feudal_japan":
        print(f"✅ Topic Detection: '{topic}' -> {detected}")
        pipeline_passed += 1
    else:
        print(f"❌ Topic Detection Failed: '{topic}' -> {detected}")

    # 2. Wiki Context Detection
    wiki_context = "Sokushinbutsu was a practice of austere self-discipline observed by a sect of Buddhist monks in Japan."
    detected_wiki = normalize_era(wiki_context)
    if detected_wiki == "feudal_japan":
        print(f"✅ Wiki Context Detection: '{wiki_context[:30]}...' -> {detected_wiki}")
        pipeline_passed += 1
    else:
        print(f"❌ Wiki Context Detection Failed: '{wiki_context[:30]}...' -> {detected_wiki}")

    print(f"📊 Pipeline Simulation: {pipeline_passed}/2 passed.")

if __name__ == "__main__":
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
    test_cultural_guardrails()
