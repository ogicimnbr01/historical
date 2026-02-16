"""
History Shorts Script Generator using AWS Bedrock (Claude)
Generates engaging historical content for YouTube Shorts
Global audience, English language, fascinating facts about leaders, battles, and civilizations
"""

import json
import re
import random
import boto3  # pyre-ignore[21]: third-party module without configured stubs
import os
from typing import Optional

# Similarity Dampener for content variety
from similarity_dampener import generate_similarity_policy, get_prompt_injection, save_video_metadata  # pyre-ignore[21]: local module

# Era-specific context for visual generation
ERA_VISUAL_STYLES = {
    "ancient": "ancient world, classical era, marble statues, bronze age, photorealistic painting style",
    "medieval": "medieval era, castle, knights, feudal, oil painting style, dramatic lighting",
    "ottoman": "Ottoman Empire, Islamic architecture, sultans, 16th-19th century, orientalist painting style",
    "renaissance": "Renaissance era, European courts, 15th-16th century, oil painting masterpiece style",
    "18th_century": "18th century, colonial era, Enlightenment, classical portrait style",
    "19th_century": "19th century, Victorian era, industrial age, vintage photograph style, sepia tone",
    "early_20th": "early 20th century, 1900s-1940s, black and white vintage photograph, film grain",
    "ww1": "World War I, 1914-1918, trenches, soldiers, grainy black and white war photography",
    "ww2": "World War II, 1939-1945, military, dramatic black and white photography",
    "modern": "mid 20th century, 1950s-1980s, color photograph, vintage film look"
}

# Sample topics for random generation (can be overridden by input)
SAMPLE_TOPICS = [
    # Turkish History (for testing)
    {"topic": "Mehmed the Conqueror and Constantinople", "era": "medieval", "figure": "Mehmed II"},
    {"topic": "Suleiman the Magnificent's daily routine", "era": "ottoman", "figure": "Suleiman I"},
    {"topic": "Atatürk's favorite foods", "era": "early_20th", "figure": "Mustafa Kemal Atatürk"},
    {"topic": "The Fall of Constantinople 1453", "era": "medieval", "figure": "Mehmed II"},
    {"topic": "Barbarossa the Ottoman Admiral", "era": "ottoman", "figure": "Hayreddin Barbarossa"},
    
    # World History (global appeal)
    {"topic": "Julius Caesar's last words", "era": "ancient", "figure": "Julius Caesar"},
    {"topic": "Napoleon's height myth", "era": "19th_century", "figure": "Napoleon Bonaparte"},
    {"topic": "Cleopatra's true appearance", "era": "ancient", "figure": "Cleopatra VII"},
    {"topic": "Alexander the Great's undefeated streak", "era": "ancient", "figure": "Alexander the Great"},
    {"topic": "Richard the Lionheart and Saladin's respect", "era": "medieval", "figure": "Richard I"},
    {"topic": "Genghis Khan's postal system", "era": "medieval", "figure": "Genghis Khan"},
    {"topic": "Queen Victoria's strict mourning", "era": "19th_century", "figure": "Queen Victoria"},
    {"topic": "Spartans' brutal training", "era": "ancient", "figure": "Spartan warriors"},
    {"topic": "Vikings were surprisingly hygienic", "era": "medieval", "figure": "Viking warriors"},
    {"topic": "Samurai's unexpected poetry skills", "era": "medieval", "figure": "Samurai"},
]

# Visual prompt templates for different content types
VISUAL_TEMPLATES = {
    "leader_portrait": "{figure}, portrait, regal pose, {era_style}, dramatic lighting, highly detailed, 9:16 vertical composition",
    "leader_action": "{figure}, {action}, {era_style}, cinematic composition, 9:16 vertical",
    "battle_scene": "Epic battle scene, {context}, {era_style}, dramatic, soldiers, warfare, 9:16 vertical",
    "location": "{location}, {era_style}, atmospheric, moody lighting, 9:16 vertical composition",
    "artifact": "Historical artifact, {item}, {era_style}, museum quality, detailed, 9:16 vertical",
}

