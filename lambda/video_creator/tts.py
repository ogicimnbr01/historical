"""
Text-to-Speech using AWS Polly
Generates documentary-style voiceover for History YouTube Shorts
Deep, authoritative voices suitable for historical content
"""

import os
import boto3
import tempfile
import random


# AWS Polly client
polly = boto3.client('polly')

# Voice options by mood - Documentary/History focused
# Using male voices for authoritative documentary feel
VOICE_BY_MOOD = {
    # Primary Documentary moods
    "documentary": [
        # Deep, authoritative male voices for documentary narration
        {"id": "Matthew", "engine": "neural", "rate": "95%", "pitch": "-5%"},
        {"id": "Brian", "engine": "neural", "rate": "92%", "pitch": "-8%"},
        {"id": "Stephen", "engine": "neural", "rate": "94%", "pitch": "-3%"},
    ],
    "epic": [
        # Dramatic voices for battles and conquests - DEEP STORYTELLER MODE
        {"id": "Brian", "engine": "neural", "rate": "80%", "pitch": "-18%"},
        {"id": "Matthew", "engine": "neural", "rate": "78%", "pitch": "-20%"},
    ],
    "nostalgic": [
        # Warmer, more emotional for personal stories
        {"id": "Matthew", "engine": "neural", "rate": "90%", "pitch": "-3%"},
        {"id": "Stephen", "engine": "neural", "rate": "92%", "pitch": "-5%"},
    ],
    "dramatic": [
        # For tense historical moments
        {"id": "Brian", "engine": "neural", "rate": "85%", "pitch": "-15%"},
    ],
    
    # Legacy moods (kept for backward compatibility, redirect to documentary)
    "whisper": [
        {"id": "Matthew", "engine": "neural", "rate": "90%", "pitch": "-5%"},
    ],
    "gentle": [
        {"id": "Stephen", "engine": "neural", "rate": "92%", "pitch": "-3%"},
    ],
    "calm": [
        {"id": "Matthew", "engine": "neural", "rate": "92%", "pitch": "-5%"},
    ],
    "relaxing": [
        {"id": "Stephen", "engine": "neural", "rate": "90%", "pitch": "-5%"},
    ],
    "night": [
        {"id": "Brian", "engine": "neural", "rate": "88%", "pitch": "-10%"},
    ],
    "energetic": [
        {"id": "Matthew", "engine": "neural", "rate": "100%", "pitch": "0%"},
    ],
    "motivating": [
        {"id": "Matthew", "engine": "neural", "rate": "98%", "pitch": "-3%"},
    ],
}

# Default voices - deep, documentary style
DEFAULT_VOICES = [
    {"id": "Matthew", "engine": "neural", "rate": "95%", "pitch": "-5%"},
    {"id": "Brian", "engine": "neural", "rate": "92%", "pitch": "-8%"},
]

# Phonetic spelling dictionary for non-English names
# Helps English TTS pronounce Turkish/Foreign names correctly
PHONETIC_REPLACEMENTS = {
    # Turkish names
    "Atatürk": "Ah-tah-turk",
    "Ataturk": "Ah-tah-turk",
    "Mustafa Kemal": "Moos-tah-fah Keh-mahl",
    "Mustafa": "Moos-tah-fah",
    "Kemal": "Keh-mahl",
    "Fatih": "Fah-teeh",
    "Mehmed": "Meh-mehd",
    "Suleiman": "Soo-lay-mahn",
    "Süleyman": "Soo-lay-mahn",
    "Bayezid": "Bah-yeh-zeed",
    "Osman": "Ohs-mahn",
    "Orhan": "Or-hahn",
    "Selim": "Seh-leem",
    "Roxelana": "Rok-seh-lah-nah",
    "Hürrem": "Hoor-rehm",
    "Barbarossa": "Bar-bah-ross-ah",
    "Hayreddin": "High-red-deen",
    "Çanakkale": "Chah-nahk-kah-leh",
    "İstanbul": "Ees-tahn-bool",
    "Ankara": "Ahn-kah-rah",
    
    # Other non-English names that might be mispronounced
    "Genghis": "Jen-gis",
    "Saladin": "Sal-ah-deen",
    "Constantinople": "Con-stan-tee-no-pull",
    "Bosphorus": "Boss-for-us",
    "Hagia Sophia": "Hah-gee-ah So-fee-ah",
    
    # Greek phrases (commonly used in historical content)
    "Kai su, teknon": "Ky-soo, tek-non",
    "Kai su teknon": "Ky-soo tek-non",
    "teknon": "tek-non",
    "Molon labe": "Moh-lon lah-bay",
    "Thalassa": "Thah-lahs-sah",
    
    # Latin phrases
    "Et tu, Brute": "Et too, Broo-tay",
    "Et tu Brute": "Et too Broo-tay",
    "Brute": "Broo-tay",
    "Brutus": "Broo-tus",
    "Veni, vidi, vici": "Vay-nee, vee-dee, vee-chee",
    "Alea iacta est": "Ah-lay-ah yahk-tah est",
    "Carpe diem": "Kar-pay dee-em",
    "Memento mori": "Meh-men-toh mor-ee",
    "Pax Romana": "Paks Ro-mah-nah",
    
    # Arabic/Persian names
    "Selahaddin": "Seh-lah-had-deen",
    "Eyyubi": "Ay-yoo-bee",
    "Harun al-Rashid": "Hah-roon al-Rah-sheed",
    "Ibn Battuta": "Ib-en Bat-too-tah",
    "Al-Khwarizmi": "Al-Kwah-riz-mee",
    
    # Egyptian/Ancient names
    "Cleopatra": "Klee-oh-pat-rah",
    "Nefertiti": "Nef-er-tee-tee",
    "Tutankhamun": "Too-tan-kah-moon",
    "Ptolemy": "Tol-eh-mee",
    "Pharaoh": "Fair-oh",
    
    # Japanese
    "Shogun": "Show-gun",
    "Samurai": "Sam-oo-rye",
    "Bushido": "Boo-shee-doh",
    "Seppuku": "Sep-poo-koo",
}


