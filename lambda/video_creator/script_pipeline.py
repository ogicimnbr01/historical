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
"""

import json
import re
import random
import time
import os
import boto3
from typing import Optional, Dict, List, Tuple

# Import from existing modules for compatibility
from similarity_dampener import generate_similarity_policy, get_prompt_injection, save_video_metadata

# ============================================================================
# CONFIGURATION
# ============================================================================

# Temperature settings (critical for evaluation stability)
WRITER_TEMPERATURE = 0.8      # Creative generation
EVALUATOR_TEMPERATURE = 0.1   # Stable scoring

# Token limits (keep costs down)
WRITER_MAX_TOKENS = 600
EVALUATOR_MAX_TOKENS = 400

# Quality thresholds (QUALITY mode - default)
HOOK_THRESHOLD = 9.0          # Hook must score >= 9.0
SECTION_THRESHOLD = 8.5       # Each section must score >= 8.5
FINAL_THRESHOLD = 8.5         # Combined script must score >= 8.5

# Iteration limits
HOOK_MAX_ITERATIONS = 5       # Max hook refinement rounds
SECTION_MAX_ITERATIONS = 3    # Max section refinement rounds

# Retry settings for throttling
MAX_RETRIES = 5
INITIAL_BACKOFF = 0.5         # seconds
JITTER_MAX = 0.3              # Max random jitter (0-30% of backoff)

# Cost control limits
MAX_API_CALLS_PER_VIDEO = 18  # Hard limit - abort after this
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

# QUALITY mode: current defaults (stricter)
QUALITY_MODE_CONFIG = {
    "hook_threshold": 9.0,
    "section_threshold": 8.5,
    "final_threshold": 8.5,
    "hook_max_iterations": 5,
    "section_max_iterations": 3,
    "max_api_calls": 18
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
    return _active_config.get(key, QUALITY_MODE_CONFIG.get(key))

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

def check_diversity_gate(topic: str, topic_entity: str, region_name: str = None) -> dict:
    """
    Check if topic passes diversity gate.
    
    Returns:
        dict with 'allowed', 'similarity', 'reason'
    """
    try:
        from similarity_dampener import get_recent_videos, calculate_similarity
        
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
        return {"allowed": True, "similarity": 0.0, "reason": f"error:{str(e)[:30]}"}

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
    result = parse_json_safe(response, client, prompt)
    
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
    result = parse_json_safe(response, client, prompt)
    
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
    result = parse_json_safe(response, client, prompt)
    
    if result and "titles" in result:
        return result["titles"][:3]
    
    # Fallback: use topic as title
    return [topic[:60], topic[:60], topic[:60]]

# ============================================================================
# ANCHOR EXAMPLES FOR SCORE CALIBRATION
# ============================================================================

HOOK_ANCHOR_EXAMPLES = """
CALIBRATION EXAMPLES (use these to anchor your scoring):

SCORE 9-10 (Elite scroll-stoppers):
- "Australia sent soldiers with machine guns to kill birds. The birds won." (9.5)
- "Shakespeare made up Richard III's hunchback. The guy was fine." (9.0)
- "Cleopatra lived closer to the iPhone than to the pyramids." (9.5)

SCORE 4-5 (Weak/generic):
- "Did you know Napoleon wasn't actually short?" (4.0 - begging opener)
- "In 1453, the Ottoman Empire conquered Constantinople." (4.5 - boring date opener)
- "History has many interesting stories to tell." (3.0 - zero tension)
"""

SECTION_ANCHOR_EXAMPLES = """
CALIBRATION EXAMPLES:

SCORE 9-10 (Excellent sections):
- CONTEXT: "1932. Crops dying. Farmers desperate. The enemy? Twenty thousand emus." (9.0 - vivid stakes)
- BODY: "They fired. Emus scattered. Bullets hit nothing. The birds didn't flinch." (9.5 - punchy pacing)
- OUTRO: "The army retreated. The emus kept eating." (9.0 - perfect ironic punch)

