"""
Script Pipeline with Iterative Scoring - Bedrock Optimized
===========================================================
Generates YouTube Shorts scripts with quality scoring and refinement.
Uses batch generation to minimize API calls and costs.

Key Optimizations for AWS Bedrock:
- Batch hook generation (3 hooks per call)
- Batch section generation (2 variants per call)
- Separate temperatures (writer: 0.8, evaluator: 0.1)
- JSON fail-safe with repair attempts
- Exponential backoff for throttling
- Anchor examples for score calibration
- Autopilot prompt memory (DO/DON'T examples)
"""

import json
import re
import random
import time
import os
import boto3  # pyre-ignore[21]
from typing import Optional, Dict, List, Tuple, Any, Type, Callable
try:
    import json_repair  # pyre-ignore[21]
except ImportError:
    json_repair = None

try:
    from pydantic import ValidationError, BaseModel  # pyre-ignore[21]
    import models  # pyre-ignore[21]
except ImportError:
    ValidationError = None
    BaseModel = None
    models = None

# Import from existing modules for compatibility
from similarity_dampener import generate_similarity_policy, get_prompt_injection, save_video_metadata  # pyre-ignore[21]
from utils.researcher import get_wiki_summary  # pyre-ignore[21]
from utils.editorial import find_viral_angle, normalize_era as refine_era_from_text  # pyre-ignore[21]

# ============================================================================
# CONFIGURATION
# ============================================================================

# Temperature settings (critical for evaluation stability)
WRITER_TEMPERATURE = 0.8      # Creative generation
EVALUATOR_TEMPERATURE = 0.1   # Stable scoring

# Dual Evaluator: Haiku as second jury (breaks the closed loop)
HAIKU_MODEL_ID = os.environ.get(
    'BEDROCK_EVALUATOR_MODEL_ID',
    'us.anthropic.claude-haiku-4-5-20251001-v1:0'
)

# Token limits (keep costs down)
WRITER_MAX_TOKENS = 600
EVALUATOR_MAX_TOKENS = 400

# Quality thresholds (QUALITY mode - default)
HOOK_THRESHOLD = 9.0          # Hook must score >= 9.0
SECTION_THRESHOLD = 8.5       # Each section must score >= 8.5
FINAL_THRESHOLD = 8.5         # Combined script must score >= 8.5

# Dual jury scoring weights
SONNET_WEIGHT = 0.4            # Structure guardian weight
HAIKU_WEIGHT = 0.6             # Attention guardian weight
SONNET_FLOOR = 6.5             # Min Sonnet score to even consider publishing

# Iteration limits
HOOK_MAX_ITERATIONS = 5       # Max hook refinement rounds
SECTION_MAX_ITERATIONS = 3    # Max section refinement rounds

# Retry settings for throttling
MAX_RETRIES = 5
INITIAL_BACKOFF = 0.5         # seconds

# ============================================================================
# AUTOPILOT PROMPT MEMORY
# ============================================================================

# Global storage for DO/DON'T examples (set by handler via generate_script_with_fallback)
_prompt_memory = {}

def format_prompt_memory() -> str:
    """
    Format DO/DON'T examples for injection into writer/evaluator prompts.
    Returns empty string if no examples.
    """
    if not _prompt_memory:
        return ""
    
    do_examples = _prompt_memory.get("do_examples", [])
    dont_examples = _prompt_memory.get("dont_examples", [])
    
    if not do_examples and not dont_examples:
        return ""
    
    sections = ["\n\n📊 LEARNED FROM REAL PERFORMANCE:"]
    
    if do_examples:
        sections.append("✅ DO (high retention):")
        for ex in do_examples[:5]:  # pyre-ignore[16]
            sections.append(f"- {ex}")
    
    if dont_examples:
        sections.append("❌ DON'T (low retention):")
        for ex in dont_examples[:5]:  # pyre-ignore[16]
            sections.append(f"- {ex}")
    
    return "\n".join(sections)
JITTER_MAX = 0.3              # Max random jitter (0-30% of backoff)

# Cost control limits
MAX_API_CALLS_PER_VIDEO = 30  # Increased from 18 to 30 for quality scripts
MAX_REPAIR_ATTEMPTS = 1       # JSON repair limit per call

# Tie-breaker settings (when scores are close)
SCORE_TIE_THRESHOLD = 0.3     # Scores within 0.3 are considered tied

# ============================================================================
# PIPELINE MODES
# ============================================================================

# FAST mode: higher throughput, slightly relaxed thresholds
FAST_MODE_CONFIG = {
    "hook_threshold": 8.7,
    "section_threshold": 8.3,
    "final_threshold": 8.3,
    "hook_max_iterations": 3,
    "section_max_iterations": 2,
    "max_api_calls": 12
}

# QUALITY mode: stricter thresholds but optimized iterations
# Reduced iterations to prevent API call waste on hard topics
QUALITY_MODE_CONFIG = {
    "hook_threshold": 9.0,
    "section_threshold": 8.5,
    "final_threshold": 8.5,
    "hook_max_iterations": 3,    # Reduced from 5 - reroll topic if stuck
    "section_max_iterations": 2,  # Reduced from 3
    "max_api_calls": 30
}

# Active mode config (set per run)
_active_config = QUALITY_MODE_CONFIG.copy()

def set_pipeline_mode(mode: str = "quality"):
    """Set pipeline mode: 'fast' or 'quality'."""
    global _active_config
    if mode.lower() == "fast":
        _active_config = FAST_MODE_CONFIG.copy()
        print("⚡ Pipeline mode: FAST (relaxed thresholds, 12 max calls)")
    else:
        _active_config = QUALITY_MODE_CONFIG.copy()
        print("🎯 Pipeline mode: QUALITY (strict thresholds, 18 max calls)")
    return _active_config

def get_threshold(key: str) -> float:
    """Get current threshold value based on active mode."""
    return _active_config.get(key, QUALITY_MODE_CONFIG.get(key))  # pyre-ignore[7]

# ============================================================================
# ERA STANDARDIZATION (prevents label drift)
# ============================================================================

ERA_ENUM = [
    "ancient",        # Before 500 AD (Egypt, Rome, Greece, China)
    "medieval",       # 500-1500 AD (Knights, Vikings, Crusades)
    "ottoman",        # 1300-1922 AD (Ottoman Empire specific)
    "early_modern",   # 1500-1800 AD (Renaissance, Colonization)
    "19th_century",   # 1800-1900 AD (Napoleon, Industrial Revolution)
    "early_20th",     # 1900-1945 AD (World Wars, Depression)
    "modern",         # 1945-2000 AD (Cold War, Space Age)
    "21st",           # 2000+ AD (Digital Age)
]

def normalize_era(era: str) -> str:
    """Normalize era to standard enum value."""
    if not era:
        return "early_20th"  # Default
    
    era_lower = era.lower().strip()
    
    # Direct match
    if era_lower in ERA_ENUM:
        return era_lower
    
    # Fuzzy matching
    era_mapping = {
        "ancient": ["egypt", "roman", "greek", "classical", "bronze", "iron"],
        "medieval": ["middle age", "knight", "viking", "crusade", "feudal"],
        "ottoman": ["ottoman", "turkish", "sultan", "constantinople"],
        "early_modern": ["renaissance", "colonial", "enlightenment"],
        "19th_century": ["napoleon", "victorian", "industrial", "1800"],
        "early_20th": ["ww1", "ww2", "world war", "1900", "1920", "1930", "1940"],
        "modern": ["cold war", "1950", "1960", "1970", "1980", "1990"],
        "21st": ["2000", "internet", "digital", "21st"],
    }
    
    for standard_era, keywords in era_mapping.items():
        if any(kw in era_lower for kw in keywords):
            return standard_era
    
    return "early_20th"  # Default fallback

# ============================================================================
# DIVERSITY GATE (enforcement, not just logging)
# ============================================================================

DIVERSITY_GATE_THRESHOLD = 0.65   # Reject topic if similarity >= this
ENTITY_COOLDOWN_COUNT = 30        # Same entity blocked for N videos

def check_diversity_gate(topic: str, topic_entity: str, region_name: Optional[str] = None) -> dict:
    """
    Check if topic passes diversity gate.
    
    Returns:
        dict with 'allowed', 'similarity', 'reason'
    """
    try:
        from similarity_dampener import get_recent_videos, calculate_similarity  # pyre-ignore[21]
        
        recent = get_recent_videos(count=ENTITY_COOLDOWN_COUNT, region_name=region_name)
        
        if not recent:
            return {"allowed": True, "similarity": 0.0, "reason": "no_history"}
        
        # Check entity cooldown
        recent_entities = [v.get("topic_entity", "") for v in recent]
        if topic_entity.lower() in [e.lower() for e in recent_entities]:
            return {
                "allowed": False, 
                "similarity": 1.0, 
                "reason": f"entity_cooldown:{topic_entity}"
            }
        
        # Calculate content similarity
        max_similarity = 0.0
        for video in recent:
            sim = calculate_similarity(topic, video.get("topic", ""))
            if sim > max_similarity:
                max_similarity = sim
        
        if max_similarity >= DIVERSITY_GATE_THRESHOLD:
            return {
                "allowed": False,
                "similarity": max_similarity,
                "reason": f"similarity_too_high:{max_similarity:.2f}"
            }
        
        return {"allowed": True, "similarity": max_similarity, "reason": "passed"}
        
    except ImportError:
        # similarity_dampener not available
        return {"allowed": True, "similarity": 0.0, "reason": "dampener_unavailable"}
    except Exception as e:
        # Don't block on errors, just warn
        print(f"⚠️ Diversity gate check failed: {e}")
        return {"allowed": True, "similarity": 0.0, "reason": f"error:{str(e)[:30]}"}  # pyre-ignore[16]

