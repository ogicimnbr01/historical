"""
Subtitle Generator for History YouTube Shorts
HORMOZI STYLE: Word-blast kinetic text
1-3 words at a time, BIG font, scale-up pop animation
Designed for maximum retention on Shorts/TikTok

v2.0 - "Street Smart Edition"
"""

import os
import tempfile
from typing import List, Tuple
import uuid
import re


# HORMOZI STYLE - Big, bold, center-screen word blasts
# Inspired by Alex Hormozi / viral TikTok text overlays
HORMOZI_STYLE = """
[Script Info]
Title: History Shorts - Hormozi Style
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: None
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,72,&H00FFFFFF,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,2,0,1,5,3,5,40,40,550,1
Style: Emphasis,Impact,82,&H0000FFFF,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,2,0,1,6,3,5,40,40,550,1
Style: Hook,Impact,86,&H0000CCFF,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,2,0,1,6,4,5,40,40,550,1
Style: Ending,Impact,78,&H0080D0FF,&H000000FF,&H00000000,&HC0000000,1,0,0,0,100,100,2,0,1,5,3,5,40,40,550,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# Power words that get YELLOW emphasis (Hormozi trick)
POWER_WORDS = {
    "never", "always", "killed", "died", "destroyed", "impossible", "secret",
    "actually", "truth", "lie", "wrong", "insane", "crazy", "worst", "best",
    "only", "first", "last", "real", "fake", "hidden", "banned", "forbidden",
    "deadliest", "bloodiest", "biggest", "smallest", "richest", "poorest",
    "war", "death", "murder", "empire", "fall", "collapse", "betrayed",
    "everything", "nothing", "nobody", "everyone", "million", "billion",
    "ancient", "forgotten", "lost", "cursed", "haunted", "legendary",
}


def format_ass_time(seconds: float) -> str:
    """Convert seconds to ASS time format (H:MM:SS.CC)"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centisecs = int((seconds - int(seconds)) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centisecs:02d}"


def is_power_word(word: str) -> bool:
    """Check if a word should get yellow emphasis"""
    clean = re.sub(r'[^a-zA-Z]', '', word).lower()
    return clean in POWER_WORDS


def chunk_words(words: List[str], max_chunk: int = 3) -> List[str]:
    """
    Split words into 1-3 word chunks for Hormozi-style display.
    
    Rules:
    - Power words get their own chunk (solo blast)
    - Short common words attach to the next word
    - Max 3 words per chunk
    """
    chunks = []
    i = 0
    
    while i < len(words):  # pyre-ignore[6]
        word = words[i]
        
        # Power word = solo blast
        if is_power_word(word):
            chunks.append(word)
            i += 1  # pyre-ignore[6]
            continue
        
        # Build chunk of 1-3 words
        chunk = [word]
        remaining = min(max_chunk - 1, len(words) - i - 1)  # pyre-ignore[6]
        
        for j in range(1, remaining + 1):
            next_word = words[i + j]  # pyre-ignore[6]
            # If next word is a power word, stop here — it gets its own chunk
            if is_power_word(next_word):
                break
            chunk.append(next_word)
            # Stop at 2 words if current chunk is already getting long
            total_chars = sum(len(w) for w in chunk)
            if total_chars > 14:
                break
        
        chunks.append(" ".join(chunk))
        i += len(chunk)  # pyre-ignore[6]
    
    return chunks


