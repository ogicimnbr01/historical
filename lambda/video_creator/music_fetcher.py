"""
Historical Music Fetcher for YouTube Shorts
Fetches royalty-free music from S3 and applies smart cutting
Music files are pre-uploaded to S3 bucket (Pixabay AI music)
"""

import os
import subprocess
import tempfile
import boto3  # pyre-ignore[21]
import random
from typing import Optional, Dict, List


def get_ffmpeg_path() -> str:
    """Get FFmpeg binary path"""
    if os.path.exists("/opt/bin/ffmpeg"):
        return "/opt/bin/ffmpeg"
    return "ffmpeg"


# S3 music configuration
MUSIC_BUCKET_PREFIX = "music/loops/"

# Mood to music category mapping
MOOD_TO_CATEGORY = {
    "epic": ["epic", "cinematic", "dramatic"],
    "war": ["epic", "war", "dramatic"],
    "battle": ["epic", "war"],
    "nostalgic": ["emotional", "piano", "sad"],
    "documentary": ["documentary", "ambient", "emotional"],
    "dramatic": ["dramatic", "epic", "emotional"],
    "ottoman": ["oriental", "arabian", "epic"],
    "medieval": ["medieval", "celtic", "epic"],
    "ancient": ["epic", "documentary"],
}

# Era to music category mapping
ERA_TO_CATEGORY = {
    "ancient": ["epic", "documentary"],
    "medieval": ["medieval", "epic", "dramatic"],
    "ottoman": ["oriental", "epic", "dramatic"],
    "renaissance": ["documentary", "emotional"],
    "19th_century": ["emotional", "documentary"],
    "early_20th": ["emotional", "documentary", "dramatic"],
    "ww1": ["epic", "war", "dramatic"],
    "ww2": ["epic", "war", "dramatic"],
}


def list_available_music(bucket: str, region: str = "us-east-1") -> Dict[str, List[str]]:
    """
    List all available music files from S3 organized by category
    Returns: {"epic": ["epic_1.mp3", "epic_2.mp3"], ...}
    """
    s3 = boto3.client('s3', region_name=region)
    music_by_category = {}
    
    try:
        continuation_token = None
        while True:
            list_kwargs = {
                "Bucket": bucket,
                "Prefix": MUSIC_BUCKET_PREFIX,
            }
            if continuation_token:
                list_kwargs["ContinuationToken"] = continuation_token  # pyre-ignore[26]
            
            response = s3.list_objects_v2(**list_kwargs)
            
            for obj in response.get('Contents', []):
                key = obj['Key']
                filename = os.path.basename(key)
                
                # Skip if not a music file
                if not filename.lower().endswith(('.mp3', '.m4a', '.wav', '.aac')):
                    continue
                
                # Extract category from filename (e.g., "epic_1.mp3" -> "epic")
                raw_category = filename.split('_')[0].lower()
                
                # Normalize category names to match our internal categories
                category_mapping = {
                    "emotional-piano": "emotional",
                    "cinematic": "epic",  # Map cinematic to epic
                    "oriental": "oriental",
                    "medieval": "medieval",
                    "documentary": "documentary",
                }
                category = category_mapping.get(raw_category, raw_category)
                
                if category not in music_by_category:
                    music_by_category[category] = []
                music_by_category[category].append(key)  # pyre-ignore[16]
            
            # Check if there are more pages
            if response.get('IsTruncated'):
                continuation_token = response.get('NextContinuationToken')
            else:
                break
        
        print(f"🎵 Found music categories: {list(music_by_category.keys())}")
        return music_by_category  # pyre-ignore[7]
        
    except Exception as e:
        print(f"⚠️ Could not list music from S3: {e}")
        return {}


def download_music(bucket: str, s3_key: str, region: str = "us-east-1") -> Optional[str]:
    """Download music file from S3 to temp directory"""
    s3 = boto3.client('s3', region_name=region)
    
    filename = os.path.basename(s3_key)
    local_path = os.path.join(tempfile.gettempdir(), f"music_{filename}")
    
    try:
        s3.download_file(bucket, s3_key, local_path)
        print(f"🎵 Downloaded music: {s3_key}")
        return local_path
    except Exception as e:
        print(f"❌ Could not download music: {e}")
        return None