SCORE 5-6 (Mediocre):
- CONTEXT: "This happened in Australia a long time ago when there were problems." (5.0 - vague)
- BODY: "The soldiers tried to shoot the emus but it didn't work very well." (5.5 - no punch)
- OUTRO: "And that's how the story ended." (4.0 - no impact)
"""

# ============================================================================
# PROMPTS
# ============================================================================

HOOK_GENERATOR_PROMPT = """You are a viral YouTube Shorts hook writer. Generate 3 different hooks for this topic.

TOPIC: {topic}
ERA: {era}

RULES:
- Each hook: 6-12 words
- Must create "Wait, WHAT?!" reaction
- Use: contradiction, shock, accusation, or paradox
- NO: "Did you know", "In [year]", "Have you ever wondered"
- Make them AGGRESSIVE scroll-stoppers

Return ONLY valid JSON:
{{"hooks": ["hook1", "hook2", "hook3"]}}"""

HOOK_EVALUATOR_PROMPT = """You are a strict YouTube Shorts hook evaluator. Score these hooks 0-10.

{anchor_examples}

HOOKS TO EVALUATE:
{hooks_json}

SCORING RUBRIC (be harsh, elite content only):
- tension (0-3): Does it create crisis/threat/contradiction?
- clarity (0-2): Understood in 1 second?
- scroll_stop (0-3): Would YOU stop scrolling?
- word_count (0-2): 6-9 words = 2, 10-12 = 1, other = 0

Return ONLY valid JSON:
{{
  "evaluations": [
    {{"hook": "...", "tension": X, "clarity": X, "scroll_stop": X, "word_count": X, "total": X, "fixes": ["..."]}},
    ...
  ]
}}"""

HOOK_REFINER_PROMPT = """Rewrite this hook to fix the issues. Keep it 6-12 words, punchy, scroll-stopping.

ORIGINAL HOOK: {hook}
ISSUES TO FIX: {fixes}

Return ONLY the new hook text, nothing else."""

SECTION_GENERATOR_PROMPT = """Generate 2 variants of the {section_type} section for this YouTube Short.

HOOK (already approved): {hook}
TOPIC: {topic}
ERA: {era}

SECTION TYPE: {section_type}
{section_rules}

Return ONLY valid JSON:
{{"variants": ["variant1", "variant2"]}}"""

SECTION_EVALUATOR_PROMPT = """Evaluate these {section_type} sections. Score 0-10.

{anchor_examples}

HOOK FOR CONTEXT: {hook}

VARIANTS TO EVALUATE:
{variants_json}

SCORING RUBRIC:
- clarity (0-3): Is the message crystal clear?
- pacing (0-3): Does it flow well, punchy sentences?
- punch (0-4): Does it hit hard, memorable?

Return ONLY valid JSON:
{{
  "evaluations": [
    {{"text": "...", "clarity": X, "pacing": X, "punch": X, "total": X, "fixes": ["..."]}},
    ...
  ]
}}"""

SECTION_REFINER_PROMPT = """Rewrite this {section_type} section to fix the issues.

ORIGINAL: {text}
ISSUES: {fixes}
HOOK CONTEXT: {hook}

Keep it punchy, short sentences, high impact.
Return ONLY the improved text, nothing else."""

FINAL_EVALUATOR_PROMPT = """Evaluate this complete YouTube Short script. Score 0-10.

FULL SCRIPT:
---
{full_script}
---

RUBRIC:
- hook_impact (0-2): Does hook grab attention?
- flow (0-3): Do sections connect smoothly?
- pacing (0-3): Is rhythm consistent, no drag?
- punch (0-2): Does outro land?

Return ONLY valid JSON:
{{"hook_impact": X, "flow": X, "pacing": X, "punch": X, "total": X, "weakest_section": "hook|context|body|outro", "fix_suggestion": "..."}}"""

SECTION_RULES = {
    "context": """