# ============================================================================
# HOOK KPI PROXY METRICS
# ============================================================================

HOOK_KPI_EVALUATOR_PROMPT = """Evaluate this hook for REAL viewer behavior prediction.

HOOK: "{hook}"

Score these YouTube-behavior predictors (0-10, be realistic):

1. instant_clarity: In 1.5 seconds, does viewer know WHO is at risk and WHAT the threat is?
   - 10 = Crystal clear, no second thought needed
   - 5 = Needs a moment to process
   - 0 = Confusing, viewer will scroll

2. curiosity_gap: Does viewer NEED to know what happens next?
   - 10 = "I cannot scroll away without knowing"
   - 5 = "Mildly interested"
   - 0 = "Don't care"

3. swipe_risk: How likely is viewer to swipe away in first 2 seconds?
   - 10 = Very unlikely to swipe (strong hook)
   - 5 = 50/50 chance
   - 0 = Will definitely swipe

Return ONLY valid JSON:
{{"instant_clarity": X, "curiosity_gap": X, "swipe_risk": X, "predicted_retention": X}}

predicted_retention = rough estimate of % viewers who will watch past 3 seconds (0-100)
"""

def evaluate_hook_kpi(client, hook: str) -> dict:
    """
    Evaluate hook with KPI proxy metrics that predict real viewer behavior.
    
    These metrics are more predictive of YouTube performance than 
    abstract "shock" or "tension" scores.
    """
    prompt = HOOK_KPI_EVALUATOR_PROMPT.format(hook=hook)
    
    response = invoke_bedrock(client, prompt, temperature=0.1, max_tokens=150)
    result = parse_json_safe(response, client, prompt, validation_model=models.HookKPI if models else None)
    
    if result:
        return {
            "instant_clarity": result.get("instant_clarity", 5),
            "curiosity_gap": result.get("curiosity_gap", 5),
            "swipe_risk": result.get("swipe_risk", 5),
            "predicted_retention": result.get("predicted_retention", 50)
        }
    
    return {
        "instant_clarity": 5,
        "curiosity_gap": 5,
        "swipe_risk": 5,
        "predicted_retention": 50
    }

# ============================================================================
# VISUAL RELEVANCE SCORE
# ============================================================================

VISUAL_RELEVANCE_PROMPT = """Score the visual-script alignment.

SCRIPT HOOK: "{hook}"
VISUAL PROMPT: "{visual_prompt}"

Question: Will the FIRST FRAME visually match what the hook describes?

Score 0-10:
- 10 = Perfect match (hook says "soldiers fighting", visual shows soldiers fighting)
- 5 = Related but not exact (hook says "soldiers fighting", visual shows soldiers standing)
- 0 = Completely unrelated (hook says "soldiers fighting", visual shows a library)

Return ONLY valid JSON:
{{"visual_relevance": X, "mismatch_risk": "none|low|medium|high", "suggestion": "..."}}
"""

def evaluate_visual_relevance(client, hook: str, visual_prompt: str) -> dict:
    """
    Score how well the visual prompt matches the hook.
    Mismatch causes swipe even if hook is good.
    """
    prompt = VISUAL_RELEVANCE_PROMPT.format(hook=hook, visual_prompt=visual_prompt)
    
    response = invoke_bedrock(client, prompt, temperature=0.1, max_tokens=150)
    result = parse_json_safe(response, client, prompt, validation_model=models.VisualRelevance if models else None)
    
    if result:
        return {
            "visual_relevance": result.get("visual_relevance", 5),
            "mismatch_risk": result.get("mismatch_risk", "medium"),
            "suggestion": result.get("suggestion", "")
        }
    
    return {"visual_relevance": 5, "mismatch_risk": "unknown", "suggestion": ""}

# ============================================================================
# TITLE GENERATION (3 variants for testing)
# ============================================================================

TITLE_GENERATOR_PROMPT = """Generate 3 YouTube Shorts title variants for this video.

HOOK: "{hook}"
TOPIC: "{topic}"

Rules:
- Max 60 characters each
- Use curiosity/shock triggers
- No clickbait that doesn't deliver
- Include 1 safe, 1 bold, 1 experimental

Return ONLY valid JSON:
{{"titles": ["safe title", "bold title", "experimental title"]}}
"""

def generate_title_variants(client, hook: str, topic: str) -> list:
    """
    Generate 3 title variants for A/B testing.
    Returns: ["safe", "bold", "experimental"]
    """
    prompt = TITLE_GENERATOR_PROMPT.format(hook=hook, topic=topic)
    
    response = invoke_bedrock(client, prompt, temperature=0.7, max_tokens=200)
    result = parse_json_safe(response, client, prompt, validation_model=models.TitleBatch if models else None)
    
    if result and "titles" in result:
        return result["titles"][:3]
    
    # Fallback: use topic as title
    return [topic[:60], topic[:60], topic[:60]]  # pyre-ignore[16]

# ============================================================================
# ANCHOR EXAMPLES FOR SCORE CALIBRATION
# ============================================================================

HOOK_ANCHOR_EXAMPLES = """
CALIBRATION EXAMPLES (be a ruthless 15-year-old TikTok judge):

SCORE 9-10 (You literally STOPPED scrolling — "wait WHAT?!"):
- "Australia sent soldiers with machine guns to kill birds. The birds won." (9.5 — bizarre + contradiction)
- "Cleopatra lived closer to the iPhone than to the pyramids." (9.5 — brain-breaking paradox)
- "A king killed his best friend over a dinner argument." (9.0 — shocking + specific)

SCORE 4-5 (You yawned and swiped):
- "Did you know Napoleon wasn't actually short?" (4.0 — boring question opener, SWIPE)
- "In 1453, the Ottoman Empire conquered Constantinople." (4.5 — history textbook, SWIPE)
- "History has many interesting stories to tell." (2.0 — literally nothing to stop for)
"""

SECTION_ANCHOR_EXAMPLES = """
CALIBRATION EXAMPLES (would a 15-year-old with ADHD keep watching?):

SCORE 9-10 (CRISIS -> ESCALATION -> can't look away):
- CRISIS: "1932. Crops dying. Farmers desperate. The enemy? Twenty thousand emus." (9.0 — vivid threat, specific stakes)
- ESCALATION: "They fired. Emus scattered. Bullets hit nothing. The birds didn't even flinch." (9.5 — it gets WORSE, punchy rhythm)
- TWIST+PUNCH: "The army retreated. The emus kept eating. And that's the real reason why—" (9.0 — ironic + loops back)

SCORE 5-6 (You'd swipe before the sentence ends):
- CRISIS: "This happened in Australia a long time ago when there were problems." (5.0 — zero urgency)
- ESCALATION: "The soldiers tried to shoot the emus but it didn't work very well." (5.5 — no punch, flat)
- TWIST+PUNCH: "And that's how the story ended." (4.0 — no twist, no loop, DEAD ending)
"""

# ============================================================================
# PROMPTS
# ============================================================================

HOOK_GENERATOR_PROMPT = """You are a viral YouTube Shorts hook writer. Generate 3 different hooks for this topic.

TOPIC: {topic}
ERA: {era}

{context_block}

{angle_block}

RULES:
- Each hook: 6-12 words
- Must create "Wait, WHAT?!" reaction
- Use: contradiction, shock, accusation, or paradox
- NO: "Did you know", "In [year]", "Have you ever wondered"
- Make them AGGRESSIVE scroll-stoppers
- IF SOURCE TEXT PROVIDED: Use ONLY facts from Source Text.
- PERFECT LOOP: The hook MUST end with a dangling clause, unfinished thought, or open question that the OUTRO will complete. Think of it as a sentence that starts at the end of the video and loops seamlessly to the beginning.
  Do NOT end abruptly with a dash (--). Make the hook a complete thought that naturally flows FROM the outro's last words.
  Example: Hook ends with "...and that's the real reason why" -> Outro completes it -> viewer loops back.

Return ONLY valid JSON:
{{"hooks": ["hook1", "hook2", "hook3"]}}"""

HOOK_EVALUATOR_PROMPT = """You are a 15-year-old with SEVERE ADHD scrolling TikTok at 2 AM. You have ZERO patience. If a hook doesn't SHOCK you in 1.5 seconds, you swipe immediately.

You only stop for: bizarre contradictions, "wait WHAT?!" moments, things that sound dangerously wrong, or stuff so weird your brain can't process it fast enough to swipe.

You DO NOT care about: educational value, historical accuracy, eloquent writing, or clever wordplay. You care about RAW shock value and instant confusion.

{anchor_examples}

HOOKS TO EVALUATE:
{hooks_json}

SCORING RUBRIC (be BRUTAL — you're bored and sleepy):
- wtf_factor (0-4): "Wait, WHAT?!" reaction strength. 0 = boring. 4 = you said it out loud.
- scroll_stop (0-3): Would you PHYSICALLY stop your thumb? Be honest.
- clarity (0-2): Understood in 1.5 seconds while half-asleep? If you have to re-read, it's 0.
- boredom_risk (0-1): 1 = does NOT sound like a textbook. 0 = sounds like school.

CRITICAL: Respond ONLY with valid JSON. No markdown formatting (no ```json). No preamble, explanations, or concluding remarks. Just the raw JSON object. All scores MUST be between 0 and 10.
{{
  "evaluations": [
    {{"hook": "...", "wtf_factor": X, "scroll_stop": X, "clarity": X, "boredom_risk": X, "total": X, "fixes": ["..."]}},
    ...
  ]
}}"""