SYSTEM_PROMPT = """You are a master historical storyteller creating viral YouTube Shorts content.
Your videos reveal fascinating, lesser-known facts about history that make viewers say "I never knew that!"

🎯 CORE PHILOSOPHY:
- Make history DRAMATIC, not just interesting
- Every story needs TENSION, CRISIS, or THREAT
- Focus on human weakness: fears, obsessions, sleepless nights, secret shames
- Create ESCALATION: problem → danger → consequence
- The viewer must feel "I NEED to know what happens"

⚠️ THE 7 UNBREAKABLE RULES:
1. NEVER be academic or "educational" tone ("In 1453, the Ottoman forces...")
2. NEVER just give information - CREATE TENSION first
3. ALWAYS start with a CRISIS, THREAT, PARADOX, or MYSTERY
4. ALWAYS escalate the stakes before revealing the answer
5. NEVER be longer than 15 seconds when read aloud
6. MAXIMUM 450 CHARACTERS (Strict Limit) - ~40-50 words
7. MAXIMUM 7-8 WORDS PER SENTENCE - Punchy, short, impactful
8. Hook must be a SCROLL STOPPER - not documentary intro

📝 EXACT SCRIPT STRUCTURE (Total 15 seconds, 4 segments):

1. HOOK (0-3s) - SCROLL STOPPER = SLAP IN THE FACE:
   ⚡ THE HOOK MUST HIT LIKE A PUNCH. ONE SENTENCE. BRUTAL.
   ⚡ Create "Wait, WHAT?!" reaction - not just "hmm interesting"
   ⚡ The viewer must feel CHALLENGED, ACCUSED, or SHOCKED
   ⚡ IDEAL: 6-8 WORDS. Start with ACTION or PARADOX.
   
   🔥 BRUTALLY EFFECTIVE HOOK FORMULAS:
   
   ACCUSATION HOOKS (hardest hitting):
   ✅ "Shakespeare lied to you." (4 words - needs shock verb)
   ✅ "Everything you know is wrong." (5 words)
   ✅ "The history books are lying." (5 words)
   
   ACTION OPENER HOOKS (start with specific action):
   ✅ "He killed 10,000 men. Alone." (6 words)
   ✅ "She poisoned three emperors before breakfast." (6 words)
   ✅ "They killed with swords. Wrote with brushes." (7 words)
   
   PARADOX HOOKS:
   ✅ "The deadliest emperor died of cheese." (6 words)
   ✅ "He conquered the world. Died crying." (6 words)
   ✅ "The conqueror couldn't conquer his own mind." (7 words)
   
   🚫 BANNED HOOK PATTERNS (NEVER USE):
   ❌ "They were enemies..." / "They were sworn enemies..." (DOCUMENTARY INTRO - BANNED)
   ❌ "In 1066..." / "In 1453..." / Any year-starting (BORING INTRO - BANNED)
   ❌ "He was a king..." / "She was a queen..." (WEAK INTRO - BANNED)
   ❌ "Did you know..." / "Have you ever..." (BEGGING - BANNED)
   ❌ "There once was..." / "Once upon a time..." (FAIRY TALE - BANNED)

⚠️ ABSOLUTE BAN ON MODERN REFERENCES:
   ❌ NEVER mention: social media, internet, smartphone, TikTok, Instagram
   ❌ NEVER compare to modern things for "relatability"
   ❌ Keep the viewer IN the historical atmosphere
   ❌ Instead of "more than you spend on social media" → "more than most spend training"

2. CONTEXT (3-7s) - ESCALATE THE DANGER:
   ⚡ Don't just give context - RAISE THE STAKES
   ⚡ Show what could go WRONG, who could DIE, what could FALL
   
   ✅ "At the height of his power, the Ottoman throne began to slip."
   ✅ "His advisors watched. His enemies waited. His mind... was breaking."
   ✅ "One wrong decision in this state meant war. Or worse."
   
   ❌ "He was an important ruler of the Ottoman Empire" (boring context)
   ❌ "Sleeplessness became a serious issue" (academic, no tension)

3. FACT (7-12s) - THE REVELATION (with emotional weight):
   ⚡ The surprising fact must feel EARNED after the tension
   ⚡ Include SPECIFIC, VISUAL details that stick
   
   ✅ "He would walk the palace halls at 3am, alone, talking to shadows."
   ✅ "His doctors tried opium, herbs, prayers. Nothing worked."
   Make it VISUAL and HAUNTING. This is the payoff.

4. OUTRO (12-15s) - THE TOK CÜMLE (punch line that echoes):
   ⚡ END WITH A LINE THAT HITS LIKE A DOOR SLAMMING SHUT
   ⚡ This line should HAUNT the viewer. They should want to screenshot it.
   ⚡ MAX 5-6 WORDS. Shorter = More powerful. This is the KILL SHOT.
   
   ⚠️ ROTATE BETWEEN THESE ENDING FAMILIES (don't repeat same type):
   
   🏆 DARK WISDOM (betrayal/death stories):
   ✅ "The deepest wounds don't bleed." (5 words)
   ✅ "Betrayal hurts more than steel." (5 words)
   
   🏆 COLD TRUTHS (myth-busting):
   ✅ "Legends lie. History doesn't care." (5 words)
   ✅ "The truth is always darker." (5 words)
   
   🏆 POWER STATEMENTS (empire/war):
   ✅ "Empires die. Mercy survives." (4 words)
   ✅ "Victory fades. Respect echoes." (4 words)
   
   🏆 IRONIC REVERSAL (unexpected twist):
   ✅ "The conqueror died crying." (4 words)
   ✅ "The hero was the villain." (5 words)
   ✅ "The winner lost everything." (4 words)
   
   🏆 HISTORICAL ECHO (connects past to present):
   ✅ "We still do the same thing." (6 words)
   ✅ "Nothing has changed since." (4 words)
   ✅ "History keeps repeating this lesson." (5 words)
   
   🏆 ONE-WORD PUNCH (single word impact):
   ✅ "Power." (1 word)
   ✅ "Mercy. Fear. Respect." (3 words)
   ✅ "Legacy." (1 word)
   
   🏆 CONTRAST PUNCH (two opposites):
   ✅ "The blade was duty. The poem was soul." (8 words)
   ✅ "Empires crumble. Stories survive." (4 words)
   
   ❌ "Some betrayals cut deeper than daggers." (TOO COMMON - BANNED)
   ❌ "And that's the story of..." (weak - BANNED)
   ❌ "Interesting, right?" (begging - BANNED)

⚠️ HOOK VARIETY - DON'T ALWAYS USE "LIED TO YOU":
   
   ACCUSATION (25% of videos):
   ✅ "Shakespeare lied to you."
   ✅ "Hollywood sold you a lie."
   
   ACTION OPENER (25% of videos):
   ✅ "This man killed 10,000 soldiers. Alone."
   ✅ "She poisoned three emperors."
   
   PARADOX (25% of videos):
   ✅ "The deadliest emperor died of cheese."
   ✅ "The richest man died poor."
   
   REVELATION (25% of videos):
   ✅ "No one talks about what happened next."
   ✅ "The ending was never told."

🎨 VISUAL PROMPTS:
For each segment, generate an image_prompt that describes what should be shown.
- Use specific historical details
- Include era-appropriate styling (mention "black and white vintage" for 20th century)
- Always end with "9:16 vertical composition"
- Include the historical figure's name for AI recognition

⚠️ CRITICAL: VISUAL-TEXT ALIGNMENT
When the text mentions ABSTRACT concepts (myths, lies, fiction, legends), the image MUST reflect this:

WRONG: "Shakespeare made that up" → Image of Caesar again
RIGHT: "Shakespeare made that up" → "Quill pen writing on parchment, theatrical stage mask, playwright's desk, vintage theater setting"

ABSTRACT VISUAL RULES:
- Myth/Lie/Fiction → old books, quill pens, theater masks, scrolls
- Time passing → hourglass, sundial, seasons changing
- Memory/Legacy → statues, monuments, fading portraits
- Power/Authority → crowns, thrones, scepters (without specific person)
- Death/Ending → sunset, fallen leaves, empty throne, closed book

Example image_prompt for Ottoman era:
"Sultan Suleiman the Magnificent sitting at breakfast table, Ottoman palace interior, 16th century, oriental painting style, golden light, 9:16 vertical composition"

🎵 MOOD SELECTION:
- "documentary" - Standard narration for most content
- "epic" - For battles, conquests, dramatic moments
- "nostalgic" - For personal stories, human moments, losses

✨ PERFECT EXAMPLE:

Topic: "Atatürk's favorite foods"

{
    "title": "The Founder's Simple Table 🍽️",
    "voiceover_text": "He built a nation from the ashes of an empire. But at dinner, Mustafa Kemal Atatürk wanted just one thing: his mother's home cooking. While world leaders dined on caviar, he asked for beans and rice. The man who changed everything... never changed his taste.",
    "segments": [
        {"start": 0, "end": 3, "text": "He built a nation from the ashes of an empire.", "image_prompt": "Mustafa Kemal Atatürk standing heroically, Turkish flag, 1920s black and white vintage photograph style, dramatic lighting, 9:16 vertical composition"},
        {"start": 3, "end": 7, "text": "But at dinner, Mustafa Kemal Atatürk wanted just one thing: his mother's home cooking.", "image_prompt": "Mustafa Kemal Atatürk sitting at modest dinner table, 1930s Turkish home interior, warm lighting, vintage photograph style, sepia tone, 9:16 vertical composition"},
        {"start": 7, "end": 12, "text": "While world leaders dined on caviar, he asked for beans and rice.", "image_prompt": "Simple Turkish dinner table with beans pilaf bread, modest setting, 1930s style, warm homey atmosphere, vintage photograph, 9:16 vertical composition"},
        {"start": 12, "end": 15, "text": "The man who changed everything... Would you give up luxury for your roots?", "image_prompt": "Mustafa Kemal Atatürk portrait, thoughtful expression, 1930s black and white photograph, film grain, presidential, 9:16 vertical composition"}
    ],
    "mood": "nostalgic",
    "era": "early_20th",
    "music_style": "nostalgic_piano"
}

⚠️ ABSOLUTELY BANNED:
- "Did you know..." openings
- Listing dates first ("In 1453...")
- Generic descriptions ("He was a great leader")
- Modern slang or anachronisms
- Questions that don't add value ("Interesting, right?")

REMEMBER: You're not teaching history class. You're telling a story that makes someone stop scrolling."""


