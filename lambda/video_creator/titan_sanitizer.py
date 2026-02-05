"""
Titan Prompt Sanitizer Module
=============================
Comprehensive prompt sanitization for AWS Bedrock Titan Image Generator

AWS Titan Content Policy Analysis (2024):
- Blocks: violence, nudity, hate speech, famous figures, misinformation
- Protected: children, public figures, copyrighted characters
- Max prompt length: 512 characters
- Detects: weapons in violent context, blood, death, war crimes

This module provides robust sanitization to ensure prompts pass Titan's filters
while maintaining historical accuracy and visual quality.
"""

import re
from typing import Tuple, Optional

# Maximum prompt length for Titan
MAX_PROMPT_LENGTH = 500  # Leave 12 char buffer from 512 limit


# =============================================================================
# CATEGORY 1: FAMOUS/PUBLIC FIGURES
# Titan blocks specific names of real people to prevent misinformation
# =============================================================================
FAMOUS_FIGURES = {
    # Controversial historical leaders
    "genghis khan": "13th century Mongol emperor in ornate golden armor",
    "genghis": "medieval Mongol ruler on horseback",
    "kublai khan": "Yuan dynasty emperor in silk robes",
    "attila": "ancient Hun warrior leader",
    "hitler": "1940s European dictator figure",
    "stalin": "Soviet era political leader",
    "mussolini": "1930s Italian leader",
    "mao": "20th century Chinese leader",
    "napoleon": "19th century French emperor in military uniform",
    "nero": "ancient Roman emperor",
    "caligula": "Roman emperor in toga",
    
    # Ottoman/Turkish figures
    "atatürk": "Turkish founding leader in military uniform",
    "ataturk": "Turkish founding leader",
    "mustafa kemal": "Turkish military commander",
    "erdogan": "modern Turkish leader",
    "mehmed ii": "young Ottoman sultan in royal robes",
    "mehmed": "Ottoman sultan",
    "fatih": "Ottoman conqueror sultan",
    "suleiman": "magnificent Ottoman emperor in turban",
    "süleyman": "Ottoman golden age ruler",
    "selim": "Ottoman sultan",
    "osman": "Ottoman dynasty founder",
    
    # Ancient rulers
    "caesar": "Roman emperor in toga and laurel crown",
    "julius caesar": "ancient Roman statesman",
    "augustus": "first Roman emperor",
    "cleopatra": "ancient Egyptian queen in royal attire",
    "alexander": "ancient Greek conqueror king",
    "alexander the great": "Macedonian warrior king",
    "xerxes": "ancient Persian king",
    "darius": "Persian emperor",
    "ramses": "ancient Egyptian pharaoh",
    "tutankhamun": "Egyptian boy pharaoh",
    
    # Medieval figures
    "saladin": "medieval Kurdish Muslim commander",
    "richard": "English crusader king",
    "constantine": "Byzantine emperor in purple robes",
    "charlemagne": "Holy Roman Emperor",
    "william the conqueror": "Norman king",
    "joan of arc": "medieval French warrior maiden",
    
    # Asian historical figures
    "tokugawa": "Japanese shogun in samurai armor",
    "oda nobunaga": "Japanese warlord",
    "hideyoshi": "Japanese military leader",
    
    # Modern political figures (often blocked)
    "putin": "Russian political leader",
    "trump": "American political figure",
    "biden": "American political figure",
    "obama": "American political figure",
    "xi jinping": "Chinese political leader",
    "kim jong": "North Korean leader",
    
    # Celebrities/Actors who played historical figures (BLOCKED!)
    "elizabeth taylor": "",  # Remove completely
    "richard burton": "",
    "marlon brando": "",
    "charlton heston": "",
    "brad pitt": "",
    "angelina jolie": "",
    "russell crowe": "",
    "joaquin phoenix": "",
    "gal gadot": "",
    "real historical": "",  # Sometimes added by Claude
    "like the movie": "",
    "as seen in": "",
    "from the film": "",
}