HOOK_REFINER_PROMPT = """Rewrite this hook. A real 19-year-old viewer gave this feedback:

VIEWER ATTENTION DIAGNOSTICS:
- Skip Reason: {skip_reason}
- Attention Drops At Word: "{drop_word}"
- Additional Issues: {fixes}

ORIGINAL HOOK: {hook}

REWRITE CONSTRAINTS:
- 6-12 words, punchy, scroll-stopping.
- SPECIFICALLY fix the drop point — that word/phrase must change or disappear.
- The new hook must create a curiosity gap the old one lacked.
- Do NOT just rephrase — change the PSYCHOLOGY of the hook.

Return ONLY the new hook text, nothing else."""

SECTION_GENERATOR_PROMPT = """Generate 2 variants of the {section_type} section for this YouTube Short.

HOOK (already approved): {hook}
TOPIC: {topic}
ERA: {era}

SECTION TYPE: {section_type}
{context_block}
{angle_block}
{section_rules}

Return ONLY valid JSON:
{{"variants": ["variant1", "variant2"]}}"""

SECTION_EVALUATOR_PROMPT = """You are a 15-year-old with ADHD watching this video on your phone. You're already 3 seconds in (you stayed for the hook). Now evaluate if these {section_type} sections keep you watching or make you swipe.

Remember: you have the attention span of a goldfish on caffeine. If a single sentence feels like a lecture, you're GONE.

{anchor_examples}

HOOK THAT KEPT YOU (for context): {hook}

VARIANTS TO EVALUATE:
{variants_json}

SCORING RUBRIC (your thumb is hovering over the screen):
- drama (0-4): Does it feel like something TERRIBLE is about to happen? Stakes rising?
- pace (0-3): Are sentences punchy (5-8 words)? Or long boring paragraphs?
- rewatch (0-3): Would you watch this part AGAIN? Would you show a friend?

CRITICAL: Respond ONLY with valid JSON. No markdown formatting (no ```json). No preamble, explanations, or concluding remarks. Just the raw JSON object. All scores MUST be between 0 and 10.
{{
  "evaluations": [
    {{"text": "...", "drama": X, "pace": X, "rewatch": X, "total": X, "fixes": ["..."]}},
    ...
  ]
}}"""

SECTION_REFINER_PROMPT = """Rewrite this {section_type} section. A real 19-year-old viewer gave this feedback:

VIEWER ATTENTION DIAGNOSTICS:
- Skip Reason: {skip_reason}
- Attention Drops At Word: "{drop_word}"
- Additional Issues: {fixes}

ORIGINAL: {text}
HOOK CONTEXT: {hook}

REWRITE CONSTRAINTS:
- Fix the drop point — that word/phrase must change or disappear.
- Every sentence must hit HARDER than the last.
- Keep it punchy, short sentences, high impact.
- Do NOT just rephrase — change the ENERGY.

Return ONLY the improved text, nothing else."""

FINAL_EVALUATOR_PROMPT = """You just watched this entire YouTube Short as a bored teenager. Score it 0-10.

FULL SCRIPT:
---
{full_script}
---

RUBRIC (be honest — would you watch it TWICE?):
- hook_impact (0-2): Did the first sentence make you stop? Or did you almost swipe?
- escalation (0-3): Did it get MORE intense? Or did it plateau after the hook?
- pacing (0-3): Every sentence punchy? Or did you zone out somewhere?
- loop_power (0-2): Does the ending make you want to watch from the beginning AGAIN?

CRITICAL: Respond ONLY with valid JSON. No markdown formatting (no ```json). No preamble, explanations, or concluding remarks. Just the raw JSON object. All scores MUST be between 0 and 10.
{{"hook_impact": X, "escalation": X, "pacing": X, "loop_power": X, "total": X, "weakest_section": "hook|context|body|outro", "fix_suggestion": "..."}}"""

# ============================================================================
# HAIKU EVALUATOR PROMPTS (Penalty-Based, Separate Persona)
# These are ONLY used by the Haiku jury. Sonnet uses the prompts above.
# Philosophy: Start at 10, LOSE points. Hard ceilings enforce brutal honesty.
# ============================================================================

HAIKU_HOOK_EVALUATOR_PROMPT = """You are 19 years old. You spend 3+ hours daily on YouTube Shorts and TikTok. You are ADDICTED to dopamine hits. You have ZERO loyalty to any creator.

Your thumb moves FAST. You give every video exactly 1.5 seconds. If you're not confused, shocked, or angry in that time, you're GONE.

You are BRUTALLY honest. You don't care about hurting feelings. You score like a real viewer behaves, not like a teacher grading an essay.

HOOKS TO EVALUATE:
{hooks_json}

SCORING RULES (start at 10, LOSE points):

HARD CEILINGS (these are ABSOLUTE — you CANNOT score above these no matter what):
- First sentence sounds like a textbook or documentary? MAX 3/10.
- First sentence is predictable (you can guess the next word)? MAX 6/10.
- No curiosity gap (you don't NEED to know what happens next)? MAX 5/10.
- No emotional tension (no danger, no anger, no absurdity)? MAX 7/10.
- You have to re-read it to understand? MAX 4/10.

PENALTIES (subtract from 10):
- Starts with year/date ("In 1453...") → -3
- Uses "Did you know" or "Have you ever wondered" → -4
- Longer than 12 words → -1 per extra word
- Feels like it belongs on History Channel → -2
- You've seen similar hooks before → -2

BONUSES (can recover lost points, but NOT exceed ceiling):
- Made you say "wait WHAT" out loud → +2
- Contains a contradiction that breaks your brain → +2
- Sounds dangerously wrong/offensive (but isn't) → +1

9-10: You would LITERALLY show this to a friend. This NEVER happens.
7-8: You stayed. Good hook. Not legendary.
5-6: Meh. You might stay if bored.
3-4: You swiped. Boring.
0-2: You didn't even finish reading it.

For EACH hook, you MUST also answer:
- skip_reason: In 5 words, why would someone swipe away?
- drop_word: The EXACT word where a viewer would lose interest (or "none" if they wouldn't)

CRITICAL: Respond ONLY with valid JSON. No markdown. No explanations. All scores 0-10.
{{
  "evaluations": [
    {{"hook": "...", "total": X, "skip_reason": "...", "drop_word": "...", "fixes": ["..."]}},
    ...
  ]
}}"""

HAIKU_SECTION_EVALUATOR_PROMPT = """You are 19 years old, dopamine-addicted, scrolling at 2 AM. You stayed for the hook. Now you're 3 seconds in. Your thumb is HOVERING — one boring sentence and you're GONE.

You don't care about: learning something, good writing, clever metaphors. You care about: "then what happened?!", escalating tension, and punchy rhythm.

HOOK THAT KEPT YOU: {hook}

SECTION TYPE: {section_type}

VARIANTS TO EVALUATE:
{variants_json}

SCORING RULES (start at 10, LOSE points):

HARD CEILINGS:
- Any sentence longer than 10 words? MAX 7/10.
- Tension stays flat (doesn't escalate)? MAX 5/10.
- Sounds like a Wikipedia article? MAX 3/10.
- You zoned out at any point? MAX 6/10.
- No new information that surprises you? MAX 6/10.

PENALTIES:
- Contains filler words ("however", "furthermore", "additionally") → -3
- Explains instead of SHOWS → -2
- Any sentence that feels like a lecture → -2 per sentence
- Pacing slows down (longer sentences appear) → -2

BONUSES:
- Each sentence hits harder than the last → +2
- Contains a detail so specific it feels real → +1
- You want to screenshot a line → +1

For EACH variant, you MUST also answer:
- skip_reason: Why would someone swipe HERE? (5 words max)
- drop_word: Exact word where attention dies (or "none")

CRITICAL: Respond ONLY with valid JSON. No markdown. No explanations. All scores 0-10.
{{
  "evaluations": [
    {{"text": "...", "total": X, "skip_reason": "...", "drop_word": "...", "fixes": ["..."]}},
    ...
  ]
}}"""

HAIKU_FINAL_EVALUATOR_PROMPT = """You just watched this entire YouTube Short. You are 19, dopamine-addicted, brutally honest. Score it.

FULL SCRIPT:
---
{full_script}
---

SCORING RULES (start at 10, LOSE points):

HARD CEILINGS:
- You got bored at ANY point? MAX 6/10.
- The ending was predictable? MAX 5/10.
- It felt like a school presentation? MAX 4/10.
- You wouldn't watch it twice? MAX 7/10.
- You wouldn't send it to a friend? MAX 8/10.

PENALTIES:
- Tension plateaued after hook → -2
- Any section felt like filler → -2
- Ending didn't loop back to beginning → -2
- You could predict the ending from the hook → -3

BONUSES:
- Would genuinely send to group chat → +2
- Would watch it 3+ times → +2
- The ending made you go "OH" → +1

You MUST also answer:
- skip_reason: Why would someone NOT finish this? (5 words max)
- drop_word: Exact word where you almost swiped (or "none")

CRITICAL: Respond ONLY with valid JSON. No markdown. No explanations. All scores 0-10.
{{"total": X, "skip_reason": "...", "drop_word": "...", "weakest_section": "hook|context|body|outro", "fix_suggestion": "..."}}"""

