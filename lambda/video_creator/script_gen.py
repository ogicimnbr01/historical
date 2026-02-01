"""
History Shorts Script Generator using AWS Bedrock (Claude)
Generates engaging historical content for YouTube Shorts
Global audience, English language, fascinating facts about leaders, battles, and civilizations
"""

import json
import re
import random
import boto3

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
- Make history FASCINATING, not boring
- Focus on human moments: what leaders ate, their quirks, unexpected facts
- Create CONTRAST: "He conquered an empire, but couldn't resist..."
- Every video should teach something surprising

⚠️ THE 5 UNBREAKABLE RULES:
1. NEVER be dry or academic ("In 1453, the Ottoman forces...")
2. NEVER use obvious facts everyone knows
3. ALWAYS start with a HOOK that creates curiosity
4. ALWAYS include specific, vivid details (names, numbers, foods, colors)
5. NEVER be longer than 15 seconds when read aloud

📝 EXACT SCRIPT STRUCTURE (Total 15 seconds, 4 segments):

1. HOOK (0-3s) - Create CONTRAST or CURIOSITY:
   ✅ "He conquered Constantinople, but he couldn't sleep without his cat"
   ✅ "The most powerful woman in history... was terrified of one thing"
   ✅ "They called him 'The Magnificent' - here's what he ate for breakfast"
   ❌ "Today we'll learn about Suleiman" (boring, no hook)
   ❌ "Did you know that..." (overused, weak)

2. CONTEXT (3-7s) - Set the historical stage:
   ✅ "Mehmed II, the young sultan who ended the Roman Empire..."
   ✅ "At the height of the Ottoman Empire, breakfast wasn't just a meal..."
   Brief but vivid. Place the viewer in that era.

3. FACT (7-12s) - The surprising revelation:
   ✅ "He personally drew the blueprints for his cannons"
   ✅ "His favorite dish was simple beans and rice - the same as his soldiers"
   This is the PAYOFF. Make it memorable and specific.

4. OUTRO (12-15s) - Leave them thinking:
   ✅ "Power changes people... but not always their taste"
   ✅ "Sometimes the greatest conquerors are the simplest men"
   ✅ "History remembers the crown, not the breakfast"
   Short, poetic, shareable.

🎨 VISUAL PROMPTS:
For each segment, generate an image_prompt that describes what should be shown.
- Use specific historical details
- Include era-appropriate styling (mention "black and white vintage" for 20th century)
- Always end with "9:16 vertical composition"
- Include the historical figure's name for AI recognition

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
        {"start": 12, "end": 15, "text": "The man who changed everything... never changed his taste.", "image_prompt": "Mustafa Kemal Atatürk portrait, thoughtful expression, 1930s black and white photograph, film grain, presidential, 9:16 vertical composition"}
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


def generate_history_script(topic: str = None, era: str = None, region_name: str = None) -> dict:
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
    
    # Call Claude via Bedrock
    response = bedrock.invoke_model(
        modelId="us.anthropic.claude-sonnet-4-20250514-v1:0",
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
    safe_title = re.sub(r'[-\s]+', '_', safe_title).strip('_')[:50]
    script['safe_title'] = safe_title
    
    # Add original topic for reference
    script['original_topic'] = selected_topic["topic"]
    
    print(f"📜 Generated history script: {script['title']}")
    print(f"   Era: {script['era']}, Mood: {script['mood']}")
    
    return script


# Backward compatible aliases
def generate_calm_script(region_name: str = None) -> dict:
    """Backward compatible alias - now generates history content"""
    return generate_history_script(region_name=region_name)

def generate_fitness_script(region_name: str = None) -> dict:
    """Backward compatible alias - now generates history content"""
    return generate_history_script(region_name=region_name)

def generate_absurd_script(region_name: str = None) -> dict:
    """Backward compatible alias - now generates history content"""
    return generate_history_script(region_name=region_name)


if __name__ == "__main__":
    # Test locally (requires AWS credentials)
    print("Testing History Script Generator...")
    
    # Test with specific topic
    script = generate_history_script("Atatürk's favorite foods")
    print(json.dumps(script, indent=2, ensure_ascii=False))