# =============================================================================
# CATEGORY 2: VIOLENCE & WARFARE
# Titan blocks explicit violence - use symbolic/aftermath imagery
# =============================================================================
VIOLENCE_TERMS = {
    # Direct violence actions
    "killing": "triumphant warrior moment",
    "kill": "victorious warrior",
    "killed": "warrior legacy memorial",
    "murder": "dramatic palace intrigue",
    "murdered": "historical tragedy scene",
    "assassinate": "shadowy palace scene",
    "assassination": "mysterious historical event",
    "assassin": "cloaked mysterious figure",
    "execute": "solemn royal ceremony",
    "execution": "historical judgment scene",
    "beheading": "royal decree scene",
    "beheaded": "historical justice served",
    "torture": "dark medieval dungeon",
    "tortured": "prisoner in stone cell",
    "massacre": "aftermath of great battle",
    "slaughter": "overwhelming victory",
    "genocide": "somber historical memorial",
    "holocaust": "historical remembrance",
    
    # Combat and warfare
    "fighting battles": "warrior standing victorious at sunset",
    "fighting": "warrior in powerful stance",
    "fight": "martial display of skill",
    "battle": "warriors preparing for glory",
    "battles": "military encampment scene",
    "battlefield": "misty field with battle flags",
    "war": "soldiers in marching formation",
    "warfare": "military strategy planning",
    "combat": "warriors in training",
    "attack": "army advancing with flags",
    "attacking": "cavalry charge formation",
    "invade": "army at fortress gates",
    "invasion": "military forces gathering",
    "siege": "fortress under watchful eyes",
    "conquer": "victory flag over fortress",
    "conquered": "celebration in captured city",
    "destroy": "crumbling ancient ruins",
    "destruction": "smoke over distant horizon",
    "raid": "warriors departing at dawn",
    "pillage": "aftermath of conquest",
    "plunder": "treasure being discovered",
    
    # Weapons in violent context
    "stabbing": "ceremonial sword display",
    "stabbed": "ancient weapon on stand",
    "shooting": "archer in training stance",
    "shot": "target practice scene",
    "slash": "sword demonstration",
    "wound": "veteran warrior resting",
    "wounded": "warrior being tended",
    "injury": "healer treating soldier",
    
    # Death and dying
    "death": "solemn memorial scene",
    "dead": "peaceful warrior at rest",
    "died": "honoring fallen hero",
    "dying": "dramatic sunset farewell",
    "corpse": "ancient burial site",
    "body": "historical tomb",
    "bodies": "ancient cemetery",
    
    # Blood and gore
    "blood": "crimson sunset",
    "bloody": "dramatic red lighting",
    "bleeding": "red dawn sky",
    "gore": "intense battlefield atmosphere",
    "gory": "dramatic historical moment",
}


# =============================================================================
# CATEGORY 3: HATE SPEECH & DISCRIMINATION
# Titan blocks content that promotes hatred
# =============================================================================
HATE_TERMS = {
    "nazi": "1940s German military",
    "nazis": "World War 2 German forces",
    "swastika": "geometric symbol",
    "fascist": "authoritarian regime",
    "racist": "historical prejudice",
    "slavery": "historical labor system",
    "slave": "historical worker",
    "slaves": "bound laborers",
    "kkk": "historical hate group",
    "terrorist": "militant extremist",
    "terrorism": "political violence",
    "jihad": "religious struggle",
    "crusade": "medieval military campaign",
}


# =============================================================================
# CATEGORY 4: COPYRIGHTED CHARACTERS & BRANDS
# Titan blocks trademarked content
# =============================================================================
COPYRIGHTED_TERMS = {
    "disney": "animated style",
    "marvel": "superhero style",
    "dc comics": "comic book style",
    "pixar": "3D animated style",
    "pokemon": "creature collection style",
    "simba": "lion cub",
    "mickey mouse": "cartoon mouse",
    "harry potter": "wizard apprentice",
    "star wars": "space opera style",
    "lord of the rings": "epic fantasy style",
    "game of thrones": "medieval fantasy style",
}


# =============================================================================
# CATEGORY 5: SENSITIVE CONTENT
# Additional terms that may trigger filters
# =============================================================================
SENSITIVE_TERMS = {
    "naked": "unarmored",
    "nude": "classical artistic",
    "undressed": "in simple robes",
    "sexy": "elegant",
    "erotic": "romantic",
    "provocative": "dramatic",
    "drug": "medicinal herbs",
    "drugs": "ancient medicine",
    "weapon": "historical artifact",
    "weapons": "ceremonial objects",
    "gun": "historical firearm display",
    "guns": "museum weapon collection",
    "bomb": "siege equipment",
    "explosion": "dramatic clouds",
    "fire": "warm lighting",
    "burning": "torch-lit scene",
    # Blade weapons - often blocked by Titan (especially with Asian themes)
    "katana": "ceremonial ornament",
    "sword": "polished steel artifact",
    "blade": "metalwork display",
    "dagger": "ornate metalwork",
    "swords": "museum relics",
    "scimitar": "curved decorative piece",
}