SECTION_RULES = {
    "context": """
CRISIS RULES (1-2 sentences):
- CREATE A CRISIS in 5 seconds: who is in danger? what's at stake? what's about to go wrong?
- Make it VISUAL and SPECIFIC — paint a scene, not a Wikipedia summary
- The viewer must feel "oh no, then what happened?!"
- Use present tense for urgency: "1932. Crops are dying. Farmers are desperate."
- Max 25 words""",
    "body": """
ESCALATION RULES (2-4 short sentences):
- Make the crisis WORSE — things escalate, not explain
- Add an unexpected detail that makes the viewer say "no way"
- Short punchy sentences (5-8 words each) — each sentence is a PUNCH
- The tension must RISE with every sentence, never flatten
- Max 40 words""",
    "outro": """
TWIST + PUNCHLINE RULES (1-2 sentences):
- Deliver a twist NO ONE expected — ironic reversal, cold truth, or dark humor
- Make them want to screenshot it or send it to a friend
- PERFECT LOOP: The last phrase must grammatically connect back to the HOOK's first words.
  Do NOT end abruptly with a dash (--). The outro must be a COMPLETE thought that naturally flows into the hook.
  Example: Outro ends with "...and that's the real reason why" -> loops into Hook -> viewer replays.
- The viewer should feel the ground shift under them
- Max 15 words"""
}

# ============================================================================
# BEDROCK CLIENT HELPERS
# ============================================================================

def get_bedrock_client(region_name: Optional[str] = None):
    """Initialize Bedrock client with region."""
    region = region_name or os.environ.get('AWS_REGION_NAME', 'us-east-1')
    return boto3.client('bedrock-runtime', region_name=region)


# Global metrics tracker for current run
_metrics = {
    "api_calls": 0,
    "repair_count": 0,
    "fallback_used": False,
    "warnings": []
}

def reset_metrics():
    """Reset metrics for new pipeline run."""
    global _metrics
    _metrics = {
        "api_calls": 0,
        "repair_count": 0,
        "fallback_used": False,
        "warnings": [],
        "start_time": time.time()
    }

def get_metrics() -> dict:
    """Get current metrics with latency."""
    m = _metrics.copy()
    if "start_time" in m:
        m["latency_ms"] = int((time.time() - m["start_time"]) * 1000)  # pyre-ignore[58]
        del m["start_time"]  # pyre-ignore[55]
    return m

def check_api_limit():
    """Check if we've exceeded max API calls. Raises exception if so."""
    if _metrics["api_calls"] >= MAX_API_CALLS_PER_VIDEO:  # pyre-ignore[58]
        _metrics["warnings"].append("MAX_API_CALLS_EXCEEDED")
        raise Exception(f"Exceeded max API calls limit ({MAX_API_CALLS_PER_VIDEO})")


def invoke_bedrock(
    client,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 500,
    system_prompt: Optional[str] = None,
    model_id: Optional[str] = None
) -> str:
    """
    Invoke Bedrock Claude with exponential backoff + jitter for throttling.
    
    Args:
        model_id: Override model. If None, uses BEDROCK_MODEL_ID env var (Sonnet default).
    
    Returns raw text response.
    """
    global _metrics
    
    # Check API call limit
    check_api_limit()
    
    model_id = model_id or os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    
    messages = [{"role": "user", "content": prompt}]
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": messages
    }
    
    if system_prompt:
        request_body["system"] = system_prompt
    
    # Exponential backoff with jitter for throttling
    backoff = INITIAL_BACKOFF
    for attempt in range(MAX_RETRIES):
        try:
            response = client.invoke_model(
                modelId=model_id,
                body=json.dumps(request_body),
                contentType="application/json",
                accept="application/json"
            )
            
            _metrics["api_calls"] += 1  # pyre-ignore[58]
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except client.exceptions.ThrottlingException as e:
            if attempt < MAX_RETRIES - 1:
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0, JITTER_MAX * backoff)
                sleep_time = backoff + jitter
                print(f"⚠️ Throttled, backing off {sleep_time:.2f}s (attempt {attempt+1})...")
                time.sleep(sleep_time)
                backoff *= 2
            else:
                raise e
        except Exception as e:
            if "ThrottlingException" in str(e) and attempt < MAX_RETRIES - 1:
                jitter = random.uniform(0, JITTER_MAX * backoff)
                sleep_time = backoff + jitter
                print(f"⚠️ Throttled, backing off {sleep_time:.2f}s (attempt {attempt+1})...")
                time.sleep(sleep_time)
                backoff *= 2
            else:
                raise e
    
    raise Exception("Max retries exceeded")


def parse_json_safe(text: str, client=None, original_prompt: Optional[str] = None, validation_model=None, logger_callback=None) -> Any:
    """
    Parse JSON from Claude response with fail-safe repair and Optional Pydantic validation.
    
    Args:
        text: Raw LLM output
        client: Bedrock client (for LLM repair)
        original_prompt: Original prompt (for LLM repair context)
        validation_model: Pydantic model class to validate against
        logger_callback: Optional callback for logging events
        
    Returns:
        Parsed dict/list or None if failed.
    """
    global _metrics
    
    def strip_markdown_fences(s: str) -> str:
        """Remove markdown code fences from text."""
        s = s.strip()
        # Remove opening fence
        if s.startswith("```json"):
            s = s[7:]  # pyre-ignore[16]
        elif s.startswith("```"):
            s = s[3:]  # pyre-ignore[16]
        # Remove closing fence
        if s.endswith("```"):
            s = s[:-3]  # pyre-ignore[16]
        return s.strip()
    
    # CRITICAL: Strip markdown code fences FIRST (most common parse failure)
    clean_text = strip_markdown_fences(text)
    
    # Try direct parse first (with cleaned text)
    try:
        # Find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', clean_text)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON array
    try:
        json_match = re.search(r'\[[\s\S]*\]', clean_text)
        if json_match:
            return {"array": json.loads(json_match.group())}
    except json.JSONDecodeError:
        pass
    
    # Try local repair with json_repair library (FAST & FREE)
    repaired_obj = None
    if json_repair:
        try:
            # repair_json returns the parsed object, not string
            repaired_obj = json_repair.repair_json(clean_text, return_objects=True)
            if repaired_obj is not None:
                # If validation model provided, validate it
                if validation_model:
                    try:
                        # Validating schema
                        validated = validation_model(**repaired_obj)
                        print(f"✅ Pydantic validation successful: {validation_model.__name__}")
                        return validated.dict()
                    except Exception as e:
                        print(f"⚠️ Pydantic validation failed: {e}")
                        repaired_obj = None # Treat as failure to trigger LLM repair
                        _metrics["warnings"].append(f"SCHEMA_VALIDATION_FAILED:{validation_model.__name__}")  # pyre-ignore[16]
                
                    if logger_callback and repaired_obj:
                         logger_callback(level="INFO", message=f"✅ Pydantic Validation Passed ({validation_model.__name__ if validation_model else 'Generic'})")
                else:
                    print("✅ Local JSON repair successful")
                    return repaired_obj
        except Exception as e:
            print(f"⚠️ Local JSON repair/validation failed: {e}")
            repaired_obj = None
    
    # Attempt LLM-based repair if local repair/validation failed (MAX 1 repair per call)
    if client and original_prompt and _metrics["repair_count"] < MAX_REPAIR_ATTEMPTS:  # pyre-ignore[58]
        try:
            _metrics["repair_count"] += 1  # pyre-ignore[58]
            print(f"🔧 Attempting LLM JSON repair (repair #{_metrics['repair_count']})...")
            
            repair_prompt = f"""The following text should be valid JSON but has errors. 
Fix it and return ONLY the corrected JSON, nothing else. Do NOT wrap in markdown code fences:

{text}"""
            repaired = invoke_bedrock(client, repair_prompt, temperature=0.0, max_tokens=300)
            # CRITICAL: Also strip markdown from repair output
            repaired = strip_markdown_fences(repaired)
            
            # recursive try local repair on the LLM output too
            if json_repair:
                 try:
                    repaired_obj = json_repair.repair_json(repaired, return_objects=True)
                    if repaired_obj is not None:
                        return repaired_obj
                 except:
                    pass

            json_match = re.search(r'\{[\s\S]*\}', repaired)
            if json_match:
                result = json.loads(json_match.group())
                print(f"✅ LLM JSON repair successful")
                return result
        except Exception as e:
            print(f"⚠️ LLM JSON repair failed: {e}")
            _metrics["warnings"].append("JSON_REPAIR_FAILED")  # pyre-ignore[16]
    
    print(f"⚠️ JSON parse failed (first 50 chars): {text[:50]}...")  # pyre-ignore[16]
    _metrics["warnings"].append("JSON_PARSE_FAILED")  # pyre-ignore[16]
    return None  # pyre-ignore[7]


# ============================================================================
# HOOK GENERATION & SCORING
# ============================================================================