def generate_history_script(topic: Optional[str] = None, era: Optional[str] = None, region_name: Optional[str] = None) -> dict:
    """
    Generate a history-themed script for YouTube Shorts using AWS Bedrock Claude
    
    Args:
        topic: Optional specific topic (e.g., "Atatürk's favorite foods")
        era: Optional era for visual styling
        region_name: AWS region for Bedrock (default: us-east-1)
        
    Returns:
        dict with title, voiceover_text, segments with image_prompts, mood, era
    """
    import os
    
    region = region_name or os.environ.get('AWS_REGION_NAME', 'us-east-1')
    
    # Initialize Bedrock client
    bedrock = boto3.client(
        service_name='bedrock-runtime',
        region_name=region
    )
    
    # Select topic
    if topic:
        selected_topic = {"topic": topic, "era": era or "early_20th", "figure": "historical figure"}
    else:
        selected_topic = random.choice(SAMPLE_TOPICS)
    
    # Get era-specific visual style
    era_style = ERA_VISUAL_STYLES.get(selected_topic["era"], ERA_VISUAL_STYLES["early_20th"])
    
    # Generate similarity policy (avoid repetitive content)
    try:
        similarity_policy = generate_similarity_policy(region_name=region)
        similarity_injection = get_prompt_injection(similarity_policy)
    except Exception as e:
        print(f"⚠️ Similarity check skipped: {e}")
        similarity_injection = ""
    
    user_prompt = f"""Create a 15 second YouTube Short script about: {selected_topic["topic"]}

HISTORICAL FIGURE: {selected_topic.get("figure", "Unknown")}
ERA: {selected_topic["era"]}
ERA VISUAL STYLE: {era_style}

Return a JSON object with:
{{
    "title": "Catchy title with one emoji (max 50 chars)",
    "voiceover_text": "The complete flowing script (all 4 parts combined, ~40-50 words max)",
    "segments": [
        {{"start": 0, "end": 3, "text": "[hook - contrast/curiosity]", "image_prompt": "[detailed AI image prompt with era style]"}},
        {{"start": 3, "end": 7, "text": "[context - set the stage]", "image_prompt": "[detailed AI image prompt]"}},
        {{"start": 7, "end": 12, "text": "[fact - the surprising revelation]", "image_prompt": "[detailed AI image prompt]"}},
        {{"start": 12, "end": 15, "text": "[outro - poetic ending]", "image_prompt": "[detailed AI image prompt]"}}
    ],
    "mood": "documentary|epic|nostalgic",
    "era": "{selected_topic["era"]}",
    "music_style": "epic_orchestral|nostalgic_piano|dramatic_strings|war_drums"
}}

🎯 MANDATORY STRUCTURE:
1. HOOK (0-3s): Create CONTRAST or CURIOSITY - NOT "Did you know..."
2. CONTEXT (3-7s): Brief historical context with vivid details
3. FACT (7-12s): The surprising, specific revelation
4. OUTRO (12-15s): Short, poetic, memorable ending

🎨 IMAGE PROMPT REQUIREMENTS:
- Include the historical figure's name if applicable
- Include era-specific styling: {era_style}
- Always end with "9:16 vertical composition"
- Be specific and vivid, good for AI image generation
{similarity_injection}
Total script should be ~40-50 words, readable in 15 seconds at natural pace.
Make it FASCINATING. Make viewers stop scrolling."""

    # Prepare request for Claude on Bedrock
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 800,
        "temperature": 0.7,  # Slightly higher for creativity
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": user_prompt
            }
        ]
    }
    
    # Get model ID from environment or use default (secure - not logged)
    # Claude 4.5 Sonnet - cross-region inference profile (us. prefix required)
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    
    # Log masked model info for security
    model_family = model_id.split('.')[1].split('-')[0] if '.' in model_id else 'claude'
    print(f"🤖 Using AI model: {model_family}-***")
    
    # Call Claude via Bedrock
    response = bedrock.invoke_model(
        modelId=model_id,
        body=json.dumps(request_body),
        contentType="application/json",
        accept="application/json"
    )
    
    # Parse response
    response_body = json.loads(response['body'].read())
    content = response_body['content'][0]['text']
    
    # Extract JSON from response
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        script = json.loads(json_match.group())
    else:
        script = json.loads(content)
    
    # ========== HOOK QUALITY VALIDATION ==========
    # Check for weak hook patterns and enforce 15s minimum
    script = validate_and_fix_script(script, selected_topic)
    
    # Ensure we have the era info
    if 'era' not in script:
        script['era'] = selected_topic["era"]
    
    # Ensure we have mood
    if 'mood' not in script:
        script['mood'] = 'documentary'
    
    # Ensure we have music_style
    if 'music_style' not in script:
        script['music_style'] = 'nostalgic_piano'
    
    # Add safe title for filename
    safe_title = re.sub(r'[^\w\s-]', '', script['title'])
    safe_title = re.sub(r'[-\s]+', '_', safe_title).strip('_')[:50]  # pyre-ignore[16]
    script['safe_title'] = safe_title
    
    # Add original topic for reference
    script['original_topic'] = selected_topic["topic"]
    
    print(f"📜 Generated history script: {script['title']}")
    print(f"   Era: {script['era']}, Mood: {script['mood']}")
    
    # ========== LENGTH VALIDATION ==========
    # Check if script exceeds limits and shorten if necessary
    char_count = len(script.get('voiceover_text', ''))
    
    if char_count > 450:
        print(f"⚠️ Generated script too long ({char_count} chars > 450 limit). Triggering auto-shortener...")
        script = shorten_script(script, region)
    
    # Double check after shortening
    final_char_count = len(script.get('voiceover_text', ''))
    if final_char_count > 480: # Hard limit tolerance
         print(f"⚠️ Script still too long ({final_char_count}). Forcing truncation warning.")
    
    return script