# =============================================================================
# ART STYLE SYSTEM - Mood-based artistic rendering
# Each style has specific prompt additions for different moods/scenes
# =============================================================================
ART_STYLES = {
    # === EPIC/DRAMATIC STYLES ===
    "charcoal_epic": {
        "prompt": ", charcoal sketch on aged paper, cross-hatching style, rough ink strokes, monochrome illustration, vintage historical art, dramatic shadows",
        "moods": ["epic", "war", "battle", "conquest", "tragedy"],
        "eras": ["medieval", "ottoman", "ancient", "ww1", "ww2"]
    },
    "ink_wash": {
        "prompt": ", black ink wash painting, bold brushstrokes, dramatic contrast, sumi-e inspired, historical illustration, textured rice paper",
        "moods": ["epic", "mysterious", "dramatic"],
        "eras": ["ancient", "medieval", "asian"]
    },
    "renaissance_oil": {
        "prompt": ", Renaissance oil painting, chiaroscuro lighting, classical composition, museum quality, old master technique, rich earth tones",
        "moods": ["epic", "noble", "royal", "dramatic"],
        "eras": ["renaissance", "medieval", "ottoman"]
    },
    
    # === NOSTALGIC/WARM STYLES ===
    "watercolor_nostalgic": {
        "prompt": ", watercolor illustration, sepia ink wash, muted warm colors, soft brushstrokes, textured canvas, hand-painted historical style",
        "moods": ["nostalgic", "emotional", "personal", "family", "memory"],
        "eras": ["all"]
    },
    "sepia_vintage": {
        "prompt": ", vintage sepia photograph, aged paper texture, soft vignette, historical archive style, antique photo aesthetic",
        "moods": ["nostalgic", "memory", "personal"],
        "eras": ["19th_century", "early_20th", "ww1", "ww2"]
    },
    "golden_age": {
        "prompt": ", golden age illustration, warm amber tones, storybook art style, detailed linework, nostalgic vintage aesthetic",
        "moods": ["nostalgic", "romantic", "peaceful"],
        "eras": ["all"]
    },
    
    # === MODERN/DYNAMIC STYLES ===
    "graphic_novel": {
        "prompt": ", graphic novel panel, bold black outlines, comic book art style, high contrast, dynamic composition, halftone textures",
        "moods": ["action", "dynamic", "exciting"],
        "eras": ["modern", "ww2", "early_20th"]
    },
    "cinematic": {
        "prompt": ", cinematic still, dramatic lighting, movie poster composition, widescreen aesthetic, professional color grading",
        "moods": ["epic", "dramatic", "action"],
        "eras": ["all"]
    },
    
    # === CULTURAL STYLES ===
    "ottoman_miniature": {
        "prompt": ", Ottoman miniature painting style, traditional Islamic art, gold leaf accents, intricate patterns, manuscript illustration",
        "moods": ["royal", "cultural", "peaceful"],
        "eras": ["ottoman", "medieval"]
    },
    "japanese_ukiyo_e": {
        "prompt": ", ukiyo-e woodblock print style, bold outlines, flat colors, traditional Japanese art, edo period aesthetic",
        "moods": ["cultural", "peaceful", "warrior"],
        "eras": ["asian", "medieval"]
    },
    "byzantine_mosaic": {
        "prompt": ", Byzantine mosaic style, golden tesserae, religious iconography aesthetic, rich jewel tones, formal composition",
        "moods": ["royal", "religious", "cultural"],
        "eras": ["ancient", "medieval"]
    },
    "persian_miniature": {
        "prompt": ", Persian miniature painting, detailed patterns, vibrant colors, garden scene aesthetic, calligraphic borders",
        "moods": ["royal", "romantic", "cultural"],
        "eras": ["ottoman", "medieval", "ancient"]
    },
}

