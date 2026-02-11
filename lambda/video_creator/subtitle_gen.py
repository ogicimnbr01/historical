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
Style: Default,Arial Black,52,&H00E0E0FF,&H000000FF,&H00202040,&H80000000,1,0,0,0,100,100,1,0,1,3,2,2,40,40,350,1
Style: Hook,Arial Black,58,&H0088CCFF,&H000000FF,&H00203060,&H80000000,1,0,0,0,100,100,1,0,1,4,3,2,40,40,350,1
Style: Emphasis,Arial Black,56,&H0080D0FF,&H000000FF,&H00304050,&H80000000,1,0,0,0,105,100,2,0,1,4,2,2,40,40,350,1
Style: Ending,Arial Black,54,&H00C0A080,&H000000FF,&H00403020,&H80000000,1,1,0,0,100,100,1,0,1,3,2,2,40,40,350,1

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
    unique_id = uuid.uuid4().hex[:8]  # pyre-ignore[16]
    subtitle_path = os.path.join(tempfile.gettempdir(), f"subtitles_{unique_id}.ass")
    
    events = []
    
    # Split text into sentences - more robust approach
    # First, normalize ellipsis and other punctuation
    normalized_text = narration_text.replace('...', '…')  # Normalize ellipsis
    normalized_text = normalized_text.replace('..', '.')   # Fix double dots
    
    # Split on sentence-ending punctuation, keeping the punctuation
    segments = re.split(r'(?<=[.?!…])\s+', normalized_text)
    
    # Filter out empty strings and standalone punctuation
    phrases = []
    for seg in segments:
        seg = seg.strip()
        # Skip empty strings or strings that are only punctuation
        if seg and len(seg) > 1 and not all(c in '.?!…, ' for c in seg):
            phrases.append(seg)
        elif seg and len(seg) == 1 and seg not in '.?!…':
            # Single character that's not punctuation - keep it
            phrases.append(seg)
    
    if not phrases:
        phrases = [narration_text.strip()]
    
    # Calculate timing based on word count (weighted duration)
    # Longer phrases get proportionally more time
    word_counts = [len(phrase.split()) for phrase in phrases]
    total_words = sum(word_counts) or 1
    
    # Calculate weighted durations
    phrase_timings = []
    current_time = 0.0
    for i, phrase in enumerate(phrases):
        # Weight by word count with minimum duration of 1.5 seconds
        weight = word_counts[i] / total_words
        phrase_duration = max(1.5, total_duration * weight)
        phrase_timings.append((current_time, current_time + phrase_duration, phrase))
        current_time += phrase_duration
    
    # Normalize timings to fit total duration
    if current_time > total_duration:
        scale = total_duration / current_time
        phrase_timings = [(s * scale, e * scale, p) for s, e, p in phrase_timings]
    
    for i, (start_time, end_time, phrase) in enumerate(phrase_timings):
        # Choose style based on position
        if i == 0:
            style = "Hook"  # First sentence - dramatic
        elif i == len(phrase_timings) - 1:
            style = "Ending"  # Last sentence - reflective
        elif "but" in phrase.lower() or "however" in phrase.lower():
            style = "Emphasis"  # Contrast sentences
        else:
            style = "Default"
        
        # KARAOKE EFFECT: Word-by-word highlighting
        # Calculate duration per word for karaoke timing
        words = phrase.split()
        phrase_duration = end_time - start_time
        
        if len(words) > 1:
            # Use karaoke fill effect (\kf) for smooth word-by-word highlighting
            # Calculate centiseconds per word (ASS karaoke uses centiseconds)
            cs_per_word = int((phrase_duration * 100) / len(words))
            
            # Build karaoke text with \kf tags
            karaoke_parts = []
            for j, word in enumerate(words):
                safe_word = escape_ass_text(word)
                # \kf = karaoke fill (smooth sweep), value is duration in centiseconds
                karaoke_parts.append(f"{{\\kf{cs_per_word}}}{safe_word}")
            
            karaoke_text = " ".join(karaoke_parts)
        else:
            # Single word - no karaoke needed
            karaoke_text = escape_ass_text(phrase)
        
        # Animation effects + karaoke base styling
        # \\1c = primary color (text), \\3c = outline color
        # Karaoke effect changes color as words are spoken
        
        if style == "Hook":
            # Hook: Gold highlight sweep with slide up
            effects = (
                "{\\fad(250,350)}"  # Fade in/out
                "{\\move(540,1560,540,1520,0,200)}"  # Slide up (moved higher)
                "{\\K1}"  # Karaoke mode - words light up with primary color
            )
        elif style == "Emphasis":
            # Emphasis: Brighter highlight with color flash
            effects = (
                "{\\fad(200,300)}"
                "{\\move(540,1560,540,1520,0,200)}"
                "{\\K1}"
            )
        elif style == "Ending":
            # Ending: Slower karaoke with elegant fade
            effects = (
                "{\\fad(400,600)}"
                "{\\move(540,1560,540,1520,0,300)}"
                "{\\K1}"
            )
        else:
            # Default style with karaoke
            effects = (
                "{\\fad(250,350)}"
                "{\\move(540,1560,540,1520,0,200)}"
                "{\\K1}"
            )
        
        events.append(
            f"Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},{style},,0,0,0,,{effects}{karaoke_text}"
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
    unique_id = uuid.uuid4().hex[:8]  # pyre-ignore[16]
    subtitle_path = os.path.join(tempfile.gettempdir(), f"simple_sub_{unique_id}.ass")
    
    safe_text = escape_ass_text(text[:80])  # Limit length  # pyre-ignore[16]
    
    content = HISTORY_STYLE + f"Dialogue: 0,{format_ass_time(0)},{format_ass_time(duration)},Default,,0,0,0,,{{\\fad(500,500)}}{safe_text}\n"
    
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
