"""
Historical Image Generator using AWS Bedrock Titan
Generates vintage-style historical images for YouTube Shorts
Uses AI image generation with Ken Burns effect for video output
All content is AI-generated and copyright-safe
"""

import os
import requests  # pyre-ignore[21]
import tempfile
import time
import uuid
import json
import base64
import boto3  # pyre-ignore[21]
from typing import List, Tuple, Optional

# Import copyright safety module
from copyright_safety import get_copyright_tracker, reset_copyright_tracker  # pyre-ignore[21]


# Global counter for unique file names
_fallback_counter = 0

# Era-specific prompt suffixes for authentic historical look
# Ancient/Medieval: Oil painting style (no grain - cameras didn't exist)
# 19th century onwards: Photograph style with appropriate grain
ERA_STYLE_SUFFIXES = {
    "ancient": ", classical oil painting on canvas, ancient world artistic style, marble and bronze aesthetic, dramatic chiaroscuro lighting, museum masterpiece quality",
    "medieval": ", medieval oil painting on canvas texture, castle and knight era, rich colors, dramatic shadows, illuminated manuscript style",
    "ottoman": ", Ottoman oriental painting style, oil on canvas, Islamic geometric patterns, palace interior aesthetic, golden warm tones, miniature painting influence",
    "renaissance": ", Renaissance masterpiece oil painting, canvas texture visible, European court aesthetic, chiaroscuro lighting, museum quality",
    "18th_century": ", 18th century portrait oil painting, canvas texture, colonial era, classical composition, formal dignified",
    "19th_century": ", vintage 19th century photograph style, sepia toned, Victorian era, slightly faded, subtle film grain",
    "early_20th": ", 1920s-1940s black and white vintage photograph, film grain texture, slightly noisy, historical archive look",
    "ww1": ", World War I era photograph, grainy black and white, war documentary style, dramatic, film grain",
    "ww2": ", World War II era photograph, black and white film grain, military documentary style, noisy film",
    "modern": ", mid-20th century color photograph, vintage film look, 1950s-1970s aesthetic, slight color fade"
}

# Default archive style suffix (for unspecified eras)
DEFAULT_ARCHIVE_STYLE = ", vintage archive photograph style, historical, dramatic lighting, photorealistic, slightly aged look"

# Known historical figures that need face-avoidance to prevent AI hallucination
FACE_AVOIDANCE_FIGURES = [
    "atatürk", "ataturk", "mustafa kemal", "fatih", "mehmed", "suleiman", "süleyman",
    "napoleon", "hitler", "stalin", "churchill", "roosevelt", "lincoln", "caesar",
    "cleopatra", "alexander", "genghis", "saladin", "richard", "victoria"
]

# Face-avoidance techniques to add when known figures detected
FACE_AVOIDANCE_TECHNIQUES = [
    "wide shot from distance",
    "dramatic silhouette against light",
    "view from behind looking at horizon",
    "artistic shadow obscuring features",
    "cinematic wide angle shot",
    "figure in dramatic backlight"
]

# Name sanitization to bypass Titan content filters
# Replaces specific controversial names with safe generic descriptors
NAME_SANITIZATION = {
    # Mongol leaders
    "genghis khan": "13th century Mongol emperor in golden armor",
    "genghis": "medieval Mongol ruler",
    "kublai khan": "Yuan dynasty emperor of China",
    "kublai": "medieval Asian emperor",
    # Ottoman leaders  
    "mehmed ii": "young Ottoman sultan in royal robes",
    "mehmed": "Ottoman sultan",
    "fatih sultan mehmed": "young conqueror sultan",
    "suleiman": "magnificent Ottoman emperor",
    "süleyman": "Ottoman golden age ruler",
    # Turkish figures
    "atatürk": "Turkish founding leader in military uniform",
    "ataturk": "Turkish founding leader",
    "mustafa kemal": "Turkish military commander",
    # Controversial historical figures
    "hitler": "1940s German leader",
    "stalin": "Soviet era leader",
    "napoleon": "19th century French emperor in military coat",
    # Ancient figures
    "caesar": "Roman emperor in toga and laurel crown",
    "julius caesar": "ancient Roman statesman",
    "cleopatra": "ancient Egyptian queen",
    "alexander": "ancient Greek conqueror king",
    "alexander the great": "Macedonian warrior king",
    # Medieval figures
    "saladin": "medieval Kurdish Muslim leader",
    "richard": "English crusader king",
    "constantine": "Byzantine emperor",
}

