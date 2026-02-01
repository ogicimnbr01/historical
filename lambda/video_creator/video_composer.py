"""
Video Composer using FFmpeg for History YouTube Shorts
Combines AI-generated historical images, voiceover, and period music
Applies old film effects for authentic historical feel
"""

import os
import subprocess
import tempfile
from typing import List, Optional


# FFmpeg binary path in Lambda Layer
FFMPEG_PATH = "/opt/bin/ffmpeg"

# Video settings for YouTube Shorts
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
FPS = 30

# Audio mixing settings - Documentary style: voice clear, music subtle
MUSIC_VOLUME = 0.30  # Background music volume (30% - atmospheric but not overpowering)
VOICE_VOLUME = 1.0   # Voiceover volume (100% - clear narration)


def compose_video(
    video_paths: List[str],
    audio_path: str,
    title: str,
    subtitle_text: str,
    music_path: Optional[str] = None,
    era: str = None
) -> str:
    """
    Compose final video from historical image clips, audio, and music
    Applies old film effects for authentic feel
    
    Args:
        video_paths: List of video clip file paths (AI-generated historical images)
        audio_path: Path to voiceover audio file
        title: Video title for overlay
        subtitle_text: Narration text for subtitles
        music_path: Optional path to background music file
        era: Historical era for effect tuning
        
    Returns:
        Path to the final composed video
    """
    from tts import get_audio_duration
    
    # Get audio duration to determine video length
    total_duration = get_audio_duration(audio_path)
    
    # If no videos, create colored background fallback
    if not video_paths:
        print("No video clips available, creating fallback...")
        video_paths = create_fallback_clips(4, total_duration)
    
    if not video_paths:
        raise RuntimeError("Could not create any video clips")
    
    # Calculate clip duration based on total audio duration
    clip_duration = total_duration / len(video_paths)
    print(f"📊 Video duration: {total_duration}s, {len(video_paths)} clips, {clip_duration:.2f}s each")
    
    output_path = os.path.join(tempfile.gettempdir(), "final_video.mp4")
    
    # Build FFmpeg filter complex
    filter_parts = []
    inputs = []
    
    # Add video inputs
    for i, video_path in enumerate(video_paths):
        inputs.extend(['-i', video_path])
    
    # Add voiceover audio input
    inputs.extend(['-i', audio_path])
    voice_index = len(video_paths)
    
    # Add background music input if provided
    music_index = None
    if music_path and os.path.exists(music_path):
        inputs.extend(['-i', music_path])
        music_index = voice_index + 1
        print(f"🎵 Adding period background music: {music_path}")
    
    # Build filter for each video clip
    # HISTORY AESTHETIC: Old film effects already applied in stock_fetcher
    # Here we just ensure smooth transitions and proper timing
    scaled_clips = []
    
    for i in range(len(video_paths)):
        # Scale, ensure proper format, trim to clip duration
        # Slight speed adjustment for cinematic feel
        filter_parts.append(
            f"[{i}:v]scale={OUTPUT_WIDTH}:{OUTPUT_HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={OUTPUT_WIDTH}:{OUTPUT_HEIGHT},"
            f"setsar=1,fps={FPS},"
            f"setpts=1.02*PTS,"  # Tiny slowdown for weight
            f"trim=0:{clip_duration},setpts=PTS-STARTPTS[v{i}]"
        )
        scaled_clips.append(f"[v{i}]")
    
    # Concatenate all clips with crossfade transitions
    # For 4 clips, we add subtle crossfades
    if len(video_paths) > 1:
        # Simple concat for now (crossfade can cause sync issues)
        concat_input = ''.join(scaled_clips)
        filter_parts.append(f"{concat_input}concat=n={len(video_paths)}:v=1:a=0[vconcat]")
    else:
        filter_parts.append(f"[v0]null[vconcat]")
    
    # Apply era-appropriate visual effects
    # Ancient/Medieval: Oil painting look (no grain - cameras didn't exist)
    # 19th century onwards: Film grain appropriate for era
    
    is_painting_era = era in ['ancient', 'medieval', 'ottoman', 'renaissance', '18th_century']
    is_photo_era = era in ['19th_century', 'early_20th', 'ww1', 'ww2', 'modern']
    
    if is_painting_era:
        # Oil painting aesthetic: warm colors, soft vignette, NO grain
        # Slight color warmth + vignette for museum painting look
        filter_parts.append(
            "[vconcat]eq=saturation=1.1:contrast=1.05,"
            "colortemperature=temperature=5500,"
            "vignette=PI/4[vprocessed]"
        )
        print(f"🎨 Applying oil painting aesthetic for era: {era}")
    elif is_photo_era:
        # Photograph era: appropriate film grain + vignette
        grain_amount = 8 if era in ['ww1', 'ww2'] else 5  # More grain for war photos
        filter_parts.append(
            f"[vconcat]noise=alls={grain_amount}:allf=t,"
            f"eq=saturation=0.9,"
            f"vignette=PI/5[vprocessed]"
        )
        print(f"📷 Applying film grain aesthetic for era: {era}")
    else:
        # Default: subtle vignette only
        filter_parts.append(
            "[vconcat]vignette=PI/5[vprocessed]"
        )
    
    # Generate and apply subtitles using ASS format
    subtitle_path = None
    try:
        from subtitle_gen import create_subtitle_file
        subtitle_path = create_subtitle_file(
            title=title,
            narration_text=subtitle_text,
            total_duration=total_duration
        )
        print(f"📝 Generated subtitles: {subtitle_path}")
        
        # Apply subtitles using ASS filter
        escaped_path = subtitle_path.replace('\\', '/').replace(':', '\\:')
        filter_parts.append(f"[vprocessed]ass='{escaped_path}'[vfinal]")
        
    except Exception as e:
        print(f"⚠️ Could not generate subtitles: {e}, proceeding without them")
        filter_parts.append("[vprocessed]null[vfinal]")
    
    # Generate context-aware SFX ambient sound
    sfx_path = None
    sfx_index = None
    try:
        from sfx_generator import generate_context_sfx
        sfx_path = generate_context_sfx(subtitle_text, total_duration)
        if sfx_path and os.path.exists(sfx_path):
            inputs.extend(['-i', sfx_path])
            sfx_index = voice_index + (1 if music_index is None else 2)
            if music_index is not None:
                sfx_index = music_index + 1
            print(f"🔊 Adding ambient SFX: {sfx_path}")
    except Exception as e:
        print(f"⚠️ SFX generation skipped: {e}")
    
    # Audio mixing with DUCKING and SFX
    # Voice is loudest, music ducks under voice, SFX is subtle ambient
    if music_index is not None and sfx_index is not None:
        # Full audio mix: Voice + Music (ducked) + SFX
        filter_parts.append(
            f"[{voice_index}:a]volume={VOICE_VOLUME},asplit=2[voice][voice_sc];"
            f"[{music_index}:a]volume={MUSIC_VOLUME}[music_vol];"
            f"[music_vol]apad=whole_dur={total_duration}[music_padded];"
            f"[music_padded]atrim=0:{total_duration}[music_trimmed];"
            f"[music_trimmed][voice_sc]sidechaincompress=threshold=0.02:ratio=4:attack=300:release=1000[music_ducked];"
            f"[{sfx_index}:a]volume=0.15,atrim=0:{total_duration}[sfx_trimmed];"
            f"[voice][music_ducked][sfx_trimmed]amix=inputs=3:duration=first:dropout_transition=2[aout]"
        )
        audio_map = '[aout]'
        print(f"🔊 Audio mix: Voice + Music (ducked) + SFX ambient")
    elif music_index is not None:
        # Audio ducking: sidechaincompress makes music quieter when voice is present
        # Parameters: threshold -20dB, ratio 4:1, attack 0.3s, release 1s
        filter_parts.append(
            f"[{voice_index}:a]volume={VOICE_VOLUME},asplit=2[voice][voice_sc];"
            f"[{music_index}:a]volume={MUSIC_VOLUME}[music_vol];"
            f"[music_vol]apad=whole_dur={total_duration}[music_padded];"
            f"[music_padded]atrim=0:{total_duration}[music_trimmed];"
            f"[music_trimmed][voice_sc]sidechaincompress=threshold=0.02:ratio=4:attack=300:release=1000[music_ducked];"
            f"[voice][music_ducked]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        audio_map = '[aout]'
        print(f"🔊 Audio ducking applied - voice will be clear over music")
    elif sfx_index is not None:
        # Voice + SFX only (no music)
        filter_parts.append(
            f"[{voice_index}:a]volume={VOICE_VOLUME}[voice];"
            f"[{sfx_index}:a]volume=0.15,atrim=0:{total_duration}[sfx_trimmed];"
            f"[voice][sfx_trimmed]amix=inputs=2:duration=first:dropout_transition=2[aout]"
        )
        audio_map = '[aout]'
        print(f"🔊 Audio mix: Voice + SFX ambient")
    else:
        # No music, just use voiceover
        audio_map = f'{voice_index}:a'
    
    # Complete filter complex
    filter_complex = ';'.join(filter_parts)
    
    # FFmpeg command
    cmd = [
        get_ffmpeg_path(),
        '-y',  # Overwrite output
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '[vfinal]',
        '-map', audio_map,
        '-c:v', 'libx264',
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-shortest',
        '-t', str(total_duration + 0.5),  # Add small buffer
        output_path
    ]
    
    print(f"🎬 Running FFmpeg composition...")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180  # 3 minute timeout
    )
    
    if result.returncode != 0:
        print(f"FFmpeg stderr: {result.stderr}")
        raise RuntimeError(f"FFmpeg failed: {result.stderr}")
    
    print(f"✅ Historical video composed: {output_path}")
    
    return output_path


