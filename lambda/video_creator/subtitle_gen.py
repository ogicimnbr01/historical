"""
Subtitle Generator for History YouTube Shorts
Creates ASS (Advanced SubStation Alpha) subtitle files
ANIMATED, COLORFUL styling with word-by-word reveal effects
"""

import os
import tempfile
from typing import List, Tuple
import uuid
import re


# HISTORY STYLE - Animated, golden text with dramatic effects
# Inspired by documentary/cinema title cards
HISTORY_STYLE = """
[Script Info]
Title: History Shorts Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial Black,52,&H00E0E0FF,&H000000FF,&H00202040,&H80000000,1,0,0,0,100,100,1,0,1,3,2,2,40,40,200,1
Style: Hook,Arial Black,58,&H0088CCFF,&H000000FF,&H00203060,&H80000000,1,0,0,0,100,100,1,0,1,4,3,2,40,40,200,1
Style: Emphasis,Arial Black,56,&H0080D0FF,&H000000FF,&H00304050,&H80000000,1,0,0,0,105,100,2,0,1,4,2,2,40,40,200,1
Style: Ending,Arial Black,54,&H00C0A080,&H000000FF,&H00403020,&H80000000,1,1,0,0,100,100,1,0,1,3,2,2,40,40,200,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# Color palette for word highlighting (ASS format BGR)
HIGHLIGHT_COLORS = [
    "&H0088CCFF",  # Golden/amber
    "&H00A0D0FF",  # Warm gold
    "&H0080CCFF",  # Orange-gold
    "&H00C0E0FF",  # Light gold
]


def format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.CC)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def create_subtitle_file(
    title: str,
    narration_text: str,
    total_duration: float
) -> str:
    """
    Create an ASS subtitle file with ANIMATED, HISTORY styling
    Features:
    - Word-by-word fade-in animation
    - Golden/amber color scheme
    - Slide-up entrance effect
    - Different styles for hook/emphasis/ending
    
    Args:
        title: Video title (not displayed - keeping it minimal)
        narration_text: Full narration text
        total_duration: Total video duration in seconds
        
    Returns:
        Path to the created ASS subtitle file
    """
    unique_id = uuid.uuid4().hex[:8]
    subtitle_path = os.path.join(tempfile.gettempdir(), f"subtitles_{unique_id}.ass")
    
    events = []
    
    # Split text into sentences
    segments = re.split(r'([.?!])', narration_text)
    
    # Recombine segments with their punctuation
    phrases = []
    current_phrase = ""
    
    for seg in segments:
        current_phrase += seg
        if seg in '.?!':
            if current_phrase.strip():
                phrases.append(current_phrase.strip())
            current_phrase = ""
            
    if current_phrase.strip():
        phrases.append(current_phrase.strip())
        
    if not phrases:
        phrases = [narration_text]
    
    # Calculate timing
    phrase_duration = total_duration / len(phrases)
    
    for i, phrase in enumerate(phrases):
        start_time = i * phrase_duration
        end_time = (i + 1) * phrase_duration
        
        # Choose style based on position
        if i == 0:
            style = "Hook"  # First sentence - dramatic
        elif i == len(phrases) - 1:
            style = "Ending"  # Last sentence - reflective
        elif "but" in phrase.lower() or "however" in phrase.lower():
            style = "Emphasis"  # Contrast sentences
        else:
            style = "Default"
        
        safe_phrase = escape_ass_text(phrase)
        
        # Animation effects:
        # \\fad(300,400) - fade in/out
        # \\move(x1,y1,x2,y2) - slide animation
        # \\t(\\fscx110) - scale animation
        
        # Slide up entrance + fade + subtle scale pop
        effects = (
            "{\\fad(250,350)}"  # Fade in/out
            "{\\move(540,1760,540,1720,0,200)}"  # Slide up
            "{\\t(0,150,\\fscx105\\fscy105)}"  # Slight scale pop
            "{\\t(150,300,\\fscx100\\fscy100)}"  # Scale back
        )
        
        # For emphasis, add color flash
        if style == "Emphasis":
            effects = (
                "{\\fad(200,300)}"
                "{\\move(540,1760,540,1720,0,200)}"
                "{\\t(0,100,\\c&H0080D0FF&\\fscx108)}"
                "{\\t(100,250,\\c&H00E0E0FF&\\fscx100)}"
            )
        
        # For ending, slower fade
        if style == "Ending":
            effects = (
                "{\\fad(400,600)}"
                "{\\move(540,1760,540,1720,0,300)}"
                "{\\t(0,200,\\fscx102)}"
            )
        
        events.append(
            f"Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},{style},,0,0,0,,{effects}{safe_phrase}"
        )
    
    # Write the ASS file
    with open(subtitle_path, 'w', encoding='utf-8') as f:
        f.write(HISTORY_STYLE)
        f.write('\n'.join(events))
        f.write('\n')
    
    print(f"✅ Created animated history subtitle file: {subtitle_path}")
    return subtitle_path


def escape_ass_text(text: str) -> str:
    """Escape special characters for ASS format"""
    # Replace newlines with ASS newline
    text = text.replace('\n', '\\N')
    # Escape backslashes (but not our escaped newlines)
    text = text.replace('\\N', '<<<NEWLINE>>>')
    text = text.replace('\\', '\\\\')
    text = text.replace('<<<NEWLINE>>>', '\\N')
    # Remove or escape other special characters
    text = text.replace('{', '\\{')
    text = text.replace('}', '\\}')
    return text


def create_simple_subtitle(text: str, duration: float) -> str:
    """
    Create a simple single-line subtitle file
    For when you just need basic text overlay
    """
    unique_id = uuid.uuid4().hex[:8]
    subtitle_path = os.path.join(tempfile.gettempdir(), f"simple_sub_{unique_id}.ass")
    
    safe_text = escape_ass_text(text[:80])  # Limit length
    
    content = CALM_STYLE + f"Dialogue: 0,{format_ass_time(0)},{format_ass_time(duration)},Default,,0,0,0,,{{\\fad(500,500)}}{safe_text}\n"
    
    with open(subtitle_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return subtitle_path


if __name__ == "__main__":
    # Test subtitle generation
    path = create_subtitle_file(
        title="🌙 Long day?",
        narration_text="Mind feels loud? You don't have to solve anything right now. Just breathe.",
        total_duration=10.0
    )
    print(f"Created: {path}")
    
    # Print contents
    with open(path, 'r') as f:
        print(f.read())