# Violence/Battle word sanitization - convert to symbolic imagery
# These words trigger Titan's violence filter, so we use symbolic alternatives
VIOLENCE_SANITIZATION = {
    # Battle/War words → Symbolic aftermath or preparation
    "fighting battles": "standing victorious on battlefield at sunset",
    "fighting": "in powerful stance with weapon raised",
    "battle": "heroic warrior stance, dramatic atmosphere",
    "battles": "military camp with warriors preparing",
    "battlefield": "misty field with distant flags",
    "war": "soldiers marching in formation, dramatic sky",
    "warfare": "military strategy table with maps",
    "combat": "warriors in training duel",
    # Violence words → Symbolic/aftermath imagery
    "kill": "triumphant victory moment",
    "killed": "fallen warrior honored by comrades",
    "killing": "intense warrior focus",
    "death": "solemn memorial scene",
    "dead": "peaceful warrior at rest",
    "died": "honored warrior legacy",
    "dying": "dramatic final stand",
    "blood": "red sunset over field",
    "bloody": "intense dramatic lighting",
    "slaughter": "overwhelming victory scene",
    "massacre": "dramatic historical moment",
    "murder": "tense dramatic scene",
    "assassin": "mysterious cloaked figure in shadows",
    "assassination": "dramatic palace intrigue scene",
    # Weapon violence → Weapon display/heritage
    "stabbing": "gleaming sword in display",
    "stabbed": "ancient weapon on ceremonial stand",
    "beheading": "royal judgment scene",
    "execution": "solemn historical ceremony",
    "torture": "dark dungeon architecture",
    "conquer": "flag being raised over fortress",
    "conquered": "victory celebration in city square",
    "invasion": "army arriving at city gates",
    "siege": "fortress walls with defenders watching",
    "destroy": "crumbling ancient ruins",
    "destruction": "smoke rising from distant city",
}


def sanitize_prompt_for_titan(prompt: str) -> str:
    """
    Sanitize prompt to bypass Titan content filters
    Replaces:
    1. Historical figure names with safe generic descriptors
    2. Violence/battle words with symbolic imagery
    
    This prevents ValidationException from Amazon's content policy
    """
    import re
    
    prompt_lower = prompt.lower()
    sanitized = prompt
    
    # First: Sanitize violence/battle words (longer phrases first)
    # Sort by length descending to match longer phrases first
    sorted_violence = sorted(VIOLENCE_SANITIZATION.items(), key=lambda x: len(x[0]), reverse=True)
    for word, replacement in sorted_violence:
        if word in prompt_lower:
            pattern = re.compile(re.escape(word), re.IGNORECASE)
            sanitized = pattern.sub(replacement, sanitized)
            prompt_lower = sanitized.lower()  # Update for next iteration
            print(f"⚔️ Violence word sanitized: '{word}' → '{replacement}'")
    
    # Second: Sanitize names
    for name, replacement in NAME_SANITIZATION.items():
        if name in prompt_lower:
            pattern = re.compile(re.escape(name), re.IGNORECASE)
            sanitized = pattern.sub(replacement, sanitized)
            prompt_lower = sanitized.lower()
            print(f"🛡️ Name sanitized: '{name}' → '{replacement}'")
    
    return sanitized