CONTEXT RULES (1-2 sentences):
- Set the stakes: who/where/what danger
- Make it VISUAL and SPECIFIC
- Create tension, not just information
- Max 25 words""",
    "body": """
BODY RULES (2-4 short sentences):
- Vivid specific details
- Escalate tension
- Short punchy sentences (5-8 words each)
- Max 40 words""",
    "outro": """
OUTRO RULES (1-2 sentences):
- Punch line that echoes
- Ironic reversal OR cold truth OR one-word punch
- Make them want to screenshot it
- Max 15 words"""
}

# ============================================================================
# BEDROCK CLIENT HELPERS
# ============================================================================

def get_bedrock_client(region_name: str = None):
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
        m["latency_ms"] = int((time.time() - m["start_time"]) * 1000)
        del m["start_time"]
    return m

def check_api_limit():
    """Check if we've exceeded max API calls. Raises exception if so."""
    if _metrics["api_calls"] >= MAX_API_CALLS_PER_VIDEO:
        _metrics["warnings"].append("MAX_API_CALLS_EXCEEDED")
        raise Exception(f"Exceeded max API calls limit ({MAX_API_CALLS_PER_VIDEO})")


def invoke_bedrock(
    client,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 500,
    system_prompt: str = None
) -> str:
    """
    Invoke Bedrock Claude with exponential backoff + jitter for throttling.
    
    Returns raw text response.
    """
    global _metrics
    
    # Check API call limit
    check_api_limit()
    
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    
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
            
            _metrics["api_calls"] += 1
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


def parse_json_safe(text: str, client=None, original_prompt: str = None) -> dict:
    """
    Parse JSON from Claude response with fail-safe repair.
    
    If parsing fails, attempts ONE JSON repair (max) or returns None.
    Tracks repair attempts in metrics.
    """
    global _metrics
    
    # Try direct parse first
    try:
        # Find JSON in response
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON array
    try:
        json_match = re.search(r'\[[\s\S]*\]', text)
        if json_match:
            return {"array": json.loads(json_match.group())}
    except json.JSONDecodeError:
        pass
    
    # Attempt JSON repair if client available (MAX 1 repair per call)
    if client and original_prompt and _metrics["repair_count"] < MAX_REPAIR_ATTEMPTS:
        try:
            _metrics["repair_count"] += 1
            print(f"🔧 Attempting JSON repair (repair #{_metrics['repair_count']})...")
            
            repair_prompt = f"""The following text should be valid JSON but has errors. 
Fix it and return ONLY the corrected JSON, nothing else:

{text}"""
            repaired = invoke_bedrock(client, repair_prompt, temperature=0.0, max_tokens=300)
            json_match = re.search(r'\{[\s\S]*\}', repaired)
            if json_match:
                result = json.loads(json_match.group())
                print(f"✅ JSON repair successful")
                return result
        except Exception as e:
            print(f"⚠️ JSON repair failed: {e}")
            _metrics["warnings"].append("JSON_REPAIR_FAILED")
    
    print(f"⚠️ JSON parse failed: {text[:100]}...")
    _metrics["warnings"].append("JSON_PARSE_FAILED")
    return None


# ============================================================================
# HOOK GENERATION & SCORING
# ============================================================================

def generate_hooks_batch(client, topic: str, era: str) -> List[str]:
    """Generate 3 hooks in a single API call."""
    prompt = HOOK_GENERATOR_PROMPT.format(topic=topic, era=era)
    
    response = invoke_bedrock(client, prompt, temperature=WRITER_TEMPERATURE, max_tokens=200)
    result = parse_json_safe(response, client, prompt)
    
    if result and "hooks" in result:
        return result["hooks"]
    
    # Fallback: try to extract hooks manually
    lines = [l.strip() for l in response.split('\n') if l.strip() and not l.startswith('{')]
    return lines[:3] if lines else ["Failed to generate hooks"]


