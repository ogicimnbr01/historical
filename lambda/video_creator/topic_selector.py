import random
from typing import List, Dict, Optional, Tuple

# ============================================================================
# THE HISTORY BUFFET: GLOBAL CONTENT STRATEGY
# ============================================================================
TOPIC_BUCKETS = {
    "modern_war": {
        "topics": [
            {"topic": "The spy who saved the world", "era": "modern", "figure": "Oleg Penkovsky", "search_entity": "Oleg Penkovsky"},
            {"topic": "Vietnam's underground city", "era": "modern", "figure": "Viet Cong", "search_entity": "Củ Chi tunnels"},
            {"topic": "The Manhattan Project secret", "era": "ww2", "figure": "Oppenheimer", "search_entity": "Manhattan Project"},
            {"topic": "The Ghost Army of WWII", "era": "ww2", "figure": "US Army", "search_entity": "Ghost Army"},
            {"topic": "Simo Häyhä: The White Death", "era": "ww2", "figure": "Simo Häyhä", "search_entity": "Simo Häyhä"},
            {"topic": "The unkillable soldier", "era": "ww1", "figure": "Adrian Carton de Wiart", "search_entity": "Adrian Carton de Wiart"},
            {"topic": "The tank that scared Hitler", "era": "ww2", "figure": "Tiger Tank", "search_entity": "Tiger I"},
        ],
        "weight": 0.15
    },
    "ancient": {
        "topics": [
            {"topic": "Why Spartans never built walls", "era": "ancient", "figure": "Spartan King", "search_entity": "Sparta"},
            {"topic": "Caesar's kidnapping revenge", "era": "ancient", "figure": "Julius Caesar", "search_entity": "Julius Caesar"},
            {"topic": "The richest man in history", "era": "ancient", "figure": "Mansa Musa", "search_entity": "Mansa Musa"},
            {"topic": "The lost legion of Rome", "era": "ancient", "figure": "Crassus", "search_entity": "Battle of Carrhae"},
            {"topic": "Cleopatra's smart strategy", "era": "ancient", "figure": "Cleopatra", "search_entity": "Cleopatra"},
            {"topic": "Alexander's biggest regret", "era": "ancient", "figure": "Alexander the Great", "search_entity": "Alexander the Great"},
            {"topic": "The library that burned civilization", "era": "ancient", "figure": "Hypatia", "search_entity": "Library of Alexandria"},
            {"topic": "Hannibal's impossible path", "era": "ancient", "figure": "Hannibal Barca", "search_entity": "Hannibal"},
        ],
        "weight": 0.30
    },
    "medieval": {
        "topics": [
            {"topic": "Samurai vs Knight: Who wins?", "era": "medieval", "figure": "Samurai", "search_entity": "Samurai"},
            {"topic": "The day Vikings attacked Paris", "era": "medieval", "figure": "Ragnar Lothbrok", "search_entity": "Siege of Paris (885–886)"},
            {"topic": "Genghis Khan's daughter diplomacy", "era": "medieval", "figure": "Genghis Khan", "search_entity": "Genghis Khan"},
            {"topic": "The Black Death doctor mask", "era": "medieval", "figure": "Plague Doctor", "search_entity": "Plague doctor"},
            {"topic": "Saladin's gift to his enemy", "era": "medieval", "figure": "Saladin", "search_entity": "Saladin"},
            {"topic": "The assassin order's secret", "era": "medieval", "figure": "Hassan-i Sabbah", "search_entity": "Order of Assassins"},
            {"topic": "The sword in the stone real story", "era": "medieval", "figure": "San Galgano", "search_entity": "San Galgano"},
        ],
        "weight": 0.25
    },
    "ottoman": {
        "topics": [
            {"topic": "Fatih Sultan Mehmet's cannon", "era": "ottoman", "figure": "Mehmed II", "search_entity": "Mehmed the Conqueror"},
            {"topic": "The woman who ruled the Ottomans", "era": "ottoman", "figure": "Hurrem Sultan", "search_entity": "Hurrem Sultan"},
            {"topic": "Janissary training secrets", "era": "ottoman", "figure": "Janissary", "search_entity": "Janissary"},
            {"topic": "Suleiman's heart buried in Hungary", "era": "ottoman", "figure": "Suleiman I", "search_entity": "Suleiman the Magnificent"},
            {"topic": "The Mad Sultan's swimming pool", "era": "ottoman", "figure": "Ibrahim I", "search_entity": "Ibrahim of the Ottoman Empire"},
            {"topic": "Hezarfen's flight from Galata", "era": "ottoman", "figure": "Hezarfen Ahmed Celebi", "search_entity": "Hezarfen Ahmed Celebi"},
            {"topic": "Mimar Sinan's secret signature", "era": "ottoman", "figure": "Mimar Sinan", "search_entity": "Mimar Sinan"},
        ],
        "weight": 0.15
    },
    "turkish_mythology": {
        "topics": [
            {"topic": "The Wolf Mother Asena", "era": "ancient", "figure": "Asena", "search_entity": "Asena (mythology)"},
            {"topic": "Ergenekon: The mountain melt", "era": "ancient", "figure": "Borte Chino", "search_entity": "Ergenekon"},
            {"topic": "Kayra Han and the Tree of Life", "era": "ancient", "figure": "Kayra Han", "search_entity": "Kayra Han"},
            {"topic": "Umay Ana: Protector of children", "era": "ancient", "figure": "Umay Ana", "search_entity": "Umay"},
            {"topic": "Tepegöz: The Cyclops of the Steppe", "era": "ancient", "figure": "Basat", "search_entity": "Tepegöz"},
            {"topic": "Alp Er Tunga's tragic end", "era": "ancient", "figure": "Alp Er Tunga", "search_entity": "Alp Er Tunga"},
        ],
        "weight": 0.10
    },
    "mystery": {
        "topics": [
            {"topic": "The Pirate who became a King", "era": "18th_century", "figure": "Black Sam Bellamy", "search_entity": "Samuel Bellamy"},
            {"topic": "Jack the Ripper's letters", "era": "19th_century", "figure": "Jack the Ripper", "search_entity": "Jack the Ripper"},
            {"topic": "The ship that vanished: Mary Celeste", "era": "19th_century", "figure": "Captain Briggs", "search_entity": "Mary Celeste"},
            {"topic": "The dancing plague of 1518", "era": "early_modern", "figure": "Frau Troffea", "search_entity": "Dancing plague of 1518"},
            {"topic": "Alcatraz escape attempt", "era": "modern", "figure": "Frank Morris", "search_entity": "June 1962 Alcatraz escape attempt"},
        ],
        "weight": 0.05
    },
    "anthropology_and_culture": {
        "topics": [
            {"topic": "Why Maori warriors stick out their tongues", "era": "modern", "figure": "Maori Warrior", "search_entity": "Haka"},
            {"topic": "The Aztec death whistle sound", "era": "ancient", "figure": "Aztec Priest", "search_entity": "Aztec death whistle"},
            {"topic": "Viking blood eagle ritual", "era": "medieval", "figure": "Viking Warrior", "search_entity": "Blood eagle"},
            {"topic": "Spartan Agoge training", "era": "ancient", "figure": "Spartan Warrior", "search_entity": "Agoge"},
            {"topic": "Mongol throat singing purpose", "era": "medieval", "figure": "Mongol Warrior", "search_entity": "Throat singing"},
            {"topic": "Druid human sacrifice rituals", "era": "ancient", "figure": "Celtic Druid", "search_entity": "Druid"},
            {"topic": "Why women lengthened their necks", "era": "modern", "figure": "Kayan Woman", "search_entity": "Kayan people (Myanmar)"},
            {"topic": "Tibetan Sky Burial ritual", "era": "modern", "figure": "Tibetan Monk", "search_entity": "Sky burial"},
            {"topic": "Sokushinbutsu: Japanese self-mummification", "era": "medieval", "figure": "Buddhist Monk", "search_entity": "Sokushinbutsu"},
            {"topic": "Chinese foot binding practice", "era": "19th_century", "figure": "Chinese Woman", "search_entity": "Foot binding"},
        ],
        "weight": 0.10
    }
}