def select_music_for_mood(music_by_category: Dict[str, List[str]], 
                          mood: Optional[str] = None, era: Optional[str] = None,
                          direct_category: Optional[str] = None) -> Optional[str]:
    """
    Select appropriate music based on mood/era or direct category
    Returns S3 key of selected music
    """
    # If direct category is specified (from story_music_matcher), use it first
    if direct_category and direct_category in music_by_category:
        selected = random.choice(music_by_category[direct_category])
        print(f"🎵 Selected music: {selected} (category: {direct_category})")
        return selected
    
    # Determine preferred categories from mood/era
    preferred_categories = []
    
    if mood and mood in MOOD_TO_CATEGORY:
        preferred_categories.extend(MOOD_TO_CATEGORY[mood])
    
    if era and era in ERA_TO_CATEGORY:
        preferred_categories.extend(ERA_TO_CATEGORY[era])
    
    # Remove duplicates while preserving order
    preferred_categories = list(dict.fromkeys(preferred_categories))
    
    # If no preferences, use epic/documentary as default
    if not preferred_categories:
        preferred_categories = ["epic", "documentary", "emotional"]
    
    # Find first available category
    for category in preferred_categories:
        if category in music_by_category and music_by_category[category]:
            selected = random.choice(music_by_category[category])
            print(f"🎵 Selected music: {selected} (category: {category})")
            return selected
    
    # Fallback: any available music
    all_music = []
    for music_list in music_by_category.values():
        all_music.extend(music_list)
    
    if all_music:
        selected = random.choice(all_music)
        print(f"🎵 Fallback music selection: {selected}")
        return selected
    
    return None


def smart_cut_music(input_path: str, target_duration: float) -> Optional[str]:
    """Apply smart cutting to music file"""
    try:
        from smart_music_cutter import smart_cut_music as do_smart_cut  # pyre-ignore[21]
        return do_smart_cut(input_path, target_duration)
    except ImportError:
        # Fallback: simple cut if smart_music_cutter not available
        return simple_cut_music(input_path, target_duration)