def evaluate_hooks_batch(client, hooks: List[str]) -> List[dict]:
    """Evaluate multiple hooks in a single API call."""
    hooks_json = json.dumps(hooks, ensure_ascii=False)
    prompt = HOOK_EVALUATOR_PROMPT.format(
        anchor_examples=HOOK_ANCHOR_EXAMPLES,
        hooks_json=hooks_json
    )
    
    response = invoke_bedrock(client, prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=400)
    result = parse_json_safe(response, client, prompt)
    
    if result and "evaluations" in result:
        return result["evaluations"]
    
    # Fallback: return empty evaluations
    return [{"hook": h, "total": 5.0, "fixes": ["evaluation failed"]} for h in hooks]


def refine_hook(client, hook: str, fixes: List[str]) -> str:
    """Refine a single hook based on fixes."""
    prompt = HOOK_REFINER_PROMPT.format(hook=hook, fixes=", ".join(fixes))
    response = invoke_bedrock(client, prompt, temperature=WRITER_TEMPERATURE, max_tokens=50)
    
    # Clean up response
    cleaned = response.strip().strip('"').strip("'")
    return cleaned if cleaned else hook


def generate_winning_hook(client, topic: str, era: str) -> Tuple[str, float, dict]:
    """
    Generate hooks with iterative refinement until threshold met.
    
    Returns: (final_hook, final_score, stats)
    """
    stats = {"iterations": 0, "total_hooks_generated": 0}
    best_hook = None
    best_score = 0.0
    best_fixes = []
    
    for iteration in range(HOOK_MAX_ITERATIONS):
        stats["iterations"] = iteration + 1
        
        if iteration == 0:
            # First iteration: generate 3 hooks batch
            hooks = generate_hooks_batch(client, topic, era)
            stats["total_hooks_generated"] += len(hooks)
        else:
            # Refinement: refine best hook based on fixes
            refined = refine_hook(client, best_hook, best_fixes)
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
            best_clarity = best_fixes[0] if best_fixes and isinstance(best_fixes[0], (int, float)) else 0
            
            if is_tied and best_hook:
                # First: higher clarity wins
                if clarity > best_clarity:
                    is_better = True
                    print(f"    ↳ Tie-breaker: higher clarity ({clarity}) wins")
                # Second: if clarity same, shorter wins
                elif clarity == best_clarity and len(hook_text.split()) < len(best_hook.split()):
                    is_better = True
                    print(f"    ↳ Tie-breaker: shorter hook ({len(hook_text.split())} words)")
            
            if is_better:
                best_score = score
                best_hook = hook_text
                best_fixes = eval_item.get("fixes", [])
                # Store clarity for tie-breaking (hacky but efficient)
                if not best_fixes:
                    best_fixes = [clarity]
        
        print(f"  Hook iteration {iteration + 1}: best score = {best_score}")
        
        # Check if threshold met (mode-aware)
        threshold = get_threshold("hook_threshold")
        if best_score >= threshold:
            print(f"✅ Hook approved: {best_score} (threshold: {threshold})")
            break
    
    stats["final_score"] = best_score
    return best_hook, best_score, stats


# ============================================================================
# SECTION GENERATION & SCORING
# ============================================================================

def generate_section_variants(
    client, 
    section_type: str, 
    hook: str, 
    topic: str, 
    era: str
) -> List[str]:
    """Generate 2 variants of a section in a single API call."""
    prompt = SECTION_GENERATOR_PROMPT.format(
        section_type=section_type.upper(),
        hook=hook,
        topic=topic,
        era=era,
        section_rules=SECTION_RULES.get(section_type, "")
    )
    
    response = invoke_bedrock(client, prompt, temperature=WRITER_TEMPERATURE, max_tokens=300)
    result = parse_json_safe(response, client, prompt)
    
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
    """Evaluate section variants in a single API call."""
    variants_json = json.dumps(variants, ensure_ascii=False)
    prompt = SECTION_EVALUATOR_PROMPT.format(
        section_type=section_type.upper(),
        anchor_examples=SECTION_ANCHOR_EXAMPLES,
        hook=hook,
        variants_json=variants_json
    )
    
    response = invoke_bedrock(client, prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=400)
    result = parse_json_safe(response, client, prompt)
    
    if result and "evaluations" in result:
        return result["evaluations"]
    
    return [{"text": v, "total": 6.0, "fixes": ["evaluation failed"]} for v in variants]