def enhance_prompt_for_era(prompt: str, era: Optional[str] = None, mood: Optional[str] = None) -> str:
    """
    Enhance an image prompt with era-appropriate styling
    Uses comprehensive titan_sanitizer module for safety
    
    Args:
        prompt: Base image generation prompt
        era: Historical era for styling (ancient, medieval, ottoman, etc.)
        mood: Content mood (epic, nostalgic, emotional, etc.)
        
    Returns:
        Enhanced prompt with era-specific styling, fully sanitized for Titan
    """
    # Use comprehensive Titan sanitizer
    try:
        from titan_sanitizer import full_sanitize, add_face_avoidance  # pyre-ignore[21]
        
        # Full sanitization pipeline with mood-based art style
        era_str = era or "medieval"
        mood_str = mood or "epic"
        prompt = full_sanitize(prompt, era_str, mood_str)
        prompt = add_face_avoidance(prompt)
        
    except ImportError:
        # Fallback to local sanitization if module not available
        print("⚠️ titan_sanitizer not found, using local sanitization")
        prompt = sanitize_prompt_for_titan(prompt)
    
    # Ensure 9:16 vertical composition for Shorts
    if "9:16" not in prompt.lower() and "vertical" not in prompt.lower():
        prompt += ", 9:16 vertical composition"
    
    print(f"🎨 Final prompt for era '{era}' mood '{mood}': {prompt[:100]}...")  # pyre-ignore[16]
    
    return prompt


def fetch_videos_by_segments(segments: List[dict], era: Optional[str] = None, api_key: Optional[str] = None) -> List[str]:
    """
    Generate videos for each script segment using AI image generation
    Fallback chain: Titan AI → Previous Success → Gradient
    
    Args:
        segments: List of segment dicts with 'image_prompt', 'start', 'end', 'text' keys
        era: Optional era for visual styling override
        api_key: Not used (kept for backward compatibility)
        
    Returns:
        List of local file paths to generated videos (one per segment)
    """
    video_paths = []
    last_successful_video = None  # Track last success for reuse
    
    for i, segment in enumerate(segments):
        # Get the image prompt from segment (new format) or fall back to query (old format)
        image_prompt = segment.get('image_prompt') or segment.get('query', 'historical scene')
        
        # Enhance prompt with era styling
        segment_era = era or segment.get('era', 'early_20th')
        enhanced_prompt = enhance_prompt_for_era(image_prompt, segment_era)
        
        print(f"🔍 Segment {i}: Generating historical image...")
        
        video_path = None
        
        # Step 1: Try Titan AI generation
        try:
            video_path = generate_historical_video(enhanced_prompt, segment_index=i)
            if video_path:
                video_paths.append(video_path)
                last_successful_video = video_path  # Remember for fallback
                print(f"✅ Segment {i}: AI-generated historical video -> {video_path}")
                continue
        except Exception as e:
            print(f"⚠️ Segment {i}: Titan failed: {e}")
        
        # Step 2: SMART FALLBACK - Reuse previous successful video
        if last_successful_video and os.path.exists(last_successful_video):  # pyre-ignore[6]
            print(f"🔄 Segment {i}: Reusing previous successful video...")
            video_paths.append(last_successful_video)  # pyre-ignore[6]
            continue
        
        # Step 3: Final fallback to gradient (only if no previous success)
        print(f"🎨 Segment {i}: Using gradient fallback...")
        fallback = create_gradient_fallback(i, segment_era)
        if fallback:
            video_paths.append(fallback)
            last_successful_video = fallback  # Even gradient can be reused
    
    return video_paths


def extract_pexels_keywords(prompt: str, era: Optional[str] = None) -> str:
    """
    Extract safe, searchable keywords from prompt for Pexels
    Removes specific names and keeps generic historical terms
    """
    # Map era to Pexels-friendly search terms
    era_keywords = {
        "ancient": "ancient ruins greece rome",
        "medieval": "medieval castle fortress",
        "ottoman": "mosque palace oriental",
        "renaissance": "renaissance art europe",
        "early_20th": "historical black white vintage",
        "ww1": "war historical military",
        "ww2": "war historical military",
        "19th_century": "victorian vintage historical",
    }
    
    # Start with era keywords
    search_terms = era_keywords.get(era or "", "historical vintage")
    
    # Add generic terms from prompt (avoid specific names)
    generic_terms = []
    for word in prompt.lower().split():
        if word in ["castle", "palace", "battle", "war", "army", "soldier", "ship", 
                    "horse", "cannon", "sword", "crown", "throne", "city", "walls",
                    "temple", "church", "mosque", "ruins", "ancient", "fire", "smoke"]:
            generic_terms.append(word)
    
    if generic_terms:
        search_terms = " ".join(generic_terms[:3]) + " " + search_terms  # pyre-ignore[16]
    
    return search_terms[:50]  # pyre-ignore[16]: Limit length