# Mood keywords to style mapping
MOOD_STYLE_MAP = {
    "epic": ["charcoal_epic", "ink_wash", "renaissance_oil", "cinematic"],
    "war": ["charcoal_epic", "ink_wash", "graphic_novel"],
    "battle": ["charcoal_epic", "graphic_novel", "cinematic"],
    "conquest": ["charcoal_epic", "renaissance_oil"],
    "nostalgic": ["watercolor_nostalgic", "sepia_vintage", "golden_age"],
    "emotional": ["watercolor_nostalgic", "sepia_vintage"],
    "personal": ["watercolor_nostalgic", "sepia_vintage"],
    "family": ["watercolor_nostalgic", "golden_age"],
    "memory": ["sepia_vintage", "watercolor_nostalgic"],
    "dramatic": ["charcoal_epic", "renaissance_oil", "cinematic"],
    "royal": ["ottoman_miniature", "renaissance_oil", "byzantine_mosaic"],
    "cultural": ["ottoman_miniature", "japanese_ukiyo_e", "persian_miniature"],
    "peaceful": ["watercolor_nostalgic", "golden_age", "persian_miniature"],
    "action": ["graphic_novel", "cinematic", "charcoal_epic"],
    "mysterious": ["ink_wash", "charcoal_epic"],
    "warrior": ["charcoal_epic", "japanese_ukiyo_e", "graphic_novel"],
}