def generate_hooks_batch(client, topic: str, era: str, context: str = "", angle: str = "") -> List[str]:
    """Generate 3 hooks in a single API call."""
    context_block = f"SOURCE TEXT (Use ONLY these facts):\n{context[:1000]}" if context else ""  # pyre-ignore[6]
    angle_block = f"VIRAL ANGLE (Focus on this):\n{angle}" if angle else ""
    
    prompt = HOOK_GENERATOR_PROMPT.format(
        topic=topic, 
        era=era,
        context_block=context_block,
        angle_block=angle_block
    )
    
    # Inject prompt memory (learned DO/DON'T examples) if available
    memory_injection = format_prompt_memory()
    if memory_injection:
        prompt += memory_injection
    
    
    response = invoke_bedrock(client, prompt, temperature=WRITER_TEMPERATURE, max_tokens=200)
    result = parse_json_safe(response, client, prompt, validation_model=models.HookBatch if models else None)
    
    if result and "hooks" in result:
        return result["hooks"]
    
    # Fallback: try to extract hooks manually
    lines = [l.strip() for l in response.split('\n') if l.strip() and not l.startswith('{')]
    return lines[:3] if lines else ["Failed to generate hooks"]  # pyre-ignore[6]


def evaluate_hooks_batch(client, hooks: List[str]) -> List[dict]:
    """Evaluate hooks with dual jury: Sonnet (primary) + Haiku (second opinion)."""
    hooks_json = json.dumps(hooks, ensure_ascii=False)
    prompt = HOOK_EVALUATOR_PROMPT.format(
        anchor_examples=HOOK_ANCHOR_EXAMPLES,
        hooks_json=hooks_json
    )
    
    # Jury 1: Sonnet (primary evaluator)
    response_sonnet = invoke_bedrock(client, prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=400)
    result_sonnet = parse_json_safe(response_sonnet, client, prompt, validation_model=models.HookEvaluationBatch if models else None)
    evals_sonnet = result_sonnet.get("evaluations", []) if result_sonnet else []
    
    # Jury 2: Haiku (separate persona -- penalty-based rubric)
    try:
        haiku_prompt = HAIKU_HOOK_EVALUATOR_PROMPT.format(hooks_json=hooks_json)
        response_haiku = invoke_bedrock(client, haiku_prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=500, model_id=HAIKU_MODEL_ID)
        result_haiku = parse_json_safe(response_haiku, client, prompt, validation_model=models.HookEvaluationBatch if models else None)
        evals_haiku = result_haiku.get("evaluations", []) if result_haiku else []
    except Exception as e:
        print(f"[WARNING] Haiku eval failed, using Sonnet only: {e}")
        evals_haiku = []
    
    # Merge: weighted scoring with floor guardrail
    if evals_sonnet:
        merged = []
        for i, s_eval in enumerate(evals_sonnet):
            h_eval = evals_haiku[i] if i < len(evals_haiku) else {}  # pyre-ignore[6]
            s_total = min(10.0, max(0.0, float(s_eval.get("total", 5.0))))  # clamp 0-10
            h_total = min(10.0, max(0.0, float(h_eval.get("total", s_total))))  # clamp 0-10
            
            # Floor guardrail: structure can't be garbage even if attention is high
            if s_total < SONNET_FLOOR:
                final_total = s_total  # Sonnet veto: structurally too weak
                print(f"    [DUAL] Hook {i+1}: Sonnet={s_total} BELOW FLOOR ({SONNET_FLOOR}) -> Final={final_total}")
            else:
                final_total = round(s_total * SONNET_WEIGHT + h_total * HAIKU_WEIGHT, 1)  # pyre-ignore[6]
                print(f"    [DUAL] Hook {i+1}: Sonnet={s_total}*{SONNET_WEIGHT} + Haiku={h_total}*{HAIKU_WEIGHT} -> Final={final_total}")
            
            # Merge fixes + Haiku diagnostics
            merged_fixes = list(s_eval.get("fixes", [])) + list(h_eval.get("fixes", []))  # pyre-ignore[6]
            merged.append({**s_eval, "total": final_total, "fixes": merged_fixes,
                          "sonnet_score": s_total, "haiku_score": h_total,
                          "skip_reason": h_eval.get("skip_reason", ""),
                          "drop_word": h_eval.get("drop_word", "")})
        return merged
    
    # Fallback
    return [{"hook": h, "total": 5.0, "fixes": ["evaluation failed"]} for h in hooks]


def refine_hook(client, hook: str, fixes: List[str], skip_reason: str = "", drop_word: str = "") -> str:
    """Refine a single hook with targeted viewer diagnostics."""
    prompt = HOOK_REFINER_PROMPT.format(
        hook=hook,
        fixes=", ".join(fixes) if fixes else "none",
        skip_reason=skip_reason or "no specific reason given",
        drop_word=drop_word or "unknown"
    )
    response = invoke_bedrock(client, prompt, temperature=WRITER_TEMPERATURE, max_tokens=50)
    
    # Clean up response
    cleaned = response.strip().strip('"').strip("'")
    return cleaned if cleaned else hook


def generate_winning_hook(client, topic: str, era: str, context: str = "", angle: str = "") -> Tuple[str, float, dict]:
    """
    Generate hooks with iterative refinement until threshold met.
    
    Returns: (final_hook, final_score, stats)
    """
    stats = {"iterations": 0, "total_hooks_generated": 0}
    best_hook = None
    best_score = 0.0
    best_fixes = []
    best_skip_reason = ""
    best_drop_word = ""
    first_hook_score = 0.0  # Pre-refine instrumentation
    
    for iteration in range(HOOK_MAX_ITERATIONS):
        stats["iterations"] = iteration + 1
        
        if iteration == 0:
            # First iteration: generate 3 hooks batch
            hooks = generate_hooks_batch(client, topic, era, context, angle)
            stats["total_hooks_generated"] += len(hooks)
        else:
            # Targeted refinement: pass Haiku diagnostics to writer
            refined = refine_hook(client, best_hook, best_fixes,  # pyre-ignore[6]
                                  best_skip_reason, best_drop_word)
            hooks = [refined]
            stats["total_hooks_generated"] += 1
        
        # Evaluate all hooks
        evaluations = evaluate_hooks_batch(client, hooks)
        
        # Find best hook with tie-breaker: CLARITY first, then shorter
        for eval_item in evaluations:
            score = eval_item.get("total", 0)
            hook_text = eval_item.get("hook", hooks[0])
            clarity = eval_item.get("clarity", 0)
            
            # Check if this is better
            is_better = score > best_score
            
            # Tie-breaker: clarity first, then shorter
            is_tied = abs(score - best_score) < SCORE_TIE_THRESHOLD
            if is_tied and best_hook:
                # First: higher clarity wins
                best_clarity = stats.get("best_clarity", 0)
                if clarity > best_clarity:
                    is_better = True
                    print(f"    \u21b3 Tie-breaker: higher clarity ({clarity}) wins")
                # Second: if clarity same, shorter wins
                elif clarity == best_clarity and len(hook_text.split()) < len(best_hook.split()):  # pyre-ignore[16]
                    is_better = True
                    print(f"    \u21b3 Tie-breaker: shorter hook ({len(hook_text.split())} words)")
            
            if is_better:
                best_score = score
                best_hook = hook_text
                best_fixes = eval_item.get("fixes", [])
                best_skip_reason = eval_item.get("skip_reason", "")
                best_drop_word = eval_item.get("drop_word", "")
                stats["best_clarity"] = clarity
                # Log initial vs post-refine scores
                if iteration == 0:
                    stats["initial_haiku_score"] = eval_item.get("haiku_score", 0)
                    first_hook_score = score  # Capture pre-refine score
                else:
                    stats["refine_haiku_score"] = eval_item.get("haiku_score", 0)
        
        # Capture first iteration's best score (even if not "is_better" on later iterations)
        if iteration == 0:
            first_hook_score = best_score
        
        print(f"  Hook iteration {iteration + 1}: best score = {best_score}")  # pyre-ignore[58]
        
        # Check if threshold met (mode-aware)
        threshold = get_threshold("hook_threshold")
        if best_score >= threshold:
            print(f"✅ Hook approved: {best_score} (threshold: {threshold})")
            break
    
    stats["final_score"] = best_score  # pyre-ignore[26]
    stats["first_hook_score"] = first_hook_score  # Pre-refine instrumentation
    return best_hook, best_score, stats  # pyre-ignore[7]


# ============================================================================
# SECTION GENERATION & SCORING
# ============================================================================

def generate_section_variants(
    client, 
    section_type: str, 
    hook: str, 
    topic: str, 
    era: str,
    context: str = "",
    angle: str = ""
) -> List[str]:
    """Generate 2 variants of a section in a single API call."""
    context_block = f"SOURCE TEXT (Use ONLY these facts):\n{context[:1000]}" if context else ""  # pyre-ignore[6]
    angle_block = f"VIRAL ANGLE (Focus on this):\n{angle}" if angle else ""

    prompt = SECTION_GENERATOR_PROMPT.format(
        section_type=section_type.upper(),
        hook=hook,
        topic=topic,
        era=era,
        context_block=context_block,
        angle_block=angle_block,
        section_rules=SECTION_RULES.get(section_type, "")
    )
    
    response = invoke_bedrock(client, prompt, temperature=WRITER_TEMPERATURE, max_tokens=300)
    result = parse_json_safe(response, client, prompt, validation_model=models.SectionVariants if models else None)
    
    if result and "variants" in result:
        return result["variants"]
    
    # Fallback
    return [response.strip()]