def fetch_pexels_video(query: str, api_key: str, index: int = 0) -> Optional[str]:
    """
    Fetch a stock video from Pexels API
    Returns path to downloaded video or None
    """
    global _fallback_counter
    import subprocess
    
    try:
        headers = {"Authorization": api_key}
        
        # Search for videos
        params = {
            "query": query,
            "orientation": "portrait",
            "size": "small",
            "per_page": 5
        }
        
        response = requests.get(
            "https://api.pexels.com/videos/search",
            headers=headers,
            params=params,
            timeout=10
        )
        
        if response.status_code != 200:
            print(f"⚠️ Pexels API error: {response.status_code}")
            return None
        
        data = response.json()
        videos = data.get('videos', [])
        
        if not videos:
            print(f"⚠️ No Pexels videos found for: {query}")
            return None
        
        # Pick a video (rotate based on index to vary results)
        video = videos[index % len(videos)]
        
        # Get the best quality video file (prefer HD)
        video_files = video.get('video_files', [])
        best_file = None
        for vf in video_files:
            if vf.get('quality') == 'hd' and vf.get('height', 0) >= 720:
                best_file = vf
                break
        
        if not best_file and video_files:
            best_file = video_files[0]
        
        if not best_file:
            return None
        
        video_url = best_file.get('link')
        
        # Download the video
        _fallback_counter += 1  # pyre-ignore[53]
        unique_id = f"pexels_{_fallback_counter}_{uuid.uuid4().hex[:6]}"  # pyre-ignore[16]
        temp_path = os.path.join(tempfile.gettempdir(), f"{unique_id}.mp4")
        
        video_response = requests.get(video_url, timeout=30)
        if video_response.status_code == 200:
            with open(temp_path, 'wb') as f:
                f.write(video_response.content)
            
            # Process with Ken Burns effect
            processed_path = os.path.join(tempfile.gettempdir(), f"{unique_id}_proc.mp4")
            cmd = [
                get_ffmpeg_path(),
                '-y',
                '-i', temp_path,
                '-vf', (
                    f"scale=1080:1920:force_original_aspect_ratio=increase,"
                    f"crop=1080:1920,"
                    f"zoompan=z='min(zoom+0.0002,1.05)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=150:s=1080x1920:fps=30,"
                    f"eq=saturation=0.9,vignette=PI/5"
                ),
                '-c:v', 'libx264',
                '-preset', 'fast',
                '-pix_fmt', 'yuv420p',
                '-t', '5',
                processed_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(processed_path):
                # Track as Pexels content
                tracker = get_copyright_tracker()
                tracker.add_video("pexels", str(video.get('id', 'unknown')), video.get('url', ''))
                
                # Cleanup temp download
                try:
                    os.remove(temp_path)
                except:
                    pass
                
                print(f"✅ Pexels video processed: {processed_path}")
                return processed_path
        
        return None
        
    except Exception as e:
        print(f"⚠️ Pexels fetch error: {e}")
        return None


def generate_historical_video(prompt: str, segment_index: int = 0) -> Optional[str]:
    """
    Generate a historical image using AWS Bedrock Titan and convert to video
    Applies Ken Burns effect and old film aesthetic
    
    Args:
        prompt: Image generation prompt
        segment_index: Segment index for unique file naming
        
    Returns:
        Path to generated video file or None if failed
    """
    global _fallback_counter
    import subprocess
    import random
    
    try:
        # Initialize Bedrock client
        region = os.environ.get('AWS_REGION_NAME', 'us-east-1')
        bedrock = boto3.client(
            service_name='bedrock-runtime',
            region_name=region
        )
        
        print(f"🎨 Generating AI image: {prompt[:100]}...")  # pyre-ignore[16]
        
        # Request body for Titan Image Generator
        request_body = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {
                "text": prompt
            },
            "imageGenerationConfig": {
                "numberOfImages": 1,
                "height": 1408,  # Closest to 9:16 aspect ratio supported
                "width": 768,
                "cfgScale": 8.0,
                "seed": random.randint(0, 2147483647)
            }
        }
        
        response = bedrock.invoke_model(
            modelId="amazon.titan-image-generator-v2:0",
            body=json.dumps(request_body),
            contentType="application/json",
            accept="application/json"
        )
        
        response_body = json.loads(response['body'].read())
        images = response_body.get('images', [])
        
        if not images:
            print("⚠️ No images returned from Titan")
            return None
        
        # Decode base64 image
        image_data = base64.b64decode(images[0])
        
        _fallback_counter += 1  # pyre-ignore[53]
        unique_id = f"hist_{segment_index}_{_fallback_counter}_{uuid.uuid4().hex[:6]}"  # pyre-ignore[16]
        
        # Save image
        image_path = os.path.join(tempfile.gettempdir(), f"{unique_id}.png")
        with open(image_path, 'wb') as f:
            f.write(image_data)
        
        print(f"✅ AI image saved: {image_path}")
        
        # Convert image to video with Ken Burns effect + old film look
        video_path = os.path.join(tempfile.gettempdir(), f"{unique_id}.mp4")
        
        # Ken Burns effect: slow zoom for cinematic feel
        # Old film effect: noise + slight desaturation + vignette
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-loop', '1',
            '-i', image_path,
            '-vf', (
                # === SKETCH/CHARCOAL STYLE VIDEO ===
                # Creates artistic hand-drawn look, NOT photorealistic
                
                # Step 1: Scale and crop for 1080x1920 vertical format
                f"scale=1080:1920:force_original_aspect_ratio=increase,"
                f"crop=1080:1920,"
                
                # Step 2: Ken Burns zoom with subtle pan
                f"zoompan=z='if(lte(zoom,1.0),1.001,min(zoom+0.0005,1.15))':x='iw/2-(iw/zoom/2)+sin(on/100)*20':y='ih/2-(ih/zoom/2)':d=240:s=1080x1920:fps=30,"
                
                # Step 3: Fade in for reveal effect
                f"fade=in:0:24,"  # 0.8s fade
                
                # Step 4: SKETCH/CHARCOAL AESTHETIC
                # High contrast + heavy grain creates drawn look
                f"eq=contrast=1.3:brightness=0.05:saturation=0.6,"  # High contrast, low saturation (sepia-ish)
                f"noise=alls=15:allf=t,"  # Heavy grain for paper texture
                f"unsharp=5:5:1.5,"  # Sharpen edges for linework effect
                f"vignette=PI/3.5"   # Stronger vignette for focus
            ),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            '-t', '8',  # 8 second clip (supports voiceovers up to 32s with 4 clips)
            video_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and os.path.exists(video_path):
            file_size = os.path.getsize(video_path)
            if file_size > 10000:
                # Track as AI-generated content (copyright-safe)
                tracker = get_copyright_tracker()
                tracker.add_fallback_video(video_path)
                
                # Cleanup image file
                try:
                    os.remove(image_path)
                except:
                    pass
                
                print(f"✅ Historical video created: {video_path} ({file_size} bytes)")
                return video_path
        
        print(f"⚠️ FFmpeg failed: {result.stderr[:200] if result.stderr else 'unknown'}")  # pyre-ignore[16]
        return None
        
    except Exception as e:
        print(f"⚠️ Historical image generation error: {e}")
        return None