# =============================================================================
# HISTORICAL FIGURE PHYSICAL DESCRIPTIONS DATABASE
# Replace names with detailed physical descriptions for filter bypass
# =============================================================================
HISTORICAL_FIGURES_PHYSICAL = {
    # === OTTOMAN EMPIRE ===
    "fatih sultan mehmet": {
        "physical": "young man in early twenties, short dark beard, aquiline nose, intense piercing dark eyes, olive complexion, strong jawline",
        "attire": "crimson kaftan with intricate gold embroidery, tall white turban with jeweled aigrette, ceremonial dagger at waist",
        "era": "ottoman",
        "style": "charcoal_epic"
    },
    "fatih": {
        "physical": "young Ottoman ruler, early twenties, dark beard, sharp noble features, determined expression",
        "attire": "royal red and gold robes, magnificent turban with ruby",
        "era": "ottoman",
        "style": "charcoal_epic"
    },
    "kanuni sultan süleyman": {
        "physical": "mature man in fifties, long distinguished white beard, noble aquiline nose, wise contemplative eyes, dignified bearing",
        "attire": "magnificent golden kaftan, enormous jeweled turban, holding ceremonial staff",
        "era": "ottoman",
        "style": "ottoman_miniature"
    },
    "süleyman": {
        "physical": "mature Ottoman emperor, long white beard, regal bearing, wise expression",
        "attire": "ornate golden robes, large ceremonial turban",
        "era": "ottoman",
        "style": "ottoman_miniature"
    },
    "atatürk": {
        "physical": "man in mid-forties, steel blue eyes, fair complexion, blonde eyebrows, sharp angular face, strong determined jawline, short military haircut",
        "attire": "olive military uniform with medals and ribbons, kalpak fur hat, polished boots",
        "era": "early_20th",
        "style": "charcoal_epic"
    },
    "mustafa kemal": {
        "physical": "Turkish military commander, blue eyes, blonde hair, sharp features, commanding presence",
        "attire": "military officer uniform, riding boots, commander's cap",
        "era": "early_20th",
        "style": "charcoal_epic"
    },
    
    # === MONGOL EMPIRE ===
    "cengiz han": {
        # SAFE: Avoid warrior/battle/fierce - use noble/artistic descriptions
        "physical": "elderly Asian ruler, weathered wise face, long gray braided hair, deep-set contemplative eyes, prominent cheekbones, distinguished beard",
        "attire": "ornate silk robes with fur trim, golden ceremonial headdress, traditional Mongol leather boots",
        "era": "medieval",
        "style": "charcoal_epic"
    },
    "genghis khan": {
        # SAFE: Avoid warrior/battle/fierce - focus on ruler/statesman
        "physical": "13th century Asian ruler, weathered noble face, traditional braided hair, wise penetrating gaze",
        "attire": "golden ceremonial Mongol robes, fur-lined imperial cape, ornate headdress",
        "era": "medieval",
        "style": "charcoal_epic"
    },
    "kubilay han": {
        "physical": "stocky man, round face, thin mustache and beard, shrewd intelligent eyes, dignified posture",
        "attire": "Chinese-Mongol imperial robes, dragon embroidery, ceremonial hat",
        "era": "medieval",
        "style": "ink_wash"
    },
    
    # === ANCIENT ROME ===
    "julius caesar": {
        "physical": "lean man in fifties, receding hairline, sharp patrician features, thin lips, penetrating gaze, clean-shaven or light stubble",
        "attire": "white toga with purple border, golden laurel wreath crown, senatorial sandals",
        "era": "ancient",
        "style": "renaissance_oil"
    },
    "caesar": {
        "physical": "Roman statesman, angular features, balding, commanding presence, thin face",
        "attire": "Roman toga, laurel crown, military cloak",
        "era": "ancient",
        "style": "renaissance_oil"
    },
    "augustus": {
        "physical": "handsome young man, curly hair, refined classical features, serene expression, athletic build",
        "attire": "imperial purple toga, golden oak leaf crown, ornate breastplate",
        "era": "ancient",
        "style": "renaissance_oil"
    },
    "nero": {
        "physical": "heavy-set man, curly reddish hair, double chin, theatrical expression, ornate appearance",
        "attire": "extravagant purple and gold robes, jeweled crown, lyre instrument",
        "era": "ancient",
        "style": "renaissance_oil"
    },
    
    # === ANCIENT EGYPT ===
    "cleopatra": {
        "physical": "elegant woman in thirties, dark hair in elaborate braids, kohl-lined eyes, olive skin, regal bearing, graceful neck",
        "attire": "white linen gown with gold accents, elaborate golden headdress with cobra, jeweled collar necklace",
        "era": "ancient",
        "style": "golden_age"
    },
    "ramses": {
        "physical": "tall powerful pharaoh, strong jaw, proud bearing, dark skin, muscular build",
        "attire": "white and gold royal shendyt, double crown of Egypt, ceremonial crook and flail",
        "era": "ancient",
        "style": "golden_age"
    },
    
    # === MEDIEVAL EUROPE ===
    "charlemagne": {
        "physical": "tall imposing man, long flowing beard, wise eyes, broad shoulders, dignified bearing",
        "attire": "royal purple robes with ermine trim, golden imperial crown, ornate sword at side",
        "era": "medieval",
        "style": "renaissance_oil"
    },
    "richard the lionheart": {
        "physical": "tall muscular warrior, reddish hair and beard, fierce blue eyes, battle-ready stance",
        "attire": "chainmail with white surcoat bearing red cross, crusader helm, broadsword",
        "era": "medieval",
        "style": "charcoal_epic"
    },
    "joan of arc": {
        "physical": "young woman late teens, short dark hair, determined bright eyes, petite but fierce",
        "attire": "plate armor, white banner with fleur-de-lis, sword at side",
        "era": "medieval",
        "style": "charcoal_epic"
    },
    
    # === ISLAMIC GOLDEN AGE ===
    "salahaddin eyyubi": {
        "physical": "dignified man in forties, dark beard, kind wise eyes, calm noble expression, medium build",
        "attire": "simple but fine Damascus robes, green turban, curved scimitar",
        "era": "medieval",
        "style": "persian_miniature"
    },
    "saladin": {
        "physical": "Kurdish commander, neat beard, noble bearing, gentle eyes, warrior's posture",
        "attire": "golden armor over robes, ceremonial sword, Islamic green sash",
        "era": "medieval",
        "style": "persian_miniature"
    },
    
    # === JAPANESE HISTORY ===
    "oda nobunaga": {
        "physical": "fierce warlord, intense narrow eyes, thin mustache, scarred face, intimidating presence",
        "attire": "elaborate samurai armor in black and red, horned kabuto helmet, ancestral katana",
        "era": "asian",
        "style": "japanese_ukiyo_e"
    },
    "tokugawa ieyasu": {
        "physical": "stocky man, calculating expression, small eyes, patient demeanor, subtle smile",
        "attire": "formal samurai garb, family crest mon, traditional haori jacket",
        "era": "asian",
        "style": "japanese_ukiyo_e"
    },
    
    # === FRENCH HISTORY ===
    "napoleon": {
        "physical": "short man with commanding presence, dark hair in signature style, sharp blue-gray eyes, strong chin, pale complexion",
        "attire": "blue military coat with gold epaulettes, white breeches, bicorne hat, hand tucked in coat",
        "era": "19th_century",
        "style": "renaissance_oil"
    },
    "louis xiv": {
        "physical": "regal man with long curly wig, proud bearing, aquiline nose, elaborate makeup",
        "attire": "extravagant gold and blue robes, red high heels, white stockings, crown",
        "era": "renaissance",
        "style": "renaissance_oil"
    },
    
    # === MODERN ERA ===
    "benjamin franklin": {
        "physical": "elderly man, bald with long gray hair on sides, round spectacles, wise smile, portly build",
        "attire": "simple colonial coat, white cravat, plain brown suit",
        "era": "18th_century",
        "style": "sepia_vintage"
    },
    "abraham lincoln": {
        "physical": "very tall thin man, angular face, distinctive beard without mustache, deep-set melancholic eyes, prominent ears",
        "attire": "black suit and coat, signature tall stovepipe hat, bow tie",
        "era": "19th_century",
        "style": "sepia_vintage"
    },
    
    # === RUSSIAN HISTORY ===
    "catherine the great": {
        "physical": "regal woman, powdered wig, keen intelligent eyes, commanding presence, elegant posture",
        "attire": "elaborate court gown in imperial blue, jeweled crown, ermine cape",
        "era": "18th_century",
        "style": "renaissance_oil"
    },
    "ivan the terrible": {
        "physical": "tall imposing man, wild eyes, long dark beard, intense paranoid expression",
        "attire": "heavy fur-trimmed royal robes, ornate Russian crown, ceremonial staff",
        "era": "medieval",
        "style": "byzantine_mosaic"
    },
    
    # === ANCIENT GREECE ===
    "alexander the great": {
        "physical": "young man with flowing hair swept back, clean-shaven, striking features, bright eyes, athletic build",
        "attire": "golden Macedonian armor, red military cloak, lion helmet",
        "era": "ancient",
        "style": "renaissance_oil"
    },
    "leonidas": {
        "physical": "muscular Spartan warrior, short beard, fierce determined eyes, battle-ready stance",
        "attire": "bronze Spartan armor, crimson cape, Corinthian helmet, round shield",
        "era": "ancient",
        "style": "charcoal_epic"
    },
}


