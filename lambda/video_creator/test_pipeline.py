"""
Test Script Pipeline - Local Testing
=====================================
Tests the new iterative script pipeline without deploying.
"""

import os
import json
import sys

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')  # pyre-ignore[16]

# Set environment for local testing
os.environ['S3_BUCKET_NAME'] = 'youtube-shorts-videos-20260119122010783300000001'
os.environ['AWS_REGION_NAME'] = 'us-east-1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

from script_pipeline import generate_script_pipeline, generate_script_with_fallback  # pyre-ignore[21]

def test_pipeline():
    """Test the full pipeline."""
    print("=" * 70)
    print("SCRIPT PIPELINE TEST")
    print("=" * 70)
    
    try:
        result = generate_script_pipeline()
        
        print("\n" + "=" * 70)
        print("✅ PIPELINE SUCCESS")
        print("=" * 70)
        
        # Display key info
        print(f"\n📌 TITLE: {result.get('title', 'N/A')}")
        print(f"📜 TOPIC: {result.get('original_topic', 'N/A')}")
        print(f"🎭 ERA: {result.get('era', 'N/A')} | MOOD: {result.get('mood', 'N/A')}")
        
        # Display voiceover
        print("\n" + "-" * 70)
        print("📝 VOICEOVER TEXT:")
        print("-" * 70)
        voiceover = result.get('voiceover_text', '')
        print(voiceover)
        print(f"\n   Word count: {len(voiceover.split())} words")
        
        # Display segments
        print("\n" + "-" * 70)
        print("🎬 SEGMENTS:")
        print("-" * 70)
        
        segment_names = ['HOOK', 'CONTEXT', 'BODY', 'OUTRO']
        for i, seg in enumerate(result.get('segments', [])):
            name = segment_names[i] if i < len(segment_names) else f'SEG{i}'
            print(f"\n  [{name}] {seg.get('start', 0)}s - {seg.get('end', 0)}s")
            print(f"  TEXT: {seg.get('text', '')}")
        
        # Display scores
        print("\n" + "-" * 70)
        print("📊 PIPELINE SCORES:")
        print("-" * 70)
        
        scores = result.get('pipeline_scores', {})
        print(f"  Hook:    {scores.get('hook_score', 'N/A')}")
        print(f"  Context: {scores.get('context_score', 'N/A')}")
        print(f"  Body:    {scores.get('body_score', 'N/A')}")
        print(f"  Outro:   {scores.get('outro_score', 'N/A')}")
        print(f"  Final:   {scores.get('final_score', 'N/A')}")
        
        if scores.get('weakest_section'):
            print(f"  ⚠️ Weakest: {scores.get('weakest_section')}")
        
        # Display stats
        print("\n" + "-" * 70)
        print("📈 PIPELINE STATS:")
        print("-" * 70)
        
        stats = result.get('pipeline_stats', {})
        for section, section_stats in stats.items():
            if isinstance(section_stats, dict):
                iters = section_stats.get('iterations', 'N/A')
                print(f"  {section}: {iters} iteration(s)")
        
        # Full JSON output
        print("\n" + "-" * 70)
        print("📄 FULL JSON:")
        print("-" * 70)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        print(f"\n❌ PIPELINE FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_fallback():
    """Test that fallback to old system works."""
    print("\n" + "=" * 70)
    print("FALLBACK TEST")
    print("=" * 70)
    
    try:
        # Test with pipeline disabled
        result = generate_script_with_fallback(use_pipeline=False)
        print(f"✅ Fallback system works: {result.get('title', 'N/A')}")
        return True
    except Exception as e:
        print(f"❌ Fallback failed: {e}")
        return False


def compare_systems():
    """Compare old vs new system outputs."""
    print("\n" + "=" * 70)
    print("SYSTEM COMPARISON")
    print("=" * 70)
    
    # New pipeline
    print("\n🆕 NEW PIPELINE:")
    try:
        new_result = generate_script_pipeline()
        print(f"   Title: {new_result.get('title', 'N/A')}")
        hook = new_result['segments'][0]['text'] if new_result.get('segments') else 'N/A'
        print(f"   Hook: {hook}")
        scores = new_result.get('pipeline_scores', {})
        print(f"   Scores: H={scores.get('hook_score')} C={scores.get('context_score')} B={scores.get('body_score')} O={scores.get('outro_score')}")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
    
    # Old system
    print("\n📦 OLD SYSTEM:")
    try:
        old_result = generate_script_with_fallback(use_pipeline=False)
        print(f"   Title: {old_result.get('title', 'N/A')}")
        hook = old_result['segments'][0]['text'] if old_result.get('segments') else 'N/A'
        print(f"   Hook: {hook}")
        print(f"   (No scoring in old system)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")


if __name__ == "__main__":
    # Parse arguments
    if len(sys.argv) > 1:
        mode = sys.argv[1]
        if mode == "fallback":
            test_fallback()
        elif mode == "compare":
            compare_systems()
        else:
            test_pipeline()
    else:
        test_pipeline()
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