def refine_section(
    client, 
    section_type: str, 
    text: str, 
    fixes: List[str], 
    hook: str
) -> str:
    """Refine a section based on fixes."""
    prompt = SECTION_REFINER_PROMPT.format(
        section_type=section_type.upper(),
        text=text,
        fixes=", ".join(fixes),
        hook=hook
    )
    response = invoke_bedrock(client, prompt, temperature=WRITER_TEMPERATURE, max_tokens=150)
    return response.strip()


def generate_winning_section(
    client, 
    section_type: str, 
    hook: str, 
    topic: str, 
    era: str
) -> Tuple[str, float, dict]:
    """
    Generate section with iterative refinement.
    
    Returns: (final_text, final_score, stats)
    """
    stats = {"iterations": 0, "variants_generated": 0}
    best_text = None
    best_score = 0.0
    best_fixes = []
    
    for iteration in range(SECTION_MAX_ITERATIONS):
        stats["iterations"] = iteration + 1
        
        if iteration == 0:
            # First iteration: generate 2 variants
            variants = generate_section_variants(client, section_type, hook, topic, era)
            stats["variants_generated"] += len(variants)
        else:
            # Refinement
            refined = refine_section(client, section_type, best_text, best_fixes, hook)
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
                elif section_type == "context" and len(text.split()) < len(best_text.split()):
                    is_better = True  # Clearer = shorter for context
                    print(f"    ↳ Tie-breaker: clearer (shorter) context selected")
            
            if is_better or (is_tied and not best_text):
                best_score = score
                best_text = text
                best_fixes = eval_item.get("fixes", [])
                best_punch = punch
        
        print(f"  {section_type.upper()} iteration {iteration + 1}: best score = {best_score}")
        
        if best_score >= SECTION_THRESHOLD:
            print(f"✅ {section_type.upper()} approved: {best_score}")
            break
    
    stats["final_score"] = best_score
    return best_text, best_score, stats


# ============================================================================
# FINAL ASSEMBLY & EVALUATION
# ============================================================================