def evaluate_section_variants(
    client, 
    section_type: str, 
    variants: List[str], 
    hook: str
) -> List[dict]:
    """Evaluate section variants with dual jury: Sonnet + Haiku."""
    variants_json = json.dumps(variants, ensure_ascii=False)
    prompt = SECTION_EVALUATOR_PROMPT.format(
        section_type=section_type.upper(),
        anchor_examples=SECTION_ANCHOR_EXAMPLES,
        hook=hook,
        variants_json=variants_json
    )
    
    # Jury 1: Sonnet
    response_sonnet = invoke_bedrock(client, prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=400)
    result_sonnet = parse_json_safe(response_sonnet, client, prompt, validation_model=models.SectionEvaluationBatch if models else None)
    evals_sonnet = result_sonnet.get("evaluations", []) if result_sonnet else []
    
    # Jury 2: Haiku (separate persona -- penalty-based rubric)
    try:
        haiku_prompt = HAIKU_SECTION_EVALUATOR_PROMPT.format(
            section_type=section_type.upper(),
            hook=hook,
            variants_json=variants_json
        )
        response_haiku = invoke_bedrock(client, haiku_prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=500, model_id=HAIKU_MODEL_ID)
        result_haiku = parse_json_safe(response_haiku, client, prompt, validation_model=models.SectionEvaluationBatch if models else None)
        evals_haiku = result_haiku.get("evaluations", []) if result_haiku else []
    except Exception as e:
        print(f"[WARNING] Haiku section eval failed, using Sonnet only: {e}")
        evals_haiku = []
    
    # Merge: weighted scoring with floor guardrail
    if evals_sonnet:
        merged = []
        for i, s_eval in enumerate(evals_sonnet):
            h_eval = evals_haiku[i] if i < len(evals_haiku) else {}  # pyre-ignore[6]
            s_total = min(10.0, max(0.0, float(s_eval.get("total", 6.0))))  # clamp 0-10
            h_total = min(10.0, max(0.0, float(h_eval.get("total", s_total))))  # clamp 0-10
            
            # Floor guardrail
            if s_total < SONNET_FLOOR:
                final_total = s_total
                print(f"    [DUAL] {section_type.upper()} variant {i+1}: Sonnet={s_total} BELOW FLOOR ({SONNET_FLOOR}) -> Final={final_total}")
            else:
                final_total = round(s_total * SONNET_WEIGHT + h_total * HAIKU_WEIGHT, 1)  # pyre-ignore[6]
                print(f"    [DUAL] {section_type.upper()} variant {i+1}: Sonnet={s_total}*{SONNET_WEIGHT} + Haiku={h_total}*{HAIKU_WEIGHT} -> Final={final_total}")
            
            merged_fixes = list(s_eval.get("fixes", [])) + list(h_eval.get("fixes", []))  # pyre-ignore[6]
            merged.append({**s_eval, "total": final_total, "fixes": merged_fixes,
                          "sonnet_score": s_total, "haiku_score": h_total,
                          "skip_reason": h_eval.get("skip_reason", ""),
                          "drop_word": h_eval.get("drop_word", "")})
        return merged
    
    return [{"text": v, "total": 6.0, "fixes": ["evaluation failed"]} for v in variants]


def refine_section(
    client, 
    section_type: str, 
    text: str, 
    fixes: List[str], 
    hook: str,
    skip_reason: str = "",
    drop_word: str = ""
) -> str:
    """Refine a section with targeted viewer diagnostics."""
    prompt = SECTION_REFINER_PROMPT.format(
        section_type=section_type.upper(),
        text=text,
        fixes=", ".join(fixes) if fixes else "none",
        hook=hook,
        skip_reason=skip_reason or "no specific reason given",
        drop_word=drop_word or "unknown"
    )
    response = invoke_bedrock(client, prompt, temperature=WRITER_TEMPERATURE, max_tokens=150)
    return response.strip()


def generate_winning_section(
    client, 
    section_type: str, 
    hook: str, 
    topic: str, 
    era: str,
    context: str = "",
    angle: str = ""
) -> Tuple[str, float, dict]:
    """
    Generate section with iterative refinement.
    
    Returns: (final_text, final_score, stats)
    """
    stats = {"iterations": 0, "variants_generated": 0}
    best_text = None
    best_score = 0.0
    best_fixes = []
    best_skip_reason = ""
    best_drop_word = ""
    
    for iteration in range(SECTION_MAX_ITERATIONS):
        stats["iterations"] = iteration + 1
        
        if iteration == 0:
            # First iteration: generate 2 variants
            variants = generate_section_variants(client, section_type, hook, topic, era, context, angle)
            stats["variants_generated"] += len(variants)
        else:
            # Targeted refinement: pass Haiku diagnostics to writer
            refined = refine_section(client, section_type, best_text, best_fixes, hook,  # pyre-ignore[6]
                                      best_skip_reason, best_drop_word)
            variants = [refined]
            stats["variants_generated"] += 1
        
        # Evaluate
        evaluations = evaluate_section_variants(client, section_type, variants, hook)
        
        # Find best with tie-breaker (punchier = higher punch score wins on tie)
        for eval_item in evaluations:
            score = eval_item.get("total", 0)
            text = eval_item.get("text", variants[0])
            punch = eval_item.get("punch", 0)
            
            # Check if this is better (or tied but punchier for outro, clearer for context)
            is_better = score > best_score
            is_tied = abs(score - best_score) < SCORE_TIE_THRESHOLD
            
            # Tie-breaker based on section type
            best_punch = 0  # Default if not set
            if is_tied and best_text:
                if section_type == "outro" and punch > best_punch:
                    is_better = True
                    print(f"    ↳ Tie-breaker: punchier outro selected")
                elif section_type == "context" and len(text.split()) < len(best_text.split()):  # pyre-ignore[16]
                    is_better = True  # Clearer = shorter for context
                    print(f"    ↳ Tie-breaker: clearer (shorter) context selected")
            
            if is_better or (is_tied and not best_text):
                best_score = score
                best_text = text
                best_fixes = eval_item.get("fixes", [])
                best_skip_reason = eval_item.get("skip_reason", "")
                best_drop_word = eval_item.get("drop_word", "")
                best_punch = punch
        
        print(f"  {section_type.upper()} iteration {iteration + 1}: best score = {best_score}")  # pyre-ignore[16]
        
        if best_score >= get_threshold("section_threshold"):
            print(f"✅ {section_type.upper()} approved: {best_score}")  # pyre-ignore[16]
            break
    
    stats["final_score"] = best_score  # pyre-ignore[26]
    return best_text, best_score, stats


# ============================================================================
# FINAL ASSEMBLY & EVALUATION
# ============================================================================

def evaluate_full_script(client, full_script: str) -> dict:
    """Evaluate complete script with dual jury: Sonnet + Haiku."""
    prompt = FINAL_EVALUATOR_PROMPT.format(full_script=full_script)
    
    # Jury 1: Sonnet
    response_sonnet = invoke_bedrock(client, prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=200)
    result_sonnet = parse_json_safe(response_sonnet, client, prompt, validation_model=models.FinalEvaluation if models else None)
    
    # Jury 2: Haiku (separate persona -- penalty-based rubric)
    try:
        haiku_prompt = HAIKU_FINAL_EVALUATOR_PROMPT.format(full_script=full_script)
        response_haiku = invoke_bedrock(client, haiku_prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=300, model_id=HAIKU_MODEL_ID)
        result_haiku = parse_json_safe(response_haiku, client, prompt, validation_model=models.FinalEvaluation if models else None)
    except Exception as e:
        print(f"[WARNING] Haiku final eval failed, using Sonnet only: {e}")
        result_haiku = None
    
    if result_sonnet:
        s_total = min(10.0, max(0.0, float(result_sonnet.get("total", 7.0))))  # clamp 0-10
        h_total = min(10.0, max(0.0, float(result_haiku.get("total", s_total)))) if result_haiku else s_total  # clamp 0-10
        
        # Floor guardrail
        if s_total < SONNET_FLOOR:
            final_total = s_total
            print(f"    [DUAL] FINAL: Sonnet={s_total} BELOW FLOOR ({SONNET_FLOOR}) -> Final={final_total}")
        else:
            final_total = round(s_total * SONNET_WEIGHT + h_total * HAIKU_WEIGHT, 1)  # pyre-ignore[6]
            print(f"    [DUAL] FINAL: Sonnet={s_total}*{SONNET_WEIGHT} + Haiku={h_total}*{HAIKU_WEIGHT} -> Final={final_total}")
        
        # Use Sonnet's qualitative feedback but weighted score
        result_sonnet["total"] = final_total
        result_sonnet["sonnet_score"] = s_total
        result_sonnet["haiku_score"] = h_total
        result_sonnet["skip_reason"] = result_haiku.get("skip_reason", "") if result_haiku else ""
        result_sonnet["drop_word"] = result_haiku.get("drop_word", "") if result_haiku else ""
        
        # If Haiku's attention score is lower, prefer its qualitative feedback
        if result_haiku and h_total < s_total:
            result_sonnet["weakest_section"] = result_haiku.get("weakest_section", result_sonnet.get("weakest_section"))
            result_sonnet["fix_suggestion"] = result_haiku.get("fix_suggestion", result_sonnet.get("fix_suggestion"))
        
        return result_sonnet
    
    return {"total": 7.0, "weakest_section": "unknown", "fix_suggestion": "evaluation failed"}