def get_ffmpeg_path() -> str:
    """Get FFmpeg binary path (Lambda Layer or local)"""
    if os.path.exists(FFMPEG_PATH):
        return FFMPEG_PATH
    # Fallback for local testing
    return "ffmpeg"


def escape_ffmpeg_text(text: str) -> str:
    """Escape special characters for FFmpeg drawtext"""
    text = text.replace("'", "'")
    text = text.replace("\\", "\\\\")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


def create_fallback_clips(count: int, total_duration: float) -> List[str]:
    """Create historical-themed colored background clips as fallback"""
    import subprocess
    
    video_paths = []
    clip_duration = total_duration / count
    
    # Historical, aged colors
    colors = [
        "0x1a1611",  # Dark parchment
        "0x2c2416",  # Sepia brown
        "0x14171a",  # Steel gray
        "0x1f1a14",  # Antique dark
        "0x111a14",  # Dark forest
    ]
    
    for i in range(count):
        color = colors[i % len(colors)]
        temp_path = os.path.join(tempfile.gettempdir(), f"fallback_{i}.mp4")
        
        try:
            cmd = [
                get_ffmpeg_path(),
                '-y',
                '-f', 'lavfi',
                '-i', f'color=c={color}:s={OUTPUT_WIDTH}x{OUTPUT_HEIGHT}:d={clip_duration}:r={FPS}',
                '-vf', 'vignette=PI/4',  # Historical vignette
                '-c:v', 'libx264',
                '-preset', 'ultrafast',
                '-pix_fmt', 'yuv420p',
                temp_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0 and os.path.exists(temp_path):
                video_paths.append(temp_path)
                print(f"Created fallback clip: {temp_path}")
            else:
                print(f"Fallback clip creation failed: {result.stderr}")
        except Exception as e:
            print(f"Error creating fallback clip: {e}")
    
    return video_paths


if __name__ == "__main__":
    # Test locally
    print("Video composer module loaded - History Shorts edition")
