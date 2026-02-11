"""
Sound Effects (SFX) Generator for History YouTube Shorts
Generates context-aware ambient sounds and foley effects
Uses FFmpeg to create atmospheric audio layers
"""

import os
import subprocess
import tempfile
import uuid
import random
from typing import Optional, Dict, List


def get_ffmpeg_path() -> str:
    """Get FFmpeg binary path"""
    if os.path.exists("/opt/bin/ffmpeg"):
        return "/opt/bin/ffmpeg"
    return "ffmpeg"


# Context keywords mapped to ambient sound types
CONTEXT_SFX_MAP = {
    # War/Battle contexts
    "battle": "war_ambient",
    "war": "war_ambient", 
    "fight": "war_ambient",
    "sword": "sword_clash",
    "army": "war_ambient",
    "soldiers": "war_ambient",
    "military": "war_ambient",
    "cannon": "war_ambient",
    "conquest": "war_ambient",
    "siege": "war_ambient",
    
    # Food/Dining contexts
    "dinner": "dining_ambient",
    "food": "dining_ambient",
    "meal": "dining_ambient",
    "eating": "dining_ambient",
    "breakfast": "dining_ambient",
    "lunch": "dining_ambient",
    "pilaf": "dining_ambient",
    "rice": "dining_ambient",
    "beans": "dining_ambient",
    "cooking": "kitchen_sounds",
    "kitchen": "kitchen_sounds",
    
    # Palace/Royal contexts
    "palace": "palace_ambient",
    "throne": "palace_ambient",
    "crown": "palace_ambient",
    "royal": "palace_ambient",
    "emperor": "palace_ambient",
    "sultan": "palace_ambient",
    "king": "palace_ambient",
    "queen": "palace_ambient",
    
    # Nature contexts
    "horse": "nature_ambient",
    "steppe": "wind_ambient",
    "desert": "wind_ambient",
    "mountain": "wind_ambient",
    "forest": "nature_ambient",
    "sea": "ocean_ambient",
    "ship": "ocean_ambient",
    
    # City/Architecture contexts
    "city": "city_ambient",
    "mosque": "mosque_ambient",
    "church": "church_ambient",
    "temple": "temple_ambient",
    "istanbul": "city_ambient",
    "constantinople": "city_ambient",
    
    # Personal/Emotional contexts
    "mother": "gentle_ambient",
    "family": "gentle_ambient",
    "home": "gentle_ambient",
    "childhood": "gentle_ambient",
    "memory": "vinyl_crackle",
    "history": "vinyl_crackle",
}


def detect_context(text: str) -> List[str]:
    """
    Detect context keywords in text and return matching SFX types
    """
    text_lower = text.lower()
    detected = []
    
    for keyword, sfx_type in CONTEXT_SFX_MAP.items():
        if keyword in text_lower and sfx_type not in detected:
            detected.append(sfx_type)
    
    # Default to vinyl crackle for historical content
    if not detected:
        detected.append("vinyl_crackle")
    
    return detected[:2]  # Max 2 ambient layers  # pyre-ignore[16]