def select_next_topic(
    past_topics: List[str], 
    category_weights: Optional[Dict[str, float]] = None, 
    last_category: Optional[str] = None,
    category_retention: Optional[Dict[str, float]] = None
) -> Tuple[Dict, str]:
    """
    Select the next topic based on weighted categories and forced diversity.
    
    Args:
        past_topics: List of recently used topic strings (to avoid repeats)
        category_weights: Optional override for weights (from autopilot config)
        last_category: The category of the last generated video (to force switch)
        category_retention: Optional dict of {category: avg_retention_pct}
            If a category's avg retention >= RETENTION_WAVE_THRESHOLD, 
            diversity blocking is skipped (wave surfing).
        
    Returns:
        Tuple[Dict, str]: (Selected topic data, Selected category name)
    """
    RETENTION_WAVE_THRESHOLD = 55.0  # % — above this, let the wave ride
    
    # 1. SETUP WEIGHTS
    # Use provided weights or fall back to defaults defined in TOPIC_BUCKETS
    weights: Dict[str, float] = {}
    if not category_weights:
        for k, v in TOPIC_BUCKETS.items():
            val = v["weight"]
            if isinstance(val, (int, float)):
                weights[k] = float(val)
            else:
                weights[k] = 0.2 # Fallback
    else:
        weights = category_weights.copy()
    
    # 2. FORCED DIVERSITY (The "No Repeat" Rule) — with retention override
    available_categories = list(weights.keys())
    
    if last_category and last_category in available_categories and len(available_categories) > 1:
        # Check if this category is on a hot streak (retention-aware diversity)
        cat_retention = (category_retention or {}).get(last_category, 0.0)
        
        if cat_retention >= RETENTION_WAVE_THRESHOLD:
            # 🏄 WAVE SURFING: Category is performing well, let it repeat
            print(f"🏄 Wave Surfing: '{last_category}' avg retention {cat_retention:.1f}% >= {RETENTION_WAVE_THRESHOLD}% — allowing repeat!")
        else:
            # Normal diversity: block last category
            print(f"🔄 Forced Diversity: Blocking '{last_category}' (retention {cat_retention:.1f}% < {RETENTION_WAVE_THRESHOLD}%).")
            weights[last_category] = 0.0
        
    # Normalize weights after blocking
    total_weight = sum(weights.values())
    if total_weight <= 0:
        # Fallback if everything blocked (shouldn't happen)
        weights = {k: 1.0 for k in available_categories}
        total_weight = len(available_categories)
        
    normalized_weights = {k: v / total_weight for k, v in weights.items()}
    
    # 3. SELECT CATEGORY
    selected_category = random.choices(
        population=list(normalized_weights.keys()),
        weights=list(normalized_weights.values()),
        k=1
    )[0]
    
    print(f"🌍 Global Strategy: Selected Category '{selected_category}' (Weight: {normalized_weights[selected_category]:.2f})")
    
    # 4. SELECT TOPIC FROM BUCKET
    # Filter out topics that are too similar to past topics
    # Filter out topics that are too similar to past topics
    from typing import cast, List, Dict, Any
    bucket_topics = cast(List[Dict[str, str]], TOPIC_BUCKETS[selected_category]["topics"])
    valid_topics = [t for t in bucket_topics if not is_topic_used(t["topic"], past_topics)]
    
    if not valid_topics:
        print(f"⚠️ All topics in {selected_category} used! Resetting checking for this bucket.")
        valid_topics = bucket_topics
        
    selected_topic_data = random.choice(valid_topics)
    
    return selected_topic_data, selected_category

def is_topic_used(new_topic: str, past_topics: List[str]) -> bool:
    """Check if topic is semantically similar to past topics."""
    new_lower = new_topic.lower()
    for past in past_topics:
        if new_lower in past.lower() or past.lower() in new_lower:
            return True
    return False