def apply_phonetic_spelling(text: str) -> str:
    """
    Replace difficult names with phonetic spellings for better TTS pronunciation
    """
    result = text
    for original, phonetic in PHONETIC_REPLACEMENTS.items():
        # Case-insensitive replacement while preserving original case
        import re
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        result = pattern.sub(phonetic, result)
    
    return result


def generate_voiceover(text: str, voice_id: str = None, mood: str = "documentary") -> str:
    """
    Generate documentary-style voiceover audio using AWS Polly
    Applies phonetic spelling for Turkish/foreign names
    
    Args:
        text: The text to convert to speech
        voice_id: Optional specific voice ID, random if not provided
        mood: Script mood for voice selection (documentary, epic, nostalgic, dramatic)
        
    Returns:
        Path to the generated audio file
    """
    # Select voice based on mood
    if voice_id is None:
        voices = VOICE_BY_MOOD.get(mood, DEFAULT_VOICES)
        voice = random.choice(voices)
    else:
        voice = {"id": voice_id, "engine": "neural", "rate": "95%", "pitch": "-5%"}
    
    # Apply phonetic spelling for better pronunciation of foreign names
    processed_text = apply_phonetic_spelling(text)
    
    # Check if any replacements were made
    if processed_text != text:
        print(f"🗣️ Phonetic spelling applied for better pronunciation")
    
    # Add natural pauses for documentary pacing
    # Epic mood gets longer, more dramatic pauses
    if mood == "epic":
        processed_text = processed_text.replace("...", '<break time="800ms"/>')
        processed_text = processed_text.replace(".", '.<break time="500ms"/>')
        processed_text = processed_text.replace("?", '?<break time="600ms"/>')
        processed_text = processed_text.replace("—", '<break time="300ms"/>—<break time="300ms"/>')
    else:
        processed_text = processed_text.replace("...", '<break time="600ms"/>')
        processed_text = processed_text.replace(".", '.<break time="350ms"/>')
        processed_text = processed_text.replace("?", '?<break time="400ms"/>')
        processed_text = processed_text.replace("—", '<break time="200ms"/>—<break time="200ms"/>')
    
    # Add SSML for documentary narration style
    ssml_text = f"""
    <speak>
        <prosody rate="{voice.get('rate', '95%')}" pitch="{voice.get('pitch', '-5%')}" volume="medium">
            {processed_text}
        </prosody>
    </speak>
    """
    
    try:
        # Try neural voice first (higher quality)
        response = polly.synthesize_speech(
            Text=ssml_text,
            TextType='ssml',
            OutputFormat='mp3',
            VoiceId=voice["id"],
            Engine=voice["engine"]
        )
        print(f"🎙️ Documentary voice: {voice['id']} (mood: {mood}, rate: {voice.get('rate')})")
    except Exception as e:
        # Fallback to standard voice
        print(f"Neural voice failed, falling back to standard: {e}")
        response = polly.synthesize_speech(
            Text=text,
            TextType='text',
            OutputFormat='mp3',
            VoiceId='Matthew',
            Engine='standard'
        )
    
    # Save to temp file with unique name
    import uuid
    audio_path = os.path.join(tempfile.gettempdir(), f"voiceover_{uuid.uuid4().hex[:8]}.mp3")
    
    with open(audio_path, 'wb') as f:
        f.write(response['AudioStream'].read())
    
    print(f"✅ Generated documentary voiceover: {audio_path}")
    
    return audio_path


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration using ffprobe"""
    import subprocess
    
    # Check for Lambda layer ffprobe
    ffprobe_path = "/opt/bin/ffprobe" if os.path.exists("/opt/bin/ffprobe") else "ffprobe"
    
    cmd = [
        ffprobe_path, '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        audio_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except:
        return 15.0  # Default duration for history shorts


if __name__ == "__main__":
    # Test locally
    test_text = "He conquered Constantinople, but he couldn't sleep without his cat. History remembers the crown, not the breakfast."
    audio_path = generate_voiceover(test_text, mood="documentary")
    print(f"Audio saved to: {audio_path}")
    duration = get_audio_duration(audio_path)
    print(f"Duration: {duration:.2f} seconds")