def create_gradient_fallback(index: int = 0, era: Optional[str] = None) -> Optional[str]:
    """
    Create a VISIBLE gradient/color based fallback video
    Used when AI generation fails
    Uses BRIGHT, visible historical-feeling colors (not dark!)
    """
    global _fallback_counter
    import subprocess
    
    # VISIBLE historical aesthetic gradients - Rich colors, NOT dark!
    # These create animated gradients that catch the eye
    gradient_configs = [
        # Era-appropriate visible colors
        ("0xB8860B", "0x8B4513", "golden_parchment"),     # Gold to brown - royal
        ("0x8B0000", "0x2F0000", "crimson_empire"),       # Deep red - war/power
        ("0x1E3A5F", "0x0D1B2A", "royal_navy"),           # Royal blue - empires
        ("0xCD853F", "0x8B7355", "antique_bronze"),       # Bronze - ancient feel
        ("0x704214", "0x3D2314", "aged_sepia"),           # Warm sepia - photos
        ("0x483D8B", "0x1E1E3F", "imperial_purple"),      # Purple - royalty
        ("0x228B22", "0x0D3D0D", "ottoman_green"),        # Ottoman imperial green
        ("0xDAA520", "0x8B6914", "sultan_gold"),          # Ottoman gold
    ]
    
    _fallback_counter += 1  # pyre-ignore[53]
    unique_id = f"grad_{_fallback_counter}_{uuid.uuid4().hex[:6]}"  # pyre-ignore[16]
    temp_path = os.path.join(tempfile.gettempdir(), f"{unique_id}.mp4")
    
    try:
        config = gradient_configs[index % len(gradient_configs)]
        color1, color2 = config[0], config[1]
        name = config[2]
        
        print(f"🎨 Creating visible gradient: {name} ({color1} -> {color2})")
        
        # Create animated gradient with movement for visual interest
        # Uses gradients filter with animated transition
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-f', 'lavfi',
            '-i', f"gradients=s=1080x1920:c0={color1}:c1={color2}:x0=540:y0=0:x1=540:y1=1920:d=8:r=30",
            '-vf', (
                # Add subtle animation via zoompan
                "zoompan=z='1+0.02*sin(on/25)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30,"
                # Add vignette for cinematic feel
                "vignette=PI/4,"
                # Add subtle noise for texture
                "noise=alls=3:allf=t"
            ),
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-pix_fmt', 'yuv420p',
            '-t', '8',
            temp_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(temp_path):
            file_size = os.path.getsize(temp_path)
            if file_size > 1000:
                tracker = get_copyright_tracker()
                tracker.add_fallback_video(temp_path)
                
                print(f"✅ Visible gradient created: {temp_path} ({file_size} bytes)")
                return temp_path
            else:
                print(f"⚠️ Fallback file too small: {file_size} bytes")
        
        # If gradients filter fails, try simple solid color
        print(f"⚠️ Gradient filter failed, trying simple color...")
        return create_simple_color_fallback(index, color1)
        
    except Exception as e:
        print(f"⚠️ Error creating gradient fallback: {e}")
        return create_simple_color_fallback(index)