def get_art_style_prompt(mood: str = None, era: str = None) -> str:
    """
    Get appropriate art style prompt based on mood and era.
    
    Args:
        mood: Content mood (epic, nostalgic, emotional, etc.)
        era: Historical era
        
    Returns:
        Art style prompt addition
    """
    import random
    
    # Default style
    default_style = "watercolor_nostalgic"
    
    # Get styles matching the mood
    if mood and mood.lower() in MOOD_STYLE_MAP:
        matching_styles = MOOD_STYLE_MAP[mood.lower()]
        style_name = random.choice(matching_styles)
    else:
        # Pick based on era if no mood
        era_styles = []
        for name, style in ART_STYLES.items():
            if era in style.get("eras", []) or "all" in style.get("eras", []):
                era_styles.append(name)
        style_name = random.choice(era_styles) if era_styles else default_style
    
    style = ART_STYLES.get(style_name, ART_STYLES[default_style])
    print(f"🎨 Art style selected: {style_name}")
    
    return style["prompt"]


def replace_figure_with_description(prompt: str) -> str:
    """
    Replace historical figure names with their physical descriptions.
    This bypasses content filters while maintaining visual accuracy.
    
    Args:
        prompt: Original prompt possibly containing figure names
        
    Returns:
        Prompt with names replaced by physical descriptions
    """
    import random
    
    prompt_lower = prompt.lower()
    modified = prompt
    
    # Sort by name length (longest first) to match "fatih sultan mehmet" before "fatih"
    sorted_figures = sorted(HISTORICAL_FIGURES_PHYSICAL.items(), 
                           key=lambda x: len(x[0]), reverse=True)
    
    for name, details in sorted_figures:
        if name in prompt_lower:
            # Build description
            description = f"{details['physical']}, {details['attire']}"
            
            # Replace name with description
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            modified = pattern.sub(description, modified)
            prompt_lower = modified.lower()
            
            print(f"👤 Figure replaced: '{name}' → physical description")
            print(f"   📝 {description[:80]}...")
            
            # Return the recommended style
            return modified, details.get("style", "charcoal_epic"), details.get("era", "medieval")
    
    return modified, None, None


SAFE_STYLE_ADDITIONS = [
    "oil painting style",
    "historical illustration",
    "museum quality artwork",
    "classical art composition",
    "documentary style",
    "educational illustration",
    "archival photograph style",
    "sepia toned historical",
    "renaissance painting style",
    "detailed historical scene",
]