def assemble_script(
    hook: str, 
    context: str, 
    body: str, 
    outro: str, 
    topic: str, 
    era: str,
    scores: dict
) -> dict:
    """Assemble final script in the format expected by the video pipeline."""
    full_text = f"{hook}\n\n{context}\n\n{body}\n\n{outro}"
    
    # Calculate word count for timing
    words = full_text.split()
    total_words = len(words)
    
    # Estimate timing (roughly 2.5 words per second for dramatic narration)
    total_duration = min(max(total_words / 2.5, 12), 17)  # 12-17 seconds
    
    # Create segments with timing
    hook_words = len(hook.split())
    context_words = len(context.split())
    body_words = len(body.split())
    outro_words = len(outro.split())
    
    # Proportional timing
    hook_end = (hook_words / total_words) * total_duration
    context_end = hook_end + (context_words / total_words) * total_duration
    body_end = context_end + (body_words / total_words) * total_duration
    
    # Create safe title
    safe_title = re.sub(r'[^\w\s-]', '', topic)
    safe_title = re.sub(r'[-\s]+', '_', safe_title).strip('_')[:50]  # pyre-ignore[16]
    
    # Era visual style
    era_styles = {
        "ancient": "ancient world, classical era, marble statues",
        "medieval": "medieval era, castle, knights, oil painting style",
        "ottoman": "Ottoman Empire, Islamic architecture, orientalist painting",
        "early_20th": "early 20th century, black and white vintage photograph",
        "ww1": "World War I, trenches, grainy black and white",
        "ww2": "World War II, military, black and white photography",
        "modern": "mid 20th century, vintage film look"
    }
    era_style = era_styles.get(era, era_styles["early_20th"])
    
    return {
        "title": f"{topic[:40]} 📜",  # pyre-ignore[16]
        "safe_title": safe_title,
        "voiceover_text": full_text.replace('\n\n', ' '),
        "segments": [
            {
                "start": 0,
                "end": round(float(hook_end), 1),  # pyre-ignore[6]
                "text": hook,
                "image_prompt": f"{topic}, dramatic opening scene, {era_style}, 9:16 vertical composition"
            },
            {
                "start": round(float(hook_end), 1),  # pyre-ignore[6]
                "end": round(float(context_end), 1),  # pyre-ignore[6]
                "text": context,
                "image_prompt": f"{topic}, historical context scene, {era_style}, 9:16 vertical composition"
            },
            {
                "start": round(float(context_end), 1),  # pyre-ignore[6]
                "end": round(float(body_end), 1),  # pyre-ignore[6]
                "text": body,
                "image_prompt": f"{topic}, main action scene, {era_style}, dramatic lighting, 9:16 vertical composition"
            },
            {
                "start": round(float(body_end), 1),  # pyre-ignore[6]
                "end": round(float(total_duration), 1),  # pyre-ignore[6]
                "text": outro,
                "image_prompt": f"{topic}, conclusion scene, {era_style}, atmospheric, 9:16 vertical composition"
            }
        ],
        "mood": "epic" if any(w in topic.lower() for w in ["war", "battle", "death", "kill"]) else "documentary",
        "era": era,
        "music_style": "epic_orchestral" if "war" in topic.lower() else "dramatic_strings",
        "original_topic": topic,
        "pipeline_scores": scores,
        "pipeline_version": "2.0"
    }


# ============================================================================
# MAIN PIPELINE
# ============================================================================

# Sample topics for random selection
PIPELINE_TOPICS = [
    {"topic": "The Great Emu War - Australia lost a war to birds", "era": "early_20th"},
    {"topic": "Cleopatra lived closer to the iPhone than to the pyramids", "era": "ancient"},
    {"topic": "Napoleon wasn't short - British propaganda made that up", "era": "19th_century"},
    {"topic": "Vikings were cleaner than medieval Europeans", "era": "medieval"},
    {"topic": "Roman soldiers were paid in salt - that's where 'salary' comes from", "era": "ancient"},
    {"topic": "Genghis Khan killed so many people it cooled the Earth", "era": "medieval"},
    {"topic": "The shortest war in history lasted 38 minutes", "era": "19th_century"},
    {"topic": "Ancient Egyptians used moldy bread as antibiotics", "era": "ancient"},
    {"topic": "Samurai could legally kill anyone who disrespected them", "era": "medieval"},
    {"topic": "The dancing plague of 1518 - people danced until they died", "era": "medieval"},
    {"topic": "Oxford University is older than the Aztec Empire", "era": "medieval"},
    {"topic": "Mehmed the Conqueror learned 7 languages and painted", "era": "ottoman"},
    {"topic": "Spartans threw weak babies off cliffs - or did they?", "era": "ancient"},
    {"topic": "The Library of Alexandria wasn't destroyed in one fire", "era": "ancient"},
    {"topic": "Julius Caesar was kidnapped by pirates and joked with them", "era": "ancient"},
]


