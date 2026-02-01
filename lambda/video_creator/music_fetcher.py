"""
Historical Music Generator for YouTube Shorts
Generates period-appropriate background music using FFmpeg
All content is original/AI-generated - 100% copyright-safe
"""

import os
import subprocess
import tempfile
import uuid
import random
from typing import Optional, Dict

# FFmpeg binary path in Lambda Layer
def get_ffmpeg_path() -> str:
    """Get FFmpeg binary path"""
    if os.path.exists("/opt/bin/ffmpeg"):
        return "/opt/bin/ffmpeg"
    return "ffmpeg"


# Historical music presets based on content type
MUSIC_PRESETS = {
    # Epic/Battle music - deep drums and low tones
    "epic_orchestral": {
        "name": "epic_orchestral",
        "base_freq": 55.00,    # A1 - Deep timpani-like
        "mid_freq": 110.00,    # A2 - Low strings
        "high_freq": 220.00,   # A3 - Higher strings
        "volumes": (0.15, 0.10, 0.06),
        "tremolo": (0.8, 0.4),  # Faster tremolo for drama
    },
    
    # War drums - rhythmic, intense
    "war_drums": {
        "name": "war_drums",
        "base_freq": 45.00,    # Very deep drum
        "mid_freq": 90.00,     # Mid drum
        "high_freq": 180.00,   # Accent
        "volumes": (0.18, 0.12, 0.05),
        "tremolo": (1.2, 0.6),  # Rhythmic pulse
    },
    
    # Nostalgic piano - warm, emotional
    "nostalgic_piano": {
        "name": "nostalgic_piano",
        "base_freq": 130.81,   # C3 - Piano-like
        "mid_freq": 196.00,    # G3 - Gentle
        "high_freq": 261.63,   # C4 - Soft high
        "volumes": (0.10, 0.08, 0.05),
        "tremolo": (0.3, 0.2),  # Subtle movement
    },
    
    # Dramatic strings - tense moments
    "dramatic_strings": {
        "name": "dramatic_strings",
        "base_freq": 73.42,    # D2 - Cello-like
        "mid_freq": 146.83,    # D3 - Viola range
        "high_freq": 293.66,   # D4 - Violin
        "volumes": (0.12, 0.10, 0.08),
        "tremolo": (0.6, 0.4),  # String tremolo
    },
    
    # Ottoman/Oriental - exotic, mysterious
    "ottoman_oriental": {
        "name": "ottoman_oriental",
        "base_freq": 98.00,    # G2 - Oud-like base
        "mid_freq": 196.00,    # G3 - Ney-like mid
        "high_freq": 392.00,   # G4 - High shimmer
        "volumes": (0.09, 0.11, 0.07),  # Mid-heavy for ney effect
        "tremolo": (0.4, 0.3),
    },
    
    # Ancient/Classical - marble halls feeling
    "ancient_classical": {
        "name": "ancient_classical",
        "base_freq": 82.41,    # E2 - Lyre-like
        "mid_freq": 164.81,    # E3
        "high_freq": 329.63,   # E4
        "volumes": (0.08, 0.10, 0.06),
        "tremolo": (0.3, 0.2),
    },
    
    # Medieval - castle atmosphere
    "medieval_court": {
        "name": "medieval_court",
        "base_freq": 65.41,    # C2 - Deep organ
        "mid_freq": 130.81,    # C3
        "high_freq": 261.63,   # C4
        "volumes": (0.11, 0.09, 0.05),
        "tremolo": (0.4, 0.25),
    },
}

# Mapping from mood/era to music style
MOOD_TO_MUSIC = {
    "epic": "epic_orchestral",
    "nostalgic": "nostalgic_piano",
    "documentary": "nostalgic_piano",
    "dramatic": "dramatic_strings",
    "war": "war_drums",
    "battle": "war_drums",
    "ottoman": "ottoman_oriental",
    "ancient": "ancient_classical",
    "medieval": "medieval_court",
    "renaissance": "nostalgic_piano",
}


