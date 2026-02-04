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

# Audio mixing settings - Documentary style: voice clear, music/SFX AUDIBLE
# IMPORTANT: These values were tuned after testing - don't lower them!
MUSIC_VOLUME = 0.55  # Background music volume (55% - clearly audible)
VOICE_VOLUME = 1.0   # Voiceover volume (100% - clear narration)
SFX_VOLUME = 0.40    # Sound effects volume (40% - noticeable impact)


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
    if music_path:
        print(f"🎵 DEBUG: music_path provided: {music_path}")
        if os.path.exists(music_path):
            music_size = os.path.getsize(music_path)
            print(f"🎵 DEBUG: music file exists, size: {music_size} bytes")
            if music_size > 1000:  # At least 1KB
                inputs.extend(['-i', music_path])
                music_index = voice_index + 1
                print(f"🎵 CONFIRMED: Adding background music at index {music_index}")
            else:
                print(f"⚠️ Music file too small ({music_size} bytes), skipping")
        else:
            print(f"❌ Music file NOT FOUND: {music_path}")
    else:
        print(f"ℹ️ DEBUG: No music_path provided")
    
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
        if sfx_path:
            print(f"🔊 DEBUG: SFX generated: {sfx_path}")
            if os.path.exists(sfx_path):
                sfx_size = os.path.getsize(sfx_path)
                print(f"🔊 DEBUG: SFX file exists, size: {sfx_size} bytes")
                if sfx_size > 1000:
                    inputs.extend(['-i', sfx_path])
                    # Calculate correct SFX index
                    sfx_index = voice_index + 1
                    if music_index is not None:
                        sfx_index = music_index + 1
                    print(f"🔊 CONFIRMED: Adding SFX at index {sfx_index}")
                else:
                    print(f"⚠️ SFX file too small ({sfx_size} bytes), skipping")
            else:
                print(f"❌ SFX file NOT FOUND: {sfx_path}")
        else:
            print(f"ℹ️ DEBUG: No SFX generated")
    except Exception as e:
        print(f"⚠️ SFX generation error: {e}")
    
    # === FINAL AUDIO SUMMARY ===
    print(f"📊 AUDIO SUMMARY: voice_index={voice_index}, music_index={music_index}, sfx_index={sfx_index}")
    print(f"📊 AUDIO INPUTS: {len(inputs)} total inputs")
    
    # ============================================================
    # FINAL AUDIO FIX - Using amix with weights (simplest approach)
    # Previous attempts with amerge/pan failed silently
    # ============================================================
    # AUDIO MIXING - Fade-out at end for "video ended" feeling
    # Music: -20% from previous levels (0.25→0.20, 0.30→0.24)
    # Fade-out: last 0.7 seconds
    # ============================================================
    
    fade_start = max(0, total_duration - 0.7)  # Fade starts 0.7s before end
    
    if music_index is not None and sfx_index is not None:
        # Voice + Music + SFX - all three
        # Music weight: 0.20 (was 0.25, -20%)
        filter_parts.append(
            f"[{voice_index}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[voice];"
            f"[{music_index}:a]aloop=loop=-1:size=2e+09,atrim=0:{total_duration},afade=t=out:st={fade_start}:d=0.7,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[music];"
            f"[{sfx_index}:a]aloop=loop=-1:size=2e+09,atrim=0:{total_duration},afade=t=out:st={fade_start}:d=0.7,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[sfx];"
            f"[voice][music][sfx]amix=inputs=3:duration=first:weights=1 0.20 0.25:normalize=0[aout]"
        )
        audio_map = '[aout]'
        print(f"🔊 FINAL MIX: Voice + Music(0.20) + SFX(0.25) + fade-out@{fade_start:.1f}s")
        
    elif music_index is not None:
        # Voice + Music only
        # Music weight: 0.24 (was 0.30, -20%)
        filter_parts.append(
            f"[{voice_index}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[voice];"
            f"[{music_index}:a]aloop=loop=-1:size=2e+09,atrim=0:{total_duration},afade=t=out:st={fade_start}:d=0.7,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[music];"
            f"[voice][music]amix=inputs=2:duration=first:weights=1 0.24:normalize=0[aout]"
        )
        audio_map = '[aout]'
        print(f"🔊 FINAL MIX: Voice + Music(0.24) + fade-out@{fade_start:.1f}s")
        
    elif sfx_index is not None:
        # Voice + SFX only
        filter_parts.append(
            f"[{voice_index}:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[voice];"
            f"[{sfx_index}:a]aloop=loop=-1:size=2e+09,atrim=0:{total_duration},afade=t=out:st={fade_start}:d=0.7,aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[sfx];"
            f"[voice][sfx]amix=inputs=2:duration=first:weights=1 0.28:normalize=0[aout]"
        )
        audio_map = '[aout]'
        print(f"🔊 FINAL MIX: Voice + SFX(0.28) + fade-out@{fade_start:.1f}s")
        
    else:
        # No music, just use voiceover
        audio_map = f'{voice_index}:a'
        print(f"🔊 Voice only (no music/sfx)")
    
    # Complete filter complex
    filter_complex = ';'.join(filter_parts)
    
    # FFmpeg command with DEVICE COMPATIBILITY settings
    # -profile:v baseline + -pix_fmt yuv420p = Samsung/iOS/Windows native player support
    # -movflags +faststart = Web streaming optimization
    cmd = [
        get_ffmpeg_path(),
        '-y',  # Overwrite output
        *inputs,
        '-filter_complex', filter_complex,
        '-map', '[vfinal]',
        '-map', audio_map,
        '-c:v', 'libx264',
        '-profile:v', 'baseline',  # Maximum device compatibility
        '-level', '3.0',           # Safe level for mobile devices
        '-pix_fmt', 'yuv420p',     # Required for Samsung/iOS/Windows
        '-preset', 'fast',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '128k',
        '-movflags', '+faststart', # Web/streaming optimization
        '-shortest',
        '-t', str(total_duration + 0.5),  # Add small buffer
        output_path
    ]
    
    print(f"🎬 Running FFmpeg composition...")
    print(f"📝 FILTER_COMPLEX (first 500 chars): {filter_complex[:500]}...")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=180  # 3 minute timeout
    )
    
    # Always log stderr for debugging
    if result.stderr:
        # Log last 1000 chars of stderr
        stderr_tail = result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr
        print(f"📋 FFmpeg stderr (last 1000 chars): {stderr_tail}")
    
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg failed with code {result.returncode}")
    
    # Verify output file has audio
    if os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        print(f"✅ Historical video composed: {output_path} ({file_size} bytes)")
    else:
        raise RuntimeError(f"Output file not created: {output_path}")
    
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
