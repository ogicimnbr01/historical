"""
Story-Music Matcher for YouTube Shorts
Analyzes script content to select the most appropriate music
Uses keyword analysis and emotional mapping
"""

from typing import Dict, List, Tuple
import re


# Keyword to music category mapping with weights
# Higher weight = stronger indicator
KEYWORD_MUSIC_MAP = {
    # WAR/BATTLE keywords → epic, war music
    "war": ("epic", 5),
    "battle": ("epic", 5),
    "fight": ("epic", 4),
    "army": ("epic", 4),
    "soldier": ("epic", 4),
    "military": ("epic", 4),
    "conquest": ("epic", 5),
    "invasion": ("epic", 5),
    "siege": ("epic", 4),
    "victory": ("epic", 4),
    "defeat": ("dramatic", 4),
    "warrior": ("epic", 4),
    "sword": ("epic", 3),
    "weapon": ("epic", 3),
    "cannon": ("epic", 4),
    "empire": ("epic", 4),
    "conquer": ("epic", 5),
    "crusade": ("epic", 5),
    
    # EMOTIONAL/SAD keywords → emotional, piano music
    "death": ("emotional", 5),
    "died": ("emotional", 5),
    "tragedy": ("emotional", 5),
    "tragic": ("emotional", 5),
    "lost": ("emotional", 3),
    "love": ("emotional", 4),
    "heart": ("emotional", 3),
    "tears": ("emotional", 4),
    "mourning": ("emotional", 5),
    "grief": ("emotional", 5),
    "farewell": ("emotional", 4),
    "sacrifice": ("emotional", 4),
    "betrayal": ("dramatic", 4),
    "lonely": ("emotional", 3),
    "broken": ("emotional", 3),
    
    # MYSTERY/DARK keywords → dramatic, mysterious music
    "secret": ("dramatic", 4),
    "mystery": ("dramatic", 5),
    "hidden": ("dramatic", 3),
    "dark": ("dramatic", 4),
    "shadow": ("dramatic", 4),
    "unknown": ("dramatic", 3),
    "conspiracy": ("dramatic", 5),
    "curse": ("dramatic", 5),
    "haunted": ("dramatic", 4),
    "legend": ("dramatic", 3),
    "myth": ("dramatic", 3),
    
    # TRIUMPH/GLORY keywords → epic, triumphant music
    "triumph": ("epic", 5),
    "glory": ("epic", 5),
    "hero": ("epic", 4),
    "legacy": ("epic", 3),
    "famous": ("documentary", 2),
    "greatest": ("epic", 4),
    "legendary": ("epic", 4),
    "powerful": ("epic", 3),
    "king": ("epic", 3),
    "emperor": ("epic", 4),
    "queen": ("epic", 3),
    "sultan": ("epic", 4),
    "throne": ("epic", 3),
    
    # DOCUMENTARY/NEUTRAL keywords → documentary, ambient music
    "history": ("documentary", 2),
    "discovered": ("documentary", 3),
    "invention": ("documentary", 4),
    "science": ("documentary", 4),
    "culture": ("documentary", 3),
    "tradition": ("documentary", 3),
    "ancient": ("documentary", 2),
    "civilization": ("documentary", 3),
    "society": ("documentary", 2),
    "technology": ("documentary", 3),
    
    # OTTOMAN/ORIENTAL keywords → oriental music
    "ottoman": ("oriental", 5),
    "sultan": ("oriental", 4),
    "istanbul": ("oriental", 4),
    "constantinople": ("oriental", 4),
    "mosque": ("oriental", 4),
    "harem": ("oriental", 4),
    "janissary": ("oriental", 5),
    "persian": ("oriental", 4),
    "arabian": ("oriental", 4),
    "islamic": ("oriental", 3),
    "muslim": ("oriental", 3),
    
    # MEDIEVAL keywords → medieval, celtic music
    "medieval": ("medieval", 4),
    "knight": ("medieval", 4),
    "castle": ("medieval", 3),
    "kingdom": ("medieval", 3),
    "crusader": ("medieval", 4),
    "feudal": ("medieval", 4),
    "viking": ("medieval", 4),
    "norse": ("medieval", 4),
}