def create_subtitle_file(
    title: str,
    narration_text: str,
    total_duration: float
) -> str:
    """
    Create an ASS subtitle file with HORMOZI STYLE word blasts.
    
    Features:
    - 1-3 words at a time (NOT full sentences)
    - Scale-up POP animation on each word group
    - Power words in YELLOW with extra size
    - Center-screen positioning for maximum eye-catch
    
    Args:
        title: Video title (not displayed)
        narration_text: Full narration text
        total_duration: Total video duration in seconds
        
    Returns:
        Path to the created ASS subtitle file
    """
    unique_id = uuid.uuid4().hex[:8]  # pyre-ignore[16]
    subtitle_path = os.path.join(tempfile.gettempdir(), f"subtitles_{unique_id}.ass")
    
    events = []
    
    # Split text into sentences first for section detection
    normalized_text = narration_text.replace('...', '…').replace('..', '.')
    sentences = re.split(r'(?<=[.?!…])\s+', normalized_text)
    sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 1]
    
    if not sentences:
        sentences = [narration_text.strip()]
    
    # Calculate total words for timing
    all_words = narration_text.split()
    total_words = len(all_words) or 1
    
    # Build word-level timing: each word gets equal time share
    word_duration = total_duration / total_words
    
    # Now iterate through sentences, chunk their words, and create events
    global_word_index = 0
    
    for sent_idx, sentence in enumerate(sentences):
        words = sentence.split()
        if not words:
            continue
        
        # Determine style based on sentence position
        if sent_idx == 0:
            base_style = "Hook"
        elif sent_idx == len(sentences) - 1:
            base_style = "Ending"
        else:
            base_style = "Default"
        
        # Chunk the words into 1-3 word groups
        chunks = chunk_words(words)
        
        for chunk in chunks:
            chunk_word_count = len(chunk.split())
            
            # Calculate timing based on word position
            start_time = global_word_index * word_duration  # pyre-ignore[6]
            end_time = (global_word_index + chunk_word_count) * word_duration  # pyre-ignore[6]
            
            # Minimum display time: 0.25s per word, minimum 0.4s total
            min_display = max(0.4, chunk_word_count * 0.25)
            if (end_time - start_time) < min_display:
                end_time = start_time + min_display
            
            # Clamp to total duration
            if end_time > total_duration:
                end_time = total_duration
            if start_time >= total_duration:
                break
            
            # Check if this chunk contains a power word
            has_power = any(is_power_word(w) for w in chunk.split())
            style = "Emphasis" if has_power else base_style
            
            # Escape text for ASS
            safe_text = escape_ass_text(chunk.upper())  # ALL CAPS for impact
            
            # ANIMATION: Scale-up pop + fade
            # \fscx130\fscy130 → \fscx100\fscy100 = "pop in" effect
            # \fad(80,120) = quick fade in/out
            # \an5 = center alignment override
            if has_power:
                # Power words: BIGGER pop, yellow color flash
                effects = (
                    "{\\an5}"
                    "{\\fad(60,100)}"
                    "{\\t(0,80,\\fscx100\\fscy100)}"  # Scale down from 140% to 100%
                    "{\\fscx140\\fscy140}"  # Start at 140%
                    "{\\1c&H00FFFF&}"  # Yellow (BGR)
                )
            else:
                # Normal words: standard pop
                effects = (
                    "{\\an5}"
                    "{\\fad(60,100)}"
                    "{\\t(0,80,\\fscx100\\fscy100)}"  # Scale down from 120% to 100%
                    "{\\fscx120\\fscy120}"  # Start at 120%
                )
            
            events.append(
                f"Dialogue: 0,{format_ass_time(start_time)},{format_ass_time(end_time)},{style},,0,0,0,,{effects}{safe_text}"
            )
            
            global_word_index += chunk_word_count  # pyre-ignore[6]
    
    # Write the ASS file
    with open(subtitle_path, 'w', encoding='utf-8') as f:
        f.write(HORMOZI_STYLE)
        f.write('\n'.join(events))
        f.write('\n')
    
    print(f"✅ Created HORMOZI-style subtitle file: {subtitle_path}")
    print(f"   Word blasts: {len(events)} chunks from {total_words} words")
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
    
    content = HORMOZI_STYLE + f"Dialogue: 0,{format_ass_time(0)},{format_ass_time(duration)},Default,,0,0,0,,{{\\an5}}{{\\fad(500,500)}}{safe_text}\n"
    
    with open(subtitle_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return subtitle_path


if __name__ == "__main__":
    # Test subtitle generation
    path = create_subtitle_file(
        title="🌙 Ancient Secret",
        narration_text="The Aztec Empire had a secret weapon. They never used swords. Instead, they used obsidian blades so sharp they could cut through steel. But here's the insane part. The Spanish destroyed every single one.",
        total_duration=15.0
    )
    print(f"\nCreated: {path}")
    
    # Print contents
    with open(path, 'r') as f:
        print(f.read())