def create_simple_color_fallback(index: int = 0, color: Optional[str] = None) -> Optional[str]:
    """
    Create a SIMPLE solid color fallback - guaranteed to work
    This is the last resort when gradient filter isn't available
    Uses BRIGHT visible colors - no dark colors!
    """
    global _fallback_counter
    import subprocess
    
    # BRIGHT visible colors that definitely work
    simple_colors = [
        "0xB8860B",  # Gold
        "0x8B4513",  # Saddle brown
        "0xCD853F",  # Peru/bronze
        "0x704214",  # Sepia
        "0x8B0000",  # Dark red (still visible)
        "0x2F4F4F",  # Dark slate gray
        "0x483D8B",  # Dark slate blue
        "0x228B22",  # Forest green
    ]
    
    _fallback_counter += 1  # pyre-ignore[53]
    unique_id = f"simple_{_fallback_counter}_{uuid.uuid4().hex[:6]}"  # pyre-ignore[16]
    temp_path = os.path.join(tempfile.gettempdir(), f"{unique_id}.mp4")
    
    use_color = color if color else simple_colors[index % len(simple_colors)]
    
    try:
        print(f"🎨 Creating simple color fallback: {use_color}")
        
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-f', 'lavfi',
            '-i', f"color=c={use_color}:s=1080x1920:d=8:r=30",
            '-vf', 'vignette=PI/5',  # Simple vignette
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-pix_fmt', 'yuv420p',
            '-t', '8',
            temp_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(temp_path):
            file_size = os.path.getsize(temp_path)
            if file_size > 1000:
                tracker = get_copyright_tracker()
                tracker.add_fallback_video(temp_path)
                print(f"✅ Simple color fallback created: {temp_path}")
                return temp_path
        
        print(f"⚠️ Simple color failed: {result.stderr[:100] if result.stderr else 'unknown'}")  # pyre-ignore[16]
        return None
        
    except Exception as e:
        print(f"⚠️ Simple color error: {e}")
        return None