def analyze_script_mood(title: str, voiceover_text: str, 
                       script_mood: str = None, era: str = None) -> Dict:
    """
    Analyze script content and return music recommendation
    
    Args:
        title: Video title
        voiceover_text: Full voiceover script
        script_mood: Mood from script generator (if available)
        era: Historical era (if available)
    
    Returns:
        Dict with recommended_category, confidence, and analysis
    """
    # Combine title and text for analysis
    full_text = f"{title} {voiceover_text}".lower()
    
    # Count keyword matches
    category_scores = {}
    matched_keywords = []
    
    for keyword, (category, weight) in KEYWORD_MUSIC_MAP.items():
        # Count occurrences
        count = len(re.findall(r'\b' + keyword + r'\b', full_text))
        if count > 0:
            if category not in category_scores:
                category_scores[category] = 0
            category_scores[category] += weight * count
            matched_keywords.append((keyword, category, count))
    
    # Get top category
    if category_scores:
        top_category = max(category_scores, key=category_scores.get)
        top_score = category_scores[top_category]
        total_score = sum(category_scores.values())
        confidence = min(0.95, top_score / max(total_score, 1) + 0.2)
    else:
        top_category = None
        confidence = 0.0
    
    # Factor in script_mood and era if no strong keyword match
    final_category = top_category
    
    if not final_category or confidence < 0.5:
        # Use mood/era as fallback
        if script_mood:
            mood_mapping = {
                "epic": "epic",
                "dramatic": "dramatic",
                "nostalgic": "emotional",
                "documentary": "documentary",
                "sad": "emotional",
                "war": "epic",
            }
            final_category = mood_mapping.get(script_mood, "documentary")
            confidence = max(confidence, 0.6)
        
        if era and not final_category:
            era_mapping = {
                "ottoman": "oriental",
                "medieval": "medieval",
                "ancient": "documentary",
                "ww1": "epic",
                "ww2": "epic",
            }
            final_category = era_mapping.get(era, "documentary")
            confidence = max(confidence, 0.5)
    
    # Default fallback
    if not final_category:
        final_category = "documentary"
        confidence = 0.4
    
    return {
        "recommended_category": final_category,
        "confidence": confidence,
        "matched_keywords": matched_keywords[:10],  # Top 10
        "all_scores": category_scores,
        "fallback_used": top_category is None
    }


def get_music_category_for_script(script: Dict) -> Tuple[str, float]:
    """
    Convenience function to get music category from script dict
    
    Args:
        script: Script dictionary with 'title', 'voiceover_text', 'mood', 'era'
    
    Returns:
        Tuple of (category_name, confidence)
    """
    title = script.get('title', '')
    voiceover = script.get('voiceover_text', '')
    mood = script.get('mood', None)
    era = script.get('era', None)
    
    analysis = analyze_script_mood(title, voiceover, mood, era)
    
    category = analysis['recommended_category']
    confidence = analysis['confidence']
    
    # Log the analysis
    print(f"🎵 Music analysis: {category} (confidence: {confidence:.0%})")
    
    if analysis['matched_keywords']:
        keywords = [f"{kw}({cat})" for kw, cat, _ in analysis['matched_keywords'][:5]]
        print(f"🎵 Matched keywords: {', '.join(keywords)}")
    
    return category, confidence


def suggest_music_for_story(title: str, voiceover_text: str) -> str:
    """
    Simple interface: Get music category suggestion
    Returns category name string
    """
    analysis = analyze_script_mood(title, voiceover_text)
    return analysis['recommended_category']


# Mapping from our categories to S3 file prefixes
CATEGORY_TO_FILE_PREFIX = {
    "epic": ["epic", "cinematic", "dramatic"],
    "emotional": ["emotional", "piano", "sad"],
    "dramatic": ["dramatic", "epic", "emotional"],
    "documentary": ["documentary", "ambient"],
    "oriental": ["oriental", "arabian", "epic"],
    "medieval": ["medieval", "celtic", "epic"],
}


def get_preferred_file_prefixes(category: str) -> List[str]:
    """Get list of file prefixes to look for in S3"""
    return CATEGORY_TO_FILE_PREFIX.get(category, ["documentary", "epic"])


if __name__ == "__main__":
    # Test cases
    test_cases = [
        {
            "title": "The Battle of Thermopylae",
            "voiceover": "300 spartans fought against the massive Persian army. This legendary battle..."
        },
        {
            "title": "The Tragic Love Story of Cleopatra",
            "voiceover": "Cleopatra's heart was broken when she heard of Antony's death..."
        },
        {
            "title": "The Mystery of the Pyramids",
            "voiceover": "Hidden secrets within the ancient pyramids remain unknown..."
        },
        {
            "title": "Sultan Mehmet's Conquest",
            "voiceover": "The young Ottoman sultan conquered Constantinople in 1453..."
        },
    ]
    
    for test in test_cases:
        print(f"\n📖 {test['title']}")
        analysis = analyze_script_mood(test['title'], test['voiceover'])
        print(f"   → Category: {analysis['recommended_category']}")
        print(f"   → Confidence: {analysis['confidence']:.0%}")
        print(f"   → Keywords: {[k for k,_,_ in analysis['matched_keywords'][:3]]}")
