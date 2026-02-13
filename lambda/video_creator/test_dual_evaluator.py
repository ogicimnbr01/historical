"""
Dual Evaluator Test — Sonnet vs Haiku scoring comparison.
No image generation, no video creation. Just script pipeline evaluation.

Usage:
    cd c:\tokmak\broje\shorts\historical\lambda\video_creator
    python test_dual_evaluator.py
"""

import sys
import os
import json
import boto3  # pyre-ignore[21]

# Setup
os.environ.setdefault('AWS_REGION_NAME', 'us-east-1')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from script_pipeline import (  # pyre-ignore[21]
    get_bedrock_client,
    invoke_bedrock,
    evaluate_hooks_batch,
    evaluate_section_variants,
    evaluate_full_script,
    generate_hooks_batch,
    generate_section_variants,
    HAIKU_MODEL_ID,
    HOOK_THRESHOLD,
    SECTION_THRESHOLD,
    FINAL_THRESHOLD,
)


def separator(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}\n")


def test_hook_evaluation(client):
    """Test hook evaluation with both good and bad hooks."""
    separator("HOOK EVALUATION (Dual Jury)")
    
    # Mix of hooks: some should score high, some should get rejected
    test_hooks = [
        # Should score HIGH (contradiction/shock)
        "The deadliest weapon in World War I wasn't a gun—",
        # Should score MEDIUM (decent but not shocking)
        "Ancient Rome had an interesting legal system.",
        # Should score LOW (boring textbook opener)
        "Did you know that in 1789, the French Revolution began?",
    ]
    
    print(f"Testing {len(test_hooks)} hooks...")
    print(f"Threshold for approval: {HOOK_THRESHOLD}\n")
    
    for i, hook in enumerate(test_hooks):
        print(f"  Hook {i+1}: \"{hook}\"")
    
    print("\nEvaluating with dual jury (Sonnet + Haiku)...\n")
    
    results = evaluate_hooks_batch(client, test_hooks)
    
    print("\n--- RESULTS ---")
    for r in results:
        hook = r.get("hook", "?")
        total = r.get("total", 0)
        sonnet = r.get("sonnet_score", "N/A")
        haiku = r.get("haiku_score", "N/A")
        fixes = r.get("fixes", [])
        status = "APPROVED" if total >= HOOK_THRESHOLD else "REJECTED"
        
        print(f"\n  [{status}] \"{hook[:60]}...\"")
        print(f"    Sonnet: {sonnet}  |  Haiku: {haiku}  |  Final: {total}")
        if fixes:
            print(f"    Fixes: {', '.join(fixes[:3])}")


def test_section_evaluation(client):
    """Test section evaluation with dual jury."""
    separator("SECTION EVALUATION (Dual Jury)")
    
    hook = "The deadliest weapon in World War I wasn't a gun—"
    
    # Test CRISIS (context) section
    crisis_variants = [
        "1916. French soldiers are dying by the thousands. But not from bullets—from their own trenches. Disease is spreading faster than the German army.",
        "A long time ago during World War I, many soldiers died in various ways including disease and combat.",
    ]
    
    print(f"Hook: \"{hook}\"")
    print(f"Testing CONTEXT (Crisis) variants...\n")
    
    for i, v in enumerate(crisis_variants):
        print(f"  Variant {i+1}: \"{v[:80]}...\"")
    
    print(f"\nThreshold for approval: {SECTION_THRESHOLD}\n")
    
    results = evaluate_section_variants(client, "context", crisis_variants, hook)
    
    print("\n--- RESULTS ---")
    for r in results:
        text = r.get("text", "?")
        total = r.get("total", 0)
        sonnet = r.get("sonnet_score", "N/A")
        haiku = r.get("haiku_score", "N/A")
        status = "APPROVED" if total >= SECTION_THRESHOLD else "REJECTED"
        
        print(f"\n  [{status}] \"{text[:70]}...\"")
        print(f"    Sonnet: {sonnet}  |  Haiku: {haiku}  |  Final: {total}")


def test_full_script_evaluation(client):
    """Test full script evaluation with dual jury."""
    separator("FULL SCRIPT EVALUATION (Dual Jury)")
    
    # A decent script
    good_script = """The deadliest weapon in World War I wasn't a gun—

1916. The Western Front. Soldiers are rotting alive in flooded trenches. The real enemy isn't across no-man's land.

Trench foot. Gangrene. Rats the size of cats feeding on the dead. Commanders knew. They sent more men anyway.

And the weapon that killed more soldiers than any bullet? Mud. Just mud. And that's the real reason why—"""

    print("Testing GOOD script...")
    print(f"Threshold: {FINAL_THRESHOLD}\n")
    print(f"Script:\n{good_script}\n")
    
    result = evaluate_full_script(client, good_script)
    
    total = result.get("total", 0)
    sonnet = result.get("sonnet_score", "N/A")
    haiku = result.get("haiku_score", "N/A")
    weakest = result.get("weakest_section", "?")
    fix = result.get("fix_suggestion", "?")
    status = "APPROVED" if total >= FINAL_THRESHOLD else "NEEDS WORK"
    
    print(f"[{status}]")
    print(f"  Sonnet: {sonnet}  |  Haiku: {haiku}  |  Final: {total}")
    print(f"  Weakest section: {weakest}")
    print(f"  Fix suggestion: {fix}")


def test_hook_generation(client):
    """Test hook generation + evaluation cycle."""
    separator("HOOK GENERATION + DUAL EVALUATION")
    
    topic = "The Great Emu War of 1932"
    era = "Modern (20th Century)"
    
    print(f"Topic: {topic}")
    print(f"Era: {era}\n")
    
    print("Generating 3 hooks with Sonnet...")
    hooks = generate_hooks_batch(client, topic, era)
    
    print(f"\nGenerated hooks:")
    for i, h in enumerate(hooks):
        print(f"  {i+1}. \"{h}\"")
    
    print(f"\nEvaluating with dual jury...\n")
    results = evaluate_hooks_batch(client, hooks)
    
    print("\n--- RESULTS ---")
    for r in results:
        hook = r.get("hook", "?")
        total = r.get("total", 0)
        sonnet = r.get("sonnet_score", "N/A")
        haiku = r.get("haiku_score", "N/A")
        status = "APPROVED" if total >= HOOK_THRESHOLD else "REJECTED"
        try:
            gap = abs(float(sonnet) - float(haiku))
        except (ValueError, TypeError):
            gap = 0.0
        
        print(f"\n  [{status}] \"{hook}\"")
        print(f"    Sonnet: {sonnet}  |  Haiku: {haiku}  |  Final: {total}  |  Gap: {gap:.1f}")


if __name__ == "__main__":
    print("=" * 70)
    print("  DUAL EVALUATOR TEST — Sonnet vs Haiku")
    print(f"  Haiku Model: {HAIKU_MODEL_ID}")
    print("=" * 70)
    
    client = get_bedrock_client()
    
    # Run all tests
    test_hook_evaluation(client)
    test_section_evaluation(client)
    test_full_script_evaluation(client)
    test_hook_generation(client)
    
    separator("TEST COMPLETE")
    print("Check the [DUAL] logs above to see Sonnet vs Haiku scoring differences.")
    print("Large gaps (>2.0) indicate the closed loop was working against us.")