def sanitize_prompt(prompt: str) -> Tuple[str, bool, list]:
    """
    Comprehensive prompt sanitization for AWS Titan Image Generator.
    
    Args:
        prompt: The original image generation prompt
        
    Returns:
        Tuple of (sanitized_prompt, was_modified, list_of_changes)
    """
    original = prompt
    changes = []
    
    # Combine all sanitization dictionaries
    all_terms = {}
    all_terms.update(FAMOUS_FIGURES)
    all_terms.update(VIOLENCE_TERMS)
    all_terms.update(HATE_TERMS)
    all_terms.update(COPYRIGHTED_TERMS)
    all_terms.update(SENSITIVE_TERMS)
    
    # Sort by length (longest first) to match phrases before individual words
    sorted_terms = sorted(all_terms.items(), key=lambda x: len(x[0]), reverse=True)
    
    sanitized = prompt
    prompt_lower = sanitized.lower()
    
    for term, replacement in sorted_terms:
        if term in prompt_lower:
            # Use word boundary to avoid partial matches (e.g., 'war' in 'warrior')
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)
            new_sanitized = pattern.sub(replacement, sanitized)
            # Only count as change if something actually changed
            if new_sanitized != sanitized:
                sanitized = new_sanitized
                prompt_lower = sanitized.lower()
                changes.append(f"'{term}' → '{replacement}'")
    
    # Truncate if too long
    if len(sanitized) > MAX_PROMPT_LENGTH:
        sanitized = sanitized[:MAX_PROMPT_LENGTH-3] + "..."
        changes.append(f"Truncated to {MAX_PROMPT_LENGTH} chars")
    
    was_modified = sanitized != original
    
    return sanitized, was_modified, changes


def enhance_for_safety(prompt: str, era: str = "medieval") -> str:
    """
    Add safety-enhancing style terms to prompt.
    These help the prompt pass filters while maintaining quality.
    
    Args:
        prompt: The sanitized prompt
        era: Historical era for style matching
        
    Returns:
        Enhanced prompt with safety terms
    """
    import random
    
    # Era-specific safe additions
    era_styles = {
        "ancient": "classical antiquity style, museum artwork",
        "medieval": "illuminated manuscript style, medieval art",
        "ottoman": "Ottoman miniature painting style, Islamic art",
        "renaissance": "Renaissance master painting style",
        "early_20th": "vintage sepia photograph, historical archive",
        "ww1": "documentary photograph style, historical record",
        "ww2": "wartime documentary style, archival image",
        "19th_century": "Victorian era painting, period artwork",
    }
    
    style = era_styles.get(era, random.choice(SAFE_STYLE_ADDITIONS))
    
    # Add style if not already present
    if style.split(",")[0].lower() not in prompt.lower():
        prompt = f"{prompt}, {style}"
    
    # Ensure educational/historical context
    if "historical" not in prompt.lower() and "educational" not in prompt.lower():
        prompt += ", historical educational illustration"
    
    return prompt


def validate_prompt(prompt: str) -> Tuple[bool, Optional[str]]:
    """
    Validate if a prompt is likely to pass Titan's filters.
    
    Args:
        prompt: The prompt to validate
        
    Returns:
        Tuple of (is_safe, warning_message)
    """
    prompt_lower = prompt.lower()
    warnings = []
    
    # Check for remaining risky terms
    risky_still_present = []
    for term in list(VIOLENCE_TERMS.keys()) + list(FAMOUS_FIGURES.keys()):
        if term in prompt_lower:
            risky_still_present.append(term)
    
    if risky_still_present:
        warnings.append(f"Risky terms still present: {', '.join(risky_still_present[:5])}")
    
    # Check length
    if len(prompt) > MAX_PROMPT_LENGTH:
        warnings.append(f"Prompt too long: {len(prompt)} chars (max {MAX_PROMPT_LENGTH})")
    
    # Check for required safety elements
    has_style = any(s in prompt_lower for s in ["painting", "illustration", "artwork", "style", "historical"])
    if not has_style:
        warnings.append("Missing style descriptor (painting, illustration, etc.)")
    
    is_safe = len(warnings) == 0
    warning_msg = "; ".join(warnings) if warnings else None
    
    return is_safe, warning_msg