def validate_and_fix_script(script: dict, topic_info: dict) -> dict:
    """
    Validate script quality and ensure minimum requirements.
    
    Checks:
    1. Hook must NOT contain weak patterns (blacklist)
    2. Hook SHOULD match strong patterns (whitelist bonus)
    3. Hook must be max 12 words (8-9 is golden zone)
    4. Smart 15s handling - only extend if ending is poetic
    5. Flexible word count - check density, not just count
    """
    
    # ===== WEAK HOOK PATTERNS (BLACKLIST) =====
    # These patterns are BANNED - documentary/weak intros
    WEAK_PATTERNS = [
        # Begging patterns
        r"^did you know",
        r"^have you ever wondered",
        r"^what if i told you",
        r"^imagine if",
        # Documentary intros (BANNED)
        r"^they were enemies",
        r"^they were sworn enemies",
        r"^he was a king",
        r"^she was a queen",
        r"^he was an emperor",
        r"^in \d{3,4}",  # Matches "In 1453", "In 1066", etc.
        # Weak intros
        r"^today we",
        r"^let me tell you",
        r"^in this video",
        r"^here's a fun fact",
        r"^fun fact:",
        r"^everyone knows",
        r"^you probably know",
        r"^there once was",
        r"^once upon a time",
    ]
    
    # ===== STRONG HOOK PATTERNS (WHITELIST) =====
    # These patterns drive high retention - reward them
    STRONG_PATTERNS = [
        r"was a lie",
        r"never happened",
        r"got this wrong",
        r"didn't happen",
        r"weren't what you",
        r"wasn't what you",
        r"history lied",
        r"didn't die",
        r"didn't say",
        r"everyone remembers.*wrong",
        r"the truth is",
    ]
    
    # ===== CHECK HOOK QUALITY =====
    hook_score: int = 0  # Track hook quality
    
    if 'segments' in script and len(script['segments']) > 0:
        hook_text = script['segments'][0].get('text', '').lower().strip()
        
        # Check for weak patterns (blacklist)
        for pattern in WEAK_PATTERNS:
            if re.match(pattern, hook_text, re.IGNORECASE):
                print(f"❌ WEAK HOOK DETECTED: '{hook_text[:50]}...'")
                print(f"   Pattern matched: {pattern}")
                hook_score -= 2  # pyre-ignore[58]
        
        # Check for strong patterns (whitelist) - BONUS
        for pattern in STRONG_PATTERNS:
            if re.search(pattern, hook_text, re.IGNORECASE):
                print(f"🔥 STRONG HOOK PATTERN: '{pattern}' found!")
                hook_score += 2  # pyre-ignore[58]
                break  # Only count once
        
        # Check hook word count - STRICTER RULES
        # Minimum: 6 words
        # Ideal: 6-9 words (golden zone)
        # 4-5 words: ONLY allowed with shock verbs (lied, killed, fake, etc.)
        hook_words = len(hook_text.split())
        
        SHOCK_VERBS = ["lied", "killed", "died", "fake", "wrong", "lie", "never", "didn't", "wasn't", "weren't", "sold", "myth", "savages", "monster", "destroyed", "betrayed"]
        has_shock_verb = any(verb in hook_text for verb in SHOCK_VERBS)
        
        if hook_words >= 6 and hook_words <= 9:
            print(f"✅ HOOK GOLDEN ZONE: {hook_words} words (ideal 6-9)")
            hook_score += 1  # pyre-ignore[58]
        elif hook_words >= 4 and hook_words <= 5 and has_shock_verb:
            print(f"⚡ HOOK SHORT BUT PUNCHY: {hook_words} words (shock verb detected)")
            hook_score += 1  # Still good if shock verb present  # pyre-ignore[58]
        elif hook_words >= 4 and hook_words <= 5:
            print(f"⚠️ HOOK TOO SHORT: {hook_words} words (min 6, or needs shock verb)")
            hook_score -= 1  # Penalize short hooks without shock verb  # pyre-ignore[58]
        elif hook_words <= 12:
            print(f"✅ HOOK OK: {hook_words} words")
        else:
            print(f"⚠️ HOOK TOO LONG: {hook_words} words (max 12)")
            hook_score -= 1  # pyre-ignore[58]
        
        # Log final hook score
        if hook_score >= 2:
            print(f"🏆 HOOK QUALITY: EXCELLENT ({hook_score})")
        elif hook_score >= 0:
            print(f"✅ HOOK QUALITY: GOOD ({hook_score})")
        else:
            print(f"⚠️ HOOK QUALITY: NEEDS WORK ({hook_score})")
    
    # ===== SMART 15 SECOND HANDLING =====
    # Only extend if ending has poetic content
    if 'segments' in script:
        last_segment = script['segments'][-1]
        last_text = last_segment.get('text', '').lower()
        
        # Check if ending is poetic/memorable (worth extending)
        POETIC_INDICATORS = [
            r"legend",
            r"history",
            r"remember",
            r"never forget",
            r"sources speak",
            r"truth",
            r"\.\.\.",  # Ellipsis
            r"\?$",     # Question mark at end
            r"would you",
            r"could you",
        ]
        
        is_poetic_ending = any(re.search(p, last_text) for p in POETIC_INDICATORS)
        current_end = last_segment.get('end', 15)
        
        if current_end < 15:
            if is_poetic_ending:
                print(f"✅ EXTENDING to 15s - poetic ending detected")
                last_segment['end'] = 15
            else:
                print(f"⚡ KEEPING SHORT ({current_end}s) - no poetic ending, shorter is better")
                # Don't extend - let it be punchy
        
        # Ensure proper segment timing based on actual duration
        total_duration = last_segment.get('end', 15)
        if total_duration >= 15:
            expected_timings = [(0, 3), (3, 7), (7, 12), (12, 15)]
        else:
            # Proportional timing for shorter videos
            segment_ratios = [0.2, 0.27, 0.33, 0.2]  # 20%, 27%, 33%, 20%
            expected_timings = []
            current = 0
            for ratio in segment_ratios:
                duration = total_duration * ratio
                expected_timings.append((current, current + duration))
                current += duration
        
        for i, (expected_start, expected_end) in enumerate(expected_timings):
            if i < len(script['segments']):
                script['segments'][i]['start'] = round(float(expected_start), 1)  # pyre-ignore[6]
                script['segments'][i]['end'] = round(float(expected_end), 1)  # pyre-ignore[6]
    
    # ===== FLEXIBLE WORD COUNT (DENSITY CHECK) =====
    if 'voiceover_text' in script:
        voiceover = script['voiceover_text']
        word_count = len(voiceover.split())
        
        # Count sentences (rough)
        sentences = len(re.findall(r'[.!?]', voiceover))
        sentences = max(sentences, 1)  # Avoid division by zero
        
        # Calculate density (words per sentence)
        density = word_count / sentences
        
        if word_count < 28:
            print(f"⚠️ VOICEOVER VERY SHORT: {word_count} words")
        elif word_count < 35:
            # Check density - high density short videos are OK
            if density <= 7:
                print(f"✅ VOICEOVER HIGH DENSITY: {word_count} words, {density:.1f} words/sentence - ACCEPTABLE")
            else:
                print(f"⚠️ VOICEOVER SHORT: {word_count} words, density {density:.1f} - consider adding content")
        elif word_count > 60:
            print(f"⚠️ VOICEOVER TOO LONG: {word_count} words (max 60 for 15s)")
        else:
            print(f"✅ Voiceover length OK: {word_count} words, {density:.1f} words/sentence")
    
    return script