def evaluate_full_script(client, full_script: str) -> dict:
    """Evaluate the complete assembled script."""
    prompt = FINAL_EVALUATOR_PROMPT.format(full_script=full_script)
    response = invoke_bedrock(client, prompt, temperature=EVALUATOR_TEMPERATURE, max_tokens=200)
    result = parse_json_safe(response, client, prompt)
    
    if result:
        return result
    
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
    safe_title = re.sub(r'[-\s]+', '_', safe_title).strip('_')[:50]
    
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
        "title": f"{topic[:40]} 📜",
        "safe_title": safe_title,
        "voiceover_text": full_text.replace('\n\n', ' '),
        "segments": [
            {
                "start": 0,
                "end": round(hook_end, 1),
                "text": hook,
                "image_prompt": f"{topic}, dramatic opening scene, {era_style}, 9:16 vertical composition"
            },
            {
                "start": round(hook_end, 1),
                "end": round(context_end, 1),
                "text": context,
                "image_prompt": f"{topic}, historical context scene, {era_style}, 9:16 vertical composition"
            },
            {
                "start": round(context_end, 1),
                "end": round(body_end, 1),
                "text": body,
                "image_prompt": f"{topic}, main action scene, {era_style}, dramatic lighting, 9:16 vertical composition"
            },
            {
                "start": round(body_end, 1),
                "end": round(total_duration, 1),
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
    topic: str = None, 
    era: str = None, 
    region_name: str = None,
    mode: str = "quality"
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
        selected_era = normalize_era(selected_era)
        
        # Extract topic entity for diversity tracking
        topic_words = selected_topic.split()
        topic_entity = topic_words[0] if topic_words else "unknown"
        # Try to find proper noun (capitalized word after first)
        for word in topic_words[1:5]:
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
            _metrics["warnings"].append(f"DIVERSITY_BLOCKED:{diversity_result['reason']}")
            if topic and topic_attempt == 0:
                print("↳ User-specified topic blocked, trying random...")
    else:
        # All attempts failed, force through with warning
        print("⚠️ Max topic attempts reached, proceeding with last selection")
        _metrics["warnings"].append("DIVERSITY_GATE_FORCED")
    
    print(f"📜 Topic: {selected_topic}")
    print(f"🕰️ Era: {selected_era} (normalized)")
    print(f"👤 Entity: {topic_entity}")
    
    # Step 1: Generate winning hook
    print("\n🔥 STEP 1: Generating hook...")
    hook, hook_score, hook_stats = generate_winning_hook(client, selected_topic, selected_era)
    print(f"   Final hook ({hook_score}): {hook}")
    
    # Step 1.5: Evaluate hook KPI metrics (YouTube behavior prediction)
    print("\n📊 STEP 1.5: Evaluating hook KPI...")
    hook_kpi = evaluate_hook_kpi(client, hook)
    print(f"   instant_clarity: {hook_kpi['instant_clarity']} | curiosity_gap: {hook_kpi['curiosity_gap']}")
    print(f"   swipe_risk: {hook_kpi['swipe_risk']} (higher=less swipe) | predicted_retention: {hook_kpi['predicted_retention']}%")
    
    # Step 2: Generate sections
    print("\n📝 STEP 2: Generating sections...")
    
    context, context_score, context_stats = generate_winning_section(
        client, "context", hook, selected_topic, selected_era
    )
    
    body, body_score, body_stats = generate_winning_section(
        client, "body", hook, selected_topic, selected_era
    )
    
    outro, outro_score, outro_stats = generate_winning_section(
        client, "outro", hook, selected_topic, selected_era
    )
    
    # Step 3: Assemble and final eval
    print("\n🎯 STEP 3: Final assembly and evaluation...")
    
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
        _metrics["warnings"].append(f"WEAKEST_SECTION_REWRITE:{weakest}")
        
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
    scores["hook_kpi"] = hook_kpi  # Add hook KPI to scores
    
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
        "topic": selected_topic[:50],
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
    topic: str = None,
    era: str = None,
    region_name: str = None,
    use_pipeline: bool = True
) -> dict:
    """
    Generate script with automatic fallback to old system.
    
    If pipeline fails or is disabled, falls back to script_gen.py.
    Adds warnings to output when fallback is used.
    """
    if not use_pipeline:
        from script_gen import generate_history_script
        result = generate_history_script(topic=topic, era=era, region_name=region_name)
        result["pipeline_warnings"] = ["PIPELINE_DISABLED"]
        return result
    
    try:
        return generate_script_pipeline(topic=topic, era=era, region_name=region_name)
    except Exception as e:
        print(f"⚠️ Pipeline failed, falling back to old system: {e}")
        
        # Track fallback in metrics
        global _metrics
        _metrics["fallback_used"] = True
        _metrics["warnings"].append(f"FALLBACK_USED:{str(e)[:50]}")
        
        from script_gen import generate_history_script
        result = generate_history_script(topic=topic, era=era, region_name=region_name)
        result["pipeline_warnings"] = ["FALLBACK_USED", str(e)[:100]]
        result["pipeline_metrics"] = get_metrics()
        
        # Log fallback event
        print(f"📊 FALLBACK_METRIC: {json.dumps({'fallback_used': True, 'reason': str(e)[:100]})}")
        
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