def generate_ambient_sfx(sfx_type: str, duration: float = 15.0) -> Optional[str]:
    """
    Generate ambient sound effect using FFmpeg
    
    Args:
        sfx_type: Type of ambient sound to generate
        duration: Duration in seconds
        
    Returns:
        Path to generated audio file or None
    """
    unique_id = uuid.uuid4().hex[:6]  # pyre-ignore[16]
    output_path = os.path.join(tempfile.gettempdir(), f"sfx_{sfx_type}_{unique_id}.m4a")
    
    # FFmpeg audio synthesis parameters by type
    sfx_configs = {
        "vinyl_crackle": {
            # Vinyl record crackle - adds nostalgic feel
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.008,"
                "highpass=f=200,"
                "lowpass=f=8000,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.15
        },
        "war_ambient": {
            # Distant rumble and low frequency tension
            "filter": (
                "anoisesrc=d={duration}:c=brown:a=0.02,"
                "lowpass=f=400,"
                "tremolo=f=0.5:d=0.3,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.12
        },
        "wind_ambient": {
            # Wind/breeze sound
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.015,"
                "lowpass=f=2000,"
                "highpass=f=100,"
                "tremolo=f=0.2:d=0.5,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.10
        },
        "dining_ambient": {
            # Subtle restaurant ambience
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.005,"
                "lowpass=f=4000,"
                "highpass=f=300,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.08
        },
        "palace_ambient": {
            # Grand hall reverb-like ambient
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.003,"
                "lowpass=f=3000,"
                "aecho=0.8:0.8:60:0.3,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.10
        },
        "gentle_ambient": {
            # Warm, soft ambient for emotional moments
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.004,"
                "lowpass=f=2500,"
                "highpass=f=150,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.08
        },
        "nature_ambient": {
            # Natural outdoor ambience
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.01,"
                "lowpass=f=5000,"
                "highpass=f=100,"
                "tremolo=f=0.1:d=0.2,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.10
        },
        "ocean_ambient": {
            # Ocean waves
            "filter": (
                "anoisesrc=d={duration}:c=brown:a=0.02,"
                "lowpass=f=1500,"
                "tremolo=f=0.08:d=0.8,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.12
        },
        "city_ambient": {
            # City background
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.008,"
                "lowpass=f=4000,"
                "highpass=f=200,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.08
        },
        "mosque_ambient": {
            # Reverberant space
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.002,"
                "lowpass=f=2000,"
                "aecho=0.8:0.9:100:0.4,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.08
        },
        "church_ambient": {
            # Cathedral reverb
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.002,"
                "lowpass=f=2500,"
                "aecho=0.8:0.88:120:0.35,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.08
        },
        "temple_ambient": {
            # Temple atmosphere
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.003,"
                "lowpass=f=2200,"
                "aecho=0.8:0.85:80:0.3,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.08
        },
        "kitchen_sounds": {
            # Kitchen ambience
            "filter": (
                "anoisesrc=d={duration}:c=pink:a=0.006,"
                "lowpass=f=6000,"
                "highpass=f=400,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.07
        },
        "sword_clash": {
            # Metallic tension
            "filter": (
                "anoisesrc=d={duration}:c=white:a=0.01,"
                "highpass=f=2000,"
                "lowpass=f=8000,"
                "tremolo=f=2:d=0.1,"
                "aformat=sample_rates=44100"
            ),
            "volume": 0.06
        },
    }
    
    config = sfx_configs.get(sfx_type, sfx_configs["vinyl_crackle"])
    filter_str = config["filter"].format(duration=duration)  # pyre-ignore[16]
    volume = config["volume"]
    
    try:
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-f', 'lavfi',
            '-i', filter_str,
            '-af', f'volume={volume}',
            '-c:a', 'aac',
            '-b:a', '64k',
            '-t', str(duration),
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(output_path):
            print(f"🔊 Generated SFX: {sfx_type} -> {output_path}")
            return output_path
        else:
            print(f"⚠️ SFX generation failed: {result.stderr[:100] if result.stderr else 'unknown'}")  # pyre-ignore[16]
            return None
            
    except Exception as e:
        print(f"⚠️ SFX error: {e}")
        return None


def generate_context_sfx(voiceover_text: str, duration: float = 15.0) -> Optional[str]:
    """
    Generate context-aware ambient sound based on voiceover content
    Now includes event-based SFX (sword clash, cannon, etc.) at video start
    
    Args:
        voiceover_text: The script/voiceover text to analyze
        duration: Duration in seconds
        
    Returns:
        Path to generated SFX audio or None
    """
    # Detect context from text
    sfx_types = detect_context(voiceover_text)
    
    if not sfx_types:
        sfx_types = ["vinyl_crackle"]
    
    print(f"🎧 Detected SFX contexts: {sfx_types}")
    
    # Check for event-based SFX triggers
    event_sfx = detect_event_sfx(voiceover_text)
    
    # Generate primary ambient layer
    primary_sfx = generate_ambient_sfx(sfx_types[0], duration)
    
    if primary_sfx and event_sfx:
        # Mix event SFX with ambient
        mixed_path = mix_event_with_ambient(event_sfx, primary_sfx, duration)
        if mixed_path:
            print(f"🎧 Mixed event SFX with ambient: {mixed_path}")
            return mixed_path
    
    if primary_sfx:
        return primary_sfx
    
    # Fallback to vinyl crackle
    return generate_ambient_sfx("vinyl_crackle", duration)


# =============================================================================
# EVENT-BASED SFX - Short impact sounds triggered by context
# =============================================================================
EVENT_SFX_TRIGGERS = {
    # Battle/Combat events
    "sword": "sword_impact",
    "blade": "sword_impact",
    "steel": "sword_impact",
    "clash": "sword_impact",
    "cannon": "cannon_boom",
    "artillery": "cannon_boom",
    "gun": "cannon_boom",
    "fire": "cannon_boom",
    "explosion": "cannon_boom",
    
    # Naval events
    "ship": "wave_crash",
    "sea": "wave_crash",
    "ocean": "wave_crash",
    "admiral": "wave_crash",
    "navy": "wave_crash",
    "sailor": "wave_crash",
    "pirate": "wave_crash",
    
    # Cavalry/Movement events
    "horse": "horse_gallop",
    "cavalry": "horse_gallop",
    "charge": "horse_gallop",
    "rider": "horse_gallop",
    "gallop": "horse_gallop",
    
    # Victory/Crowd events
    "conquer": "crowd_cheer",
    "victory": "crowd_cheer",
    "triumph": "crowd_cheer",
    "celebrate": "crowd_cheer",
    "glory": "crowd_cheer",
}


def detect_event_sfx(text: str) -> Optional[str]:
    """
    Detect event-based SFX triggers in text
    Returns the most relevant event SFX type or None
    """
    text_lower = text.lower()
    
    # Priority order: sword > cannon > wave > horse > crowd
    priority_order = ["sword_impact", "cannon_boom", "wave_crash", "horse_gallop", "crowd_cheer"]
    detected = {}
    
    for keyword, sfx_type in EVENT_SFX_TRIGGERS.items():
        if keyword in text_lower:
            if sfx_type not in detected:
                detected[sfx_type] = 0
            detected[sfx_type] += 1
    
    if not detected:
        return None
    
    # Return highest priority detected SFX
    for sfx_type in priority_order:
        if sfx_type in detected:
            print(f"⚔️ Event SFX detected: {sfx_type}")
            return sfx_type
    
    return None


def generate_event_sfx(sfx_type: str) -> Optional[str]:
    """
    Generate short event-based sound effect (0.5-1.5 seconds)
    These are impact sounds, not ambient
    """
    unique_id = uuid.uuid4().hex[:6]  # pyre-ignore[16]
    output_path = os.path.join(tempfile.gettempdir(), f"event_{sfx_type}_{unique_id}.m4a")
    
    # Event SFX configurations - short, impactful sounds
    event_configs = {
        "sword_impact": {
            # Metallic clash sound
            "filter": (
                "anoisesrc=d=0.3:c=white:a=0.5,"
                "highpass=f=3000,"
                "lowpass=f=12000,"
                "afade=t=out:st=0.1:d=0.2,"
                "aformat=sample_rates=44100"
            ),
            "duration": 0.3,
            "volume": 0.4
        },
        "cannon_boom": {
            # Deep boom sound
            "filter": (
                "anoisesrc=d=1.0:c=brown:a=0.8,"
                "lowpass=f=200,"
                "afade=t=in:st=0:d=0.05,"
                "afade=t=out:st=0.2:d=0.8,"
                "aformat=sample_rates=44100"
            ),
            "duration": 1.0,
            "volume": 0.5
        },
        "wave_crash": {
            # Ocean wave crash
            "filter": (
                "anoisesrc=d=1.5:c=pink:a=0.3,"
                "lowpass=f=2000,"
                "tremolo=f=0.5:d=0.9,"
                "afade=t=in:st=0:d=0.3,"
                "afade=t=out:st=0.8:d=0.7,"
                "aformat=sample_rates=44100"
            ),
            "duration": 1.5,
            "volume": 0.3
        },
        "horse_gallop": {
            # Rhythmic galloping sound
            "filter": (
                "anoisesrc=d=1.2:c=brown:a=0.2,"
                "lowpass=f=500,"
                "tremolo=f=3:d=0.8,"
                "afade=t=out:st=0.8:d=0.4,"
                "aformat=sample_rates=44100"
            ),
            "duration": 1.2,
            "volume": 0.35
        },
        "crowd_cheer": {
            # Distant crowd roar
            "filter": (
                "anoisesrc=d=1.5:c=pink:a=0.15,"
                "lowpass=f=4000,"
                "highpass=f=300,"
                "tremolo=f=0.3:d=0.5,"
                "afade=t=in:st=0:d=0.3,"
                "afade=t=out:st=1.0:d=0.5,"
                "aformat=sample_rates=44100"
            ),
            "duration": 1.5,
            "volume": 0.25
        },
    }
    
    config = event_configs.get(sfx_type)
    if not config:
        return None
    
    try:
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-f', 'lavfi',
            '-i', config["filter"],
            '-af', f'volume={config["volume"]}',
            '-c:a', 'aac',
            '-b:a', '96k',
            '-t', str(config["duration"]),
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)  # pyre-ignore[6]
        
        if result.returncode == 0 and os.path.exists(output_path):
            print(f"⚔️ Generated event SFX: {sfx_type} -> {output_path}")
            return output_path
        else:
            print(f"⚠️ Event SFX generation failed: {result.stderr[:100] if result.stderr else 'unknown'}")
            return None
            
    except Exception as e:
        print(f"⚠️ Event SFX error: {e}")
        return None


def mix_event_with_ambient(event_type: str, ambient_path: str, duration: float) -> Optional[str]:
    """
    Mix event SFX at the beginning with ambient SFX throughout
    Event plays at 0.5s mark for impact after hook
    """
    # Generate the event SFX
    event_path = generate_event_sfx(event_type)
    if not event_path:
        return None
    
    unique_id = uuid.uuid4().hex[:6]  # pyre-ignore[16]
    output_path = os.path.join(tempfile.gettempdir(), f"mixed_sfx_{unique_id}.m4a")
    
    try:
        # Mix: ambient plays throughout, event plays at 0.5s
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-i', ambient_path,
            '-i', event_path,
            '-filter_complex', (
                f"[0:a]apad=whole_dur={duration}[ambient];"
                f"[1:a]adelay=500|500[event];"  # Delay event by 0.5s
                f"[ambient][event]amix=inputs=2:duration=first:dropout_transition=0[out]"
            ),
            '-map', '[out]',
            '-c:a', 'aac',
            '-b:a', '96k',
            '-t', str(duration),
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(output_path):
            print(f"🎧 Mixed SFX created: {output_path}")
            return output_path
        
    except Exception as e:
        print(f"⚠️ SFX mix error: {e}")
    
    return None


if __name__ == "__main__":
    # Test SFX generation
    print("Testing SFX Generator...")
    
    test_texts = [
        "He conquered Constantinople, but he couldn't sleep without his cat.",
        "At dinner, Atatürk wanted just his mother's simple pilaf.",
        "The samurai warrior drew his sword on the battlefield.",
    ]
    
    for text in test_texts:
        print(f"\n📝 Text: {text[:50]}...")  # pyre-ignore[16]
        contexts = detect_context(text)
        print(f"🎧 Contexts: {contexts}")
        sfx_path = generate_context_sfx(text, 5.0)
        if sfx_path:
            print(f"✅ Generated: {sfx_path}")