def simple_cut_music(input_path: str, target_duration: float) -> Optional[str]:
    """Simple fallback: cut from random position with fade"""
    try:
        # Get total duration
        cmd = [
            get_ffmpeg_path().replace('ffmpeg', 'ffprobe'),
            '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0',
            input_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        total_duration = float(result.stdout.strip()) if result.returncode == 0 else 60.0
        
        # Choose random start (skip first 10 seconds)
        max_start = max(0, total_duration - target_duration - 5)  # pyre-ignore[6]
        start = random.uniform(10.0, min(30.0, max_start)) if max_start > 10 else 0
        
        # Cut with fade
        output_path = os.path.join(tempfile.gettempdir(), "cut_music.m4a")
        
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-ss', str(start),
            '-t', str(target_duration),
            '-i', input_path,
            '-af', f'afade=t=in:st=0:d=1,afade=t=out:st={target_duration-2}:d=2',
            '-c:a', 'aac',
            '-b:a', '128k',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(output_path):
            return output_path
        
        return None
        
    except Exception as e:
        print(f"❌ Simple cut failed: {e}")
        return None


def generate_historical_music(duration: float = 30.0, music_style: Optional[str] = None,
                             mood: Optional[str] = None, era: Optional[str] = None,
                             region_name: Optional[str] = None) -> Optional[Dict]:
    """
    Main function: Get royalty-free music from S3 and apply smart cutting
    
    Args:
        duration: Target duration in seconds
        music_style: Specific style (epic, emotional, etc.)
        mood: Script mood for auto-selection
        era: Historical era for auto-selection
        region_name: AWS region
    
    Returns:
        Dict with 'path' to cut music file and 'metadata'
    """
    from copyright_safety import get_copyright_tracker  # pyre-ignore[21]
    
    # Get bucket name from environment
    bucket = os.environ.get('S3_BUCKET_NAME', '')
    region = region_name or os.environ.get('AWS_REGION', 'us-east-1')
    
    if not bucket:
        print("⚠️ S3_BUCKET_NAME not set, falling back to synthesis")
        return generate_synthesis_fallback(duration)
    
    # List available music
    music_by_category = list_available_music(bucket, region)
    
    if not music_by_category:
        print("⚠️ No music found in S3, falling back to synthesis")
        return generate_synthesis_fallback(duration)
    
    # Select appropriate music - use music_style as direct category from story_music_matcher
    selected_key = select_music_for_mood(
        music_by_category,
        mood=mood,
        era=era,
        direct_category=music_style  # This comes from story_music_matcher analysis
    )
    
    if not selected_key:
        print("⚠️ Could not select music, falling back to synthesis")
        return generate_synthesis_fallback(duration)
    
    # Download music
    local_path = download_music(bucket, selected_key, region)
    
    if not local_path:
        print("⚠️ Could not download music, falling back to synthesis")
        return generate_synthesis_fallback(duration)
    
    # Apply smart cutting
    cut_path = smart_cut_music(local_path, duration)
    
    if not cut_path:
        print("⚠️ Could not cut music, using original with simple cut")
        cut_path = simple_cut_music(local_path, duration)
    
    if cut_path and os.path.exists(cut_path):
        # Track in copyright system
        tracker = get_copyright_tracker()
        tracker.add_music(
            source="pixabay_royalty_free",
            music_id=os.path.basename(selected_key),
            title=f"Pixabay Music - {os.path.basename(selected_key)}",
            artist="Pixabay AI",
            license_type="Pixabay License - Royalty Free"
        )
        
        file_size = os.path.getsize(cut_path)
        print(f"✅ Music ready: {cut_path} ({file_size} bytes)")
        
        return {
            "path": cut_path,
            "metadata": {
                "source": "pixabay_s3",
                "original_file": os.path.basename(selected_key),
                "license": "Pixabay License - Royalty Free, Commercial Use OK",
                "safe_for_youtube": True
            }
        }
    
    return generate_synthesis_fallback(duration)


def generate_synthesis_fallback(duration: float) -> Optional[Dict]:
    """Fallback: Generate simple synthetic music if S3 music not available"""
    from copyright_safety import get_copyright_tracker  # pyre-ignore[21]
    import uuid
    
    unique_id = uuid.uuid4().hex[:8]  # pyre-ignore[16]
    output_path = os.path.join(tempfile.gettempdir(), f"synth_music_{unique_id}.m4a")
    
    try:
        # Simple melodic synthesis
        filter_complex = (
            f"aevalsrc='0.2*sin(2*PI*220*t)+0.15*sin(2*PI*330*t)+0.1*sin(2*PI*440*t)*sin(2*PI*2*t)'"
            f":s=44100:d={duration}[raw];"
            f"[raw]tremolo=f=3:d=0.3,lowpass=f=2000,"
            f"afade=t=in:st=0:d=1.5,afade=t=out:st={duration-2}:d=2,"
            f"volume=2.5[final]"
        )
        
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-f', 'lavfi',
            '-i', f'anullsrc=r=44100:cl=stereo:d={duration}',
            '-filter_complex', filter_complex,
            '-map', '[final]',
            '-c:a', 'aac',
            '-b:a', '128k',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and os.path.exists(output_path):
            tracker = get_copyright_tracker()
            tracker.add_music(
                source="self_generated",
                music_id=unique_id,
                title="Synthesized Background",
                artist="System Generated",
                license_type="Original Content"
            )
            
            print(f"✅ Fallback synthesis music: {output_path}")
            return {
                "path": output_path,
                "metadata": {
                    "source": "synthesis_fallback",
                    "license": "Original Content - No Copyright",
                    "safe_for_youtube": True
                }
            }
    except Exception as e:
        print(f"❌ Synthesis fallback failed: {e}")
    
    return None


# Backward compatible functions
def generate_ambient_music(duration: float = 30.0) -> Optional[Dict]:
    return generate_historical_music(duration=duration, mood="documentary")

def fetch_background_music(mood: str = "calm", duration_hint: float = 30.0, api_key: Optional[str] = None) -> Optional[Dict]:
    return generate_historical_music(duration=duration_hint, mood=mood)


if __name__ == "__main__":
    print("Testing Music Fetcher...")
    # Test requires S3 bucket with music files
    result = generate_historical_music(15.0, mood="epic")
    if result:
        print(f"Result: {result}")
    else:
        print("No music generated")