def generate_script_pipeline(
    topic: Optional[str] = None, 
    era: Optional[str] = None, 
    region_name: Optional[str] = None,
    mode: str = "quality",
    logger_callback: Optional[Callable] = None
) -> dict:
    """
    Main pipeline: Generate script with iterative scoring and refinement.
    
    This is the Bedrock-optimized version with batch generation,
    exponential backoff, and quality thresholds.
    
    Args:
        topic: Optional specific topic
        era: Optional era for visual styling
        region_name: AWS region for Bedrock
        mode: 'quality' (strict) or 'fast' (relaxed thresholds)
        logger_callback: Optional callback(level, message, metadata) for status updates
        
    Returns:
        Script dict compatible with existing video pipeline
    """
    # Reset metrics for this run
    reset_metrics()
    
    # Set pipeline mode
    set_pipeline_mode(mode)
    
    print("🎬 Starting Script Pipeline v2.3 (Final - Diversity + KPI)...")
    
    # Initialize client
    region = region_name or os.environ.get('AWS_REGION_NAME', 'us-east-1')
    client = get_bedrock_client(region)
    
    # Topic selection with diversity gate enforcement
    max_topic_attempts = 5
    diversity_result = None
    
    for topic_attempt in range(max_topic_attempts):
        # Select topic
        if topic and topic_attempt == 0:
            selected_topic = topic
            selected_era = era or "early_20th"
        else:
            selection = random.choice(PIPELINE_TOPICS)
            selected_topic = selection["topic"]
            selected_era = selection.get("era", "early_20th")
        
        # Normalize era to standard enum
        selected_era = normalize_era(selected_era)  # pyre-ignore[6]
        
        # Extract topic entity for diversity tracking
        topic_words = selected_topic.split()
        topic_entity = topic_words[0] if topic_words else "unknown"
        # Try to find proper noun (capitalized word after first)
        for word in list(topic_words[1:5]):  # pyre-ignore[16]
            if len(word) > 0 and word[0].isupper() and word.lower() not in ['the', 'a', 'an', 'in', 'on', 'at']:
                topic_entity = word.strip('.,!?')
                break
        
        # Check diversity gate
        diversity_result = check_diversity_gate(selected_topic, topic_entity, region)
        
        if diversity_result["allowed"]:
            print(f"✅ Diversity gate passed (similarity: {diversity_result['similarity']:.2f})")
            break
        else:
            print(f"⛔ Diversity gate blocked: {diversity_result['reason']}")
            _metrics["warnings"].append(f"DIVERSITY_BLOCKED:{diversity_result['reason']}")  # pyre-ignore[16]
            if topic and topic_attempt == 0:
                print("↳ User-specified topic blocked, trying random...")
    else:
        # All attempts failed, force through with warning
        print("⚠️ Max topic attempts reached, proceeding with last selection")
        _metrics["warnings"].append("DIVERSITY_GATE_FORCED")  # pyre-ignore[16]
    
    print(f"📜 Topic: {selected_topic}")
    print(f"🕰️ Era: {selected_era} (normalized)")
    print(f"👤 Entity: {topic_entity}")
    
    print(f"📜 Topic: {selected_topic}")
    print(f"🕰️ Era: {selected_era} (normalized)")
    print(f"👤 Entity: {topic_entity}")
    
    
    if logger_callback:
        logger_callback(level="INFO", message=f"📜 Selected Topic: {selected_topic}")  # pyre-ignore[29]

    # Step 0: Research & Grounding
    print("\n📚 STEP 0: Researching & Angle Hunting...")
    if logger_callback:
        logger_callback(level="INFO", message=f"📚 Researching '{selected_topic}'...")
    
    wiki_context = get_wiki_summary(selected_topic)
    
    # Fix Era Mismatch based on text content (e.g. "1520" -> "ottoman")
    if wiki_context:
        original_era = selected_era
        selected_era = refine_era_from_text(wiki_context, selected_era)
        if selected_era != original_era:
             print(f"🕰️ Era Refined via Text Analysis: {original_era} -> {selected_era}")

    viral_angle = ""
    
    if wiki_context:
        print("✅ Wikipedia context found. Hunting for angle...")
        angle_data = find_viral_angle(client, selected_topic, wiki_context, invoke_bedrock)
        
        if angle_data and "angle" in angle_data:
            viral_angle = angle_data["angle"]
            reason = angle_data.get("reason", "No reason provided")
            print(f"🎯 Viral Angle: {viral_angle}")
            print(f"   Reason: {reason}")
            
            if logger_callback:
                logger_callback(level="INFO", message=f"💎 Angle Found: {viral_angle[:40]}...")
        else:
            print("⚠️ Angle hunting failed or returned no angle.")
            
        if logger_callback:
            logger_callback(level="INFO", message="✅ Context Found. Anti-Hallucination Mode ON.")
    else:
        print("⚠️ No context found. Using general knowledge (Risky).")
        if logger_callback:
            logger_callback(level="WARNING", message="⚠️ No Context Found. Using General Knowledge.")

    # Step 1: Generate winning hook
    print("\n🔥 STEP 1: Generating hook...")
    if logger_callback:
        logger_callback(level="INFO", message="🔥 Generating Hook & Titles...")

    hook, hook_score, hook_stats = generate_winning_hook(client, selected_topic, selected_era, wiki_context, viral_angle)
    print(f"   Final hook ({hook_score}): {hook}")
    
    # Step 1.5: Evaluate hook KPI metrics (YouTube behavior prediction)
    print("\n📊 STEP 1.5: Evaluating hook KPI...")
    hook_kpi = evaluate_hook_kpi(client, hook)
    
    # Generate titles now to update UI immediately
    titles = generate_title_variants(client, hook, selected_topic)
    selected_title = titles[0] if titles else selected_topic
    
    if logger_callback:
        logger_callback(
            level="INFO", 
            message=f"✅ Titles Generated. Primary: '{selected_title}'", 
            metadata={"title": selected_title}
        )

    print(f"   instant_clarity: {hook_kpi['instant_clarity']} | curiosity_gap: {hook_kpi['curiosity_gap']}")
    print(f"   swipe_risk: {hook_kpi['swipe_risk']} (higher=less swipe) | predicted_retention: {hook_kpi['predicted_retention']}%")
    
    # Step 2: Generate sections
    # Step 2: Generate sections
    print("\n📝 STEP 2: Generating sections...")
    if logger_callback:
        logger_callback(level="INFO", message="📝 Generating Sections (Context, Body, Outro)...")
    
    context, context_score, context_stats = generate_winning_section(
        client, "context", hook, selected_topic, selected_era, wiki_context, viral_angle
    )
    
    body, body_score, body_stats = generate_winning_section(
        client, "body", hook, selected_topic, selected_era, wiki_context, viral_angle
    )
    
    outro, outro_score, outro_stats = generate_winning_section(
        client, "outro", hook, selected_topic, selected_era, wiki_context, viral_angle
    )
    
    # Step 3: Assemble and final eval
    # Step 3: Assemble and final eval
    print("\n🎯 STEP 3: Final assembly and evaluation...")
    if logger_callback:
        logger_callback(level="INFO", message="🎯 Assembling Final Script...")
    
    scores = {
        "hook_score": hook_score,
        "context_score": context_score,
        "body_score": body_score,
        "outro_score": outro_score
    }
    
    script = assemble_script(hook, context, body, outro, selected_topic, selected_era, scores)
    
    # Final evaluation
    final_eval = evaluate_full_script(client, script["voiceover_text"])
    final_score = final_eval.get("total", 8.0)
    weakest = final_eval.get("weakest_section", "none")
    
    # Step 4: Rewrite weakest section if final score too low
    if final_score < FINAL_THRESHOLD and weakest != "none" and weakest != "unknown":
        print(f"\n🔧 STEP 4: Rewriting weakest section ({weakest})...")
        _metrics["warnings"].append(f"WEAKEST_SECTION_REWRITE:{weakest}")  # pyre-ignore[16]
        
        if weakest == "hook":
            hook, hook_score, _ = generate_winning_hook(client, selected_topic, selected_era)
            scores["hook_score"] = hook_score
        elif weakest == "context":
            context, context_score, _ = generate_winning_section(client, "context", hook, selected_topic, selected_era)
            scores["context_score"] = context_score
        elif weakest == "body":
            body, body_score, _ = generate_winning_section(client, "body", hook, selected_topic, selected_era)
            scores["body_score"] = body_score
        elif weakest == "outro":
            outro, outro_score, _ = generate_winning_section(client, "outro", hook, selected_topic, selected_era)
            scores["outro_score"] = outro_score
        
        # Re-assemble and re-evaluate
        script = assemble_script(hook, context, body, outro, selected_topic, selected_era, scores)
        final_eval = evaluate_full_script(client, script["voiceover_text"])
        final_score = final_eval.get("total", 8.0)
    
    # Final scores
    scores["final_score"] = final_score
    scores["weakest_section"] = final_eval.get("weakest_section", "none")
    scores["hook_kpi"] = hook_kpi  # pyre-ignore[6]: Add hook KPI to scores
    
    # Collect all stats
    all_stats = {
        "hook": hook_stats,
        "context": context_stats,
        "body": body_stats,
        "outro": outro_stats,
        "attempts": {
            "hook": hook_stats.get("iterations", 1),
            "context": context_stats.get("iterations", 1),
            "body": body_stats.get("iterations", 1),
            "outro": outro_stats.get("iterations", 1)
        }
    }
    
    # Get final metrics
    metrics = get_metrics()
    
    script["pipeline_scores"] = scores
    script["pipeline_stats"] = all_stats
    script["pipeline_metrics"] = metrics
    
    # Diversity tracking data
    diversity_data = {
        "topic_entity": topic_entity,
        "era": selected_era,
        "theme": "war" if any(w in selected_topic.lower() for w in ["war", "battle", "army", "soldier"]) else "general",
        "region": "europe" if any(w in selected_topic.lower() for w in ["rome", "greek", "ottoman", "napoleon", "viking"]) else "global",
        "recent_similarity": 0.0  # TODO: Calculate from similarity_dampener history
    }
    script["diversity_data"] = diversity_data
    
    # Log final metrics (single line JSON for CloudWatch)
    log_output = {
        "pipeline_version": "2.3",
        "mode": mode,
        "topic": selected_topic[:50],  # pyre-ignore[16]
        "topic_entity": topic_entity,
        "era": selected_era,
        "theme": diversity_data["theme"],
        "hook_score": hook_score,
        "context_score": context_score,
        "body_score": body_score,
        "outro_score": outro_score,
        "final_score": final_score,
        "hook_kpi": hook_kpi,  # YouTube behavior prediction
        "api_calls": metrics["api_calls"],
        "repair_count": metrics["repair_count"],
        "latency_ms": metrics.get("latency_ms", 0),
        "warnings": metrics["warnings"],
        "attempts": all_stats["attempts"],
        "diversity": {
            "entity": topic_entity,
            "era": selected_era,
            "gate_result": diversity_result["reason"] if diversity_result else "unknown",
            "similarity": diversity_result["similarity"] if diversity_result else 0.0
        }
    }
    print(f"\n📊 METRICS: {json.dumps(log_output)}")
    
    print(f"\n✅ Pipeline complete!")
    print(f"   Hook: {hook_score} | Context: {context_score} | Body: {body_score} | Outro: {outro_score}")
    print(f"   Final: {final_score} | API Calls: {metrics['api_calls']} | Latency: {metrics.get('latency_ms', 0)}ms")
    
    # Save to similarity history
    try:
        save_video_metadata(script, region_name=region)
    except Exception as e:
        print(f"⚠️ Failed to save similarity history: {e}")
    
    return script


# ============================================================================
# FALLBACK TO OLD SYSTEM
# ============================================================================

def generate_script_with_fallback(
    topic: Optional[str] = None,
    era: Optional[str] = None,
    region_name: Optional[str] = None,
    use_pipeline: bool = True,
    prompt_memory: Optional[dict] = None,
    logger_callback: Optional[Callable] = None
) -> dict:
    """
    Generate script with automatic fallback to old system.
    
    If pipeline fails or is disabled, falls back to script_gen.py.
    Adds warnings to output when fallback is used.
    
    Args:
        prompt_memory: DO/DON'T examples from autopilot for writer/evaluator prompts
    """
    if not use_pipeline:
        from script_gen import generate_history_script  # pyre-ignore[21]
        result = generate_history_script(topic=topic, era=era, region_name=region_name)
        result["pipeline_warnings"] = ["PIPELINE_DISABLED"]
        return result
    
    try:
        # Pass prompt_memory to pipeline (stored as global for prompt injection)
        if prompt_memory:
            global _prompt_memory
            _prompt_memory = prompt_memory
        return generate_script_pipeline(topic=topic, era=era, region_name=region_name, logger_callback=logger_callback)
    except Exception as e:
        print(f"⚠️ Pipeline failed, falling back to old system: {e}")
        
        # Track fallback in metrics
        global _metrics
        _metrics["fallback_used"] = True
        _metrics["warnings"].append(f"FALLBACK_USED:{str(e)[:50]}")  # pyre-ignore[16]
        
        from script_gen import generate_history_script  # pyre-ignore[21]
        result = generate_history_script(topic=topic, era=era, region_name=region_name)
        result["pipeline_warnings"] = ["FALLBACK_USED", str(e)[:100]]  # pyre-ignore[16]
        result["pipeline_metrics"] = get_metrics()
        
        # Log fallback event
        print(f"📊 FALLBACK_METRIC: {json.dumps({'fallback_used': True, 'reason': str(e)[:100]})}")  # pyre-ignore[16]
        
        return result


# ============================================================================
# CLI TEST
# ============================================================================

if __name__ == "__main__":
    import sys
    
    # Windows encoding fix
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding='utf-8')
    
    print("=" * 70)
    print("SCRIPT PIPELINE TEST")
    print("=" * 70)
    
    # Run pipeline
    result = generate_script_pipeline()
    
    print("\n" + "=" * 70)
    print("FINAL OUTPUT")
    print("=" * 70)
    print(json.dumps(result, indent=2, ensure_ascii=False))