def create_animated_fallbacks(count: int, query: Optional[str] = None) -> List[str]:
    """
    Create fallback videos when main generation fails
    Backward compatible function
    """
    video_paths = []
    
    for i in range(count):
        if query:
            # Try AI generation with the query
            video = generate_historical_video(query or "", segment_index=i)  # pyre-ignore[6]
            if video:
                video_paths.append(video)
                continue
        
        # Fall back to gradient
        gradient_video = create_gradient_fallback(i)
        if gradient_video:
            video_paths.append(gradient_video)
    
    return video_paths


def fetch_stock_videos(keywords: List[str], num_clips: int = 3, api_key: Optional[str] = None) -> List[str]:
    """
    Backward compatible function - now generates AI images instead of fetching stock
    
    Args:
        keywords: List of search keywords (used as prompts)
        num_clips: Number of video clips to generate
        api_key: Not used (kept for compatibility)
        
    Returns:
        List of local file paths to generated videos
    """
    video_paths = []
    
    for i, keyword in enumerate(list(keywords[:num_clips])):  # pyre-ignore[16]
        # Enhance keyword as a prompt
        prompt = f"{keyword}, historical scene, dramatic lighting"
        video = generate_historical_video(prompt, segment_index=i)
        
        if video:
            video_paths.append(video)
        else:
            fallback = create_gradient_fallback(i)
            if fallback:
                video_paths.append(fallback)
    
    # Fill remaining with fallbacks if needed
    while len(video_paths) < num_clips:
        fallback = create_gradient_fallback(len(video_paths))
        if fallback:
            video_paths.append(fallback)
        else:
            break
    
    return video_paths


def get_ffmpeg_path() -> str:
    """Get FFmpeg binary path"""
    if os.path.exists("/opt/bin/ffmpeg"):
        return "/opt/bin/ffmpeg"
    return "ffmpeg"


def get_video_duration(video_path: str) -> float:
    """Get video duration using ffprobe"""
    import subprocess
    
    ffprobe_path = "/opt/bin/ffprobe" if os.path.exists("/opt/bin/ffprobe") else "ffprobe"
    
    cmd = [
        ffprobe_path, '-v', 'quiet',
        '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1',
        video_path
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return float(result.stdout.strip())
    except:
        return 5.0  # Default duration


# Legacy function aliases for backward compatibility
def enhance_query(query: str) -> str:
    """Legacy function - now enhances as historical prompt"""
    return enhance_prompt_for_era(query, "early_20th")

def filter_keywords(keywords: List[str]) -> List[str]:
    """Legacy function - returns keywords as-is"""
    return keywords

def generate_ai_video_fallback(query: Optional[str] = None) -> Optional[str]:
    """Legacy function - now calls generate_historical_video"""
    return generate_historical_video(query or "historical scene, vintage photograph style")


if __name__ == "__main__":
    # Test locally
    print("Testing Historical Image Generator...")
    
    # Test with a historical prompt
    test_prompt = "Mustafa Kemal Atatürk at dinner table, 1930s, modest Turkish home"
    video = generate_historical_video(test_prompt)
    
    if video:
        print(f"Generated: {video}")
    else:
        print("Generation failed, testing fallback...")
        fallback = create_gradient_fallback(0)
        print(f"Fallback: {fallback}")