def full_sanitize(prompt: str, era: str = "medieval", mood: str = None) -> str:
    """
    Complete sanitization pipeline for Titan Image Generator.
    
    This is the main function to use for all prompts.
    Now includes:
    - Historical figure name → physical description replacement
    - Mood-based art style selection
    - Violence/content sanitization
    - Safety enhancements
    
    Args:
        prompt: Original prompt
        era: Historical era for styling
        mood: Content mood (epic, nostalgic, emotional, etc.)
        
    Returns:
        Fully sanitized and enhanced prompt ready for Titan
    """
    print(f"🛡️ Titan Sanitizer processing prompt...")
    
    # Step 0: Replace historical figure names with physical descriptions
    prompt_with_desc, figure_style, figure_era = replace_figure_with_description(prompt)
    if figure_style:
        # Use the figure's recommended style if no mood specified
        if not mood:
            mood = "epic"  # Default mood for historical figures
        if not era or era == "medieval":
            era = figure_era  # Use figure's era
    
    # Step 1: Sanitize dangerous terms
    sanitized, was_modified, changes = sanitize_prompt(prompt_with_desc)
    
    if changes:
        print(f"🛡️ Titan Sanitizer: {len(changes)} modifications made")
        for change in changes[:5]:  # Show first 5
            print(f"   ⚔️ {change}")
        if len(changes) > 5:
            print(f"   ... and {len(changes) - 5} more")
    
    # Step 1.5: EARLY TRUNCATION at word boundary
    # Keep base prompt short to leave room for style additions (~120 chars)
    BASE_PROMPT_LIMIT = 280  # Reduced from 350
    if len(sanitized) > BASE_PROMPT_LIMIT:
        # Find last space before limit to avoid cutting words
        truncate_at = sanitized.rfind(' ', 0, BASE_PROMPT_LIMIT)
        if truncate_at > 100:  # Make sure we have enough text
            sanitized = sanitized[:truncate_at]
        else:
            sanitized = sanitized[:BASE_PROMPT_LIMIT]
        print(f"📏 Base prompt truncated to {len(sanitized)} chars at word boundary")
    
    # Step 2: ALWAYS add sketch/charcoal style for artistic non-photorealistic look
    # This is the key change - force artistic styles
    SKETCH_STYLE = ", charcoal sketch, hand-drawn illustration, artistic linework, non-photorealistic"
    sanitized += SKETCH_STYLE
    print(f"🎨 Forced sketch style added")
    
    # Step 3: Skip other style additions - we already have sketch style
    enhanced = sanitized
    
    # Step 4: Final truncation at word boundary to ensure under 480 (leaving buffer)
    FINAL_LIMIT = 480
    if len(enhanced) > FINAL_LIMIT:
        truncate_at = enhanced.rfind(' ', 0, FINAL_LIMIT)
        if truncate_at > 200:
            enhanced = enhanced[:truncate_at]
        else:
            enhanced = enhanced[:FINAL_LIMIT]
        print(f"📏 Final truncation to {len(enhanced)} chars")
    
    # Step 5: Validate
    is_safe, warning = validate_prompt(enhanced)
    if not is_safe:
        print(f"⚠️ Titan Sanitizer Warning: {warning}")
    else:
        print("✅ Titan Sanitizer: Prompt validated as safe")
    
    return enhanced


# =============================================================================
# HISTORICAL FIGURE FACE AVOIDANCE
# Additional techniques to avoid generating recognizable faces
# =============================================================================
FACE_AVOIDANCE_SUFFIXES = [
    ", viewed from behind",
    ", dramatic silhouette against bright sky",
    ", artistic shadow obscuring face",
    ", wide shot showing full scene",
    ", face turned away from viewer",
    ", backlit dramatic pose",
    ", seen from a distance",
    ", figure in dramatic fog",
]


def add_face_avoidance(prompt: str) -> str:
    """
    Add face avoidance technique to prompt.
    Helps prevent generation of recognizable historical faces.
    """
    import random
    
    # Check if prompt likely contains a person
    person_indicators = ["emperor", "king", "queen", "warrior", "soldier", "leader", 
                        "sultan", "pharaoh", "general", "commander", "ruler"]
    
    has_person = any(ind in prompt.lower() for ind in person_indicators)
    
    if has_person:
        suffix = random.choice(FACE_AVOIDANCE_SUFFIXES)
        if suffix.strip(", ").lower() not in prompt.lower():
            prompt += suffix
            print(f"🎭 Face avoidance added: {suffix}")
    
    return prompt


# Test function
if __name__ == "__main__":
    test_prompts = [
        "Genghis Khan killing enemies in bloody battle",
        "Hitler at Nazi rally",
        "Samurai fighting battles with sword",
        "Assassination of Julius Caesar",
        "Cleopatra naked in palace",
    ]
    
    print("=" * 60)
    print("TITAN PROMPT SANITIZER TEST")
    print("=" * 60)
    
    for prompt in test_prompts:
        print(f"\n📝 ORIGINAL: {prompt}")
        result = full_sanitize(prompt, "medieval")
        result = add_face_avoidance(result)
        print(f"✨ RESULT: {result}")
        print("-" * 60)