def generate_historical_music(duration: float = 30.0, music_style: str = None, mood: str = None, era: str = None) -> Optional[Dict]:
    """
    Generate period-appropriate background music using FFmpeg
    
    Args:
        duration: Duration in seconds
        music_style: Specific music style (epic_orchestral, nostalgic_piano, etc.)
        mood: Script mood for auto-selection
        era: Historical era for auto-selection
        
    Returns:
        Dict with 'path' to music file and 'metadata' for copyright tracking
        None if generation fails
    """
    from copyright_safety import get_copyright_tracker
    
    unique_id = uuid.uuid4().hex[:8]
    
    # Select preset based on priority: explicit style > era > mood > random
    if music_style and music_style in MUSIC_PRESETS:
        preset_key = music_style
    elif era and era in MOOD_TO_MUSIC:
        preset_key = MOOD_TO_MUSIC[era]
    elif mood and mood in MOOD_TO_MUSIC:
        preset_key = MOOD_TO_MUSIC[mood]
    else:
        # Default to nostalgic piano for general history content
        preset_key = "nostalgic_piano"
    
    preset = MUSIC_PRESETS.get(preset_key, MUSIC_PRESETS["nostalgic_piano"])
    
    # Use AAC output (widely supported)
    output_path = os.path.join(tempfile.gettempdir(), f"history_music_{unique_id}.m4a")
    
    try:
        # Generate background music using FFmpeg synthesis
        tremolo_freq, tremolo_depth = preset.get("tremolo", (0.5, 0.3))
        
        cmd = [
            get_ffmpeg_path(),
            '-y',
            # Low drone (foundation)
            '-f', 'lavfi',
            '-i', f"sine=frequency={preset['base_freq']}:duration={duration}",
            # Mid tone (harmony)
            '-f', 'lavfi',
            '-i', f"sine=frequency={preset['mid_freq']}:duration={duration}",
            # High tone (shimmer)
            '-f', 'lavfi',
            '-i', f"sine=frequency={preset['high_freq']}:duration={duration}",
            # Mix with volumes, apply effects
            '-filter_complex', (
                f"[0:a]volume={preset['volumes'][0]},tremolo=f={tremolo_freq}:d={tremolo_depth}[a0];"
                f"[1:a]volume={preset['volumes'][1]},tremolo=f={tremolo_freq*0.7}:d={tremolo_depth*0.8}[a1];"
                f"[2:a]volume={preset['volumes'][2]},tremolo=f={tremolo_freq*1.3}:d={tremolo_depth*0.6}[a2];"
                f"[a0][a1][a2]amix=inputs=3:duration=first[mixed];"
                f"[mixed]afade=t=in:st=0:d=2,afade=t=out:st={max(0, duration-2)}:d=2,"
                f"lowpass=f=1200,volume=2.0[out]"  # Warmer sound
            ),
            '-map', '[out]',
            '-c:a', 'aac',
            '-b:a', '128k',
            output_path
        ]
        
        print(f"🎵 Generating {preset['name']} music...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"⚠️ AAC output failed, trying WAV...")
            # Fallback to WAV
            output_path = output_path.replace('.m4a', '.wav')
            cmd[-1] = output_path
            cmd[-3] = 'pcm_s16le'
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode != 0:
                print(f"❌ FFmpeg music error: {result.stderr[:500]}")
                return None
        
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 1000:
                # Track in copyright system
                tracker = get_copyright_tracker()
                tracker.add_music(
                    source="self_generated",
                    music_id=unique_id,
                    title=f"History Shorts - {preset['name']}",
                    artist="System Generated",
                    license_type="Original Content"
                )
                
                print(f"✅ Generated {preset['name']} music: {output_path} ({file_size} bytes)")
                
                return {
                    "path": output_path,
                    "metadata": {
                        "source": "self_generated",
                        "title": f"History Shorts - {preset['name']}",
                        "artist": "System Generated",
                        "license": "Original Content - No Copyright",
                        "safe_for_youtube": True
                    }
                }
            else:
                print(f"❌ Music file too small: {file_size} bytes")
                return None
        
        print(f"❌ Music file not created")
        return None
        
    except Exception as e:
        print(f"❌ Error generating music: {e}")
        return None


# Backward compatible functions
def generate_ambient_music(duration: float = 30.0) -> Optional[Dict]:
    """Backward compatible - now generates historical music"""
    return generate_historical_music(duration=duration, music_style="nostalgic_piano")

def fetch_background_music(mood: str = "calm", duration_hint: float = 30.0, api_key: str = None) -> Optional[Dict]:
    """Backward compatible - now generates historical music"""
    return generate_historical_music(duration=duration_hint, mood=mood)


if __name__ == "__main__":
    # Test music generation
    print("Testing Historical Music Generator...")
    
    # Test different styles
    for style in ["epic_orchestral", "nostalgic_piano", "war_drums"]:
        print(f"\nTesting {style}...")
        result = generate_historical_music(10.0, music_style=style)
        if result:
            print(f"  Generated: {result['path']}")
        else:
            print(f"  Failed!")