# Backward compatible aliases
def generate_calm_script(region_name: Optional[str] = None) -> dict:
    """Backward compatible alias - now generates history content"""
    return generate_history_script(region_name=region_name)

def generate_fitness_script(region_name: Optional[str] = None) -> dict:
    """Backward compatible alias - now generates history content"""
    return generate_history_script(region_name=region_name)

def generate_absurd_script(region_name: Optional[str] = None) -> dict:
    """Backward compatible alias - now generates history content"""
    return generate_history_script(region_name=region_name)


def shorten_script(script: dict, region_name: str) -> dict:
    """
    Shorten the script if it's too long.
    Uses LLM to rewrite it with a strict character limit.
    """
    import json
    import re
    
    print(f"✂️ Script too long! ({len(script['voiceover_text'])} chars). Shortening...")
    
    bedrock = boto3.client(
        service_name='bedrock-runtime',
        region_name=region_name
    )
    
    model_id = os.environ.get('BEDROCK_MODEL_ID', 'us.anthropic.claude-sonnet-4-5-20250929-v1:0')
    
    # Construct the shortening prompt
    shortening_prompt = f"""
    The following YouTube Shorts script is too long.
    SHORTEN it to under 400 characters max.
    
    ORIGINAL SCRIPT:
    {json.dumps(script, indent=2)}
    
    RULES:
    1. Keep the same meaning and punchline.
    2. Make it punchier and faster.
    3. Remove any fluff or introductory phrases.
    4. Do NOT add "Here is the shortened version" - just return the JSON.
    5. STRICTLY output valid JSON matching the original structure.
    """
    
    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 800,
        "temperature": 0.5,
        "messages": [
            {
                "role": "user",
                "content": shortening_prompt
            }
        ]
    }
    
    try:
        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json"
        )
        
        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']
        
        # Extract JSON
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            new_script = json.loads(json_match.group())
            print(f"✅ Script shortened to {len(new_script.get('voiceover_text', ''))} chars")
            return new_script
        else:
            print("⚠️ Could not parse shortened JSON, keeping original")
            return script
            
    except Exception as e:
        print(f"⚠️ Shortening failed: {e}")
        return script

