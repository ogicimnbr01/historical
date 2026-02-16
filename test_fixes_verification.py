"""Quick verification test for search_entity and float fixes"""
import sys
sys.path.insert(0, 'lambda/video_creator')

# Test 1: Float validation in models
print("=" * 60)
print("TEST 1: Pydantic Float Validation")
print("=" * 60)

from models import HookEvaluation, SectionEvaluation, FinalEvaluation

try:
    h = HookEvaluation(
        hook='test', 
        tension=1.5, 
        clarity=2.5, 
        scroll_stop=3.5, 
        word_count=10.5, 
        total=7.5, 
        fixes=[]
    )
    print(f"✅ HookEvaluation accepts float: tension={h.tension}, clarity={h.clarity}")
except Exception as e:
    print(f"❌ HookEvaluation FAILED: {e}")
    sys.exit(1)

try:
    s = SectionEvaluation(
        text='test', 
        clarity=1.5, 
        pacing=2.5, 
        punch=3.5, 
        total=7.5, 
        fixes=[]
    )
    print(f"✅ SectionEvaluation accepts float: clarity={s.clarity}, pacing={s.pacing}")
except Exception as e:
    print(f"❌ SectionEvaluation FAILED: {e}")
    sys.exit(1)

try:
    f = FinalEvaluation(
        hook_impact=8.5, 
        flow=7.5, 
        pacing=6.5, 
        punch=9.5, 
        total=8.0, 
        weakest_section='none', 
        fix_suggestion='none'
    )
    print(f"✅ FinalEvaluation accepts float: hook_impact={f.hook_impact}, pacing={f.pacing}")
except Exception as e:
    print(f"❌ FinalEvaluation FAILED: {e}")
    sys.exit(1)

# Test 2: Search entity in topic_selector
print("\n" + "=" * 60)
print("TEST 2: Search Entity in Topic Selector")
print("=" * 60)

from topic_selector import TOPIC_BUCKETS

ottoman_topics = [t for t in TOPIC_BUCKETS['ottoman']['topics'] if 'Mad Sultan' in t['topic']]
if ottoman_topics:
    topic = ottoman_topics[0]
    print(f"✅ Found Mad Sultan topic: {topic['topic']}")
    
    if 'search_entity' in topic:
        print(f"✅ search_entity present: '{topic['search_entity']}'")
        assert topic['search_entity'] == "Ibrahim of the Ottoman Empire", "Wrong search_entity value!"
    else:
        print("❌ search_entity field MISSING!")
        sys.exit(1)
else:
    print("❌ Mad Sultan topic NOT FOUND!")
    sys.exit(1)

# Test 3: Researcher accepts search_entity
print("\n" + "=" * 60)
print("TEST 3: Researcher Function Signature")
print("=" * 60)

import inspect
from utils.researcher import get_wiki_summary

sig = inspect.signature(get_wiki_summary)
params = list(sig.parameters.keys())

print(f"✅ get_wiki_summary parameters: {params}")

if 'search_entity' in params:
    print(f"✅ search_entity parameter present in signature")
else:
    print("❌ search_entity parameter MISSING from signature!")
    sys.exit(1)

# Test 4: Script pipeline accepts search_entity
print("\n" + "=" * 60)
print("TEST 4: Script Pipeline Function Signatures")
print("=" * 60)

from script_pipeline import generate_script_pipeline, generate_script_with_fallback

sig1 = inspect.signature(generate_script_pipeline)
params1 = list(sig1.parameters.keys())

sig2 = inspect.signature(generate_script_with_fallback)
params2 = list(sig2.parameters.keys())

if 'search_entity' in params1:
    print(f"✅ generate_script_pipeline has search_entity parameter")
else:
    print("❌ generate_script_pipeline MISSING search_entity!")
    sys.exit(1)

if 'search_entity' in params2:
    print(f"✅ generate_script_with_fallback has search_entity parameter")
else:
    print("❌ generate_script_with_fallback MISSING search_entity!")
    sys.exit(1)

print("\n" + "=" * 60)
print("🎉 ALL TESTS PASSED!")
print("=" * 60)
print("\nSummary:")
print("  ✅ Pydantic models accept float values (no more validation errors)")
print("  ✅ 'The Mad Sultan's swimming pool' has search_entity='Ibrahim of the Ottoman Empire'")
print("  ✅ get_wiki_summary() accepts search_entity parameter")
print("  ✅ Script pipeline functions accept search_entity parameter")
print("\n🚀 Ready for deployment!")
