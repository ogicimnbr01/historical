"""
Smart Music Cutter for YouTube Shorts
Analyzes music files and extracts the best segment for short videos
Uses loudness analysis to find the most impactful section
"""

import os
import subprocess
import tempfile
import json
import random
from typing import Optional, Tuple


def get_ffmpeg_path() -> str:
    """Get FFmpeg binary path"""
    if os.path.exists("/opt/bin/ffmpeg"):
        return "/opt/bin/ffmpeg"
    return "ffmpeg"


def get_ffprobe_path() -> str:
    """Get FFprobe binary path"""
    if os.path.exists("/opt/bin/ffprobe"):
        return "/opt/bin/ffprobe"
    return "ffprobe"


def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file in seconds"""
    try:
        cmd = [
            get_ffprobe_path(),
            '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'json',
            audio_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return float(data['format']['duration'])
    except Exception as e:
        print(f"⚠️ Could not get audio duration: {e}")
    return 60.0  # Default fallback


def analyze_loudness(audio_path: str, segment_duration: float = 5.0) -> list:
    """
    Analyze audio file and return loudness values for each segment
    Returns list of (start_time, loudness) tuples
    """
    duration = get_audio_duration(audio_path)
    loudness_data = []
    
    # Sample every 5 seconds
    for start in range(0, int(duration) - int(segment_duration), int(segment_duration)):
        try:
            cmd = [
                get_ffmpeg_path(),
                '-y',
                '-ss', str(start),
                '-t', str(segment_duration),
                '-i', audio_path,
                '-af', 'volumedetect',
                '-f', 'null',
                '-'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            # Parse mean volume from stderr
            stderr = result.stderr
            mean_vol = -30.0  # Default
            for line in stderr.split('\n'):
                if 'mean_volume' in line:
                    try:
                        mean_vol = float(line.split(':')[1].strip().replace(' dB', ''))
                    except:
                        pass
            
            loudness_data.append((start, mean_vol))
            
        except Exception as e:
            loudness_data.append((start, -30.0))
    
    return loudness_data


def find_best_segment(audio_path: str, target_duration: float = 15.0, 
                     skip_intro: float = 10.0) -> Tuple[float, float]:
    """
    Find the best segment to use from a longer audio file
    
    Strategy:
    1. Skip the first 10 seconds (usually intro/quiet)
    2. Analyze loudness of remaining audio
    3. Find the loudest/most energetic section
    4. Return start time and duration
    """
    total_duration = get_audio_duration(audio_path)
    
    # If audio is already short enough, use from beginning (after small skip)
    if total_duration <= target_duration + 5:
        start = min(2.0, total_duration * 0.1)
        return (start, min(target_duration, total_duration - start))
    
    # Analyze loudness
    loudness_data = analyze_loudness(audio_path, segment_duration=5.0)
    
    if not loudness_data:
        # Fallback: random position after intro
        max_start = max(0, total_duration - target_duration - 5)
        start = random.uniform(skip_intro, min(skip_intro + 30, max_start))
        return (start, target_duration)
    
    # Filter out intro
    valid_segments = [(t, v) for t, v in loudness_data if t >= skip_intro]
    
    if not valid_segments:
        valid_segments = loudness_data
    
    # Find loudest segment
    best_segment = max(valid_segments, key=lambda x: x[1])
    best_start = best_segment[0]
    
    # Make sure we don't exceed audio length
    if best_start + target_duration > total_duration:
        best_start = max(0, total_duration - target_duration - 2)
    
    print(f"🎵 Best segment found at {best_start:.1f}s (loudness: {best_segment[1]:.1f} dB)")
    
    return (best_start, target_duration)


def cut_music_segment(input_path: str, output_path: str, 
                     start_time: float, duration: float,
                     fade_in: float = 1.0, fade_out: float = 2.0) -> bool:
    """
    Cut a segment from music file with fade in/out
    
    Args:
        input_path: Path to original music file
        output_path: Path for output file
        start_time: Where to start cutting (seconds)
        duration: How long to cut (seconds)
        fade_in: Fade in duration (seconds)
        fade_out: Fade out duration (seconds)
    
    Returns:
        True if successful
    """
    try:
        # Build filter for fade in/out
        fade_filter = (
            f"afade=t=in:st=0:d={fade_in},"
            f"afade=t=out:st={duration - fade_out}:d={fade_out}"
        )
        
        cmd = [
            get_ffmpeg_path(),
            '-y',
            '-ss', str(start_time),
            '-t', str(duration),
            '-i', input_path,
            '-af', fade_filter,
            '-c:a', 'aac',
            '-b:a', '128k',
            output_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0 and os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            if file_size > 1000:
                print(f"✅ Music cut: {start_time:.1f}s - {start_time + duration:.1f}s ({file_size} bytes)")
                return True
        
        print(f"⚠️ Music cut failed: {result.stderr[:200]}")
        return False
        
    except Exception as e:
        print(f"❌ Error cutting music: {e}")
        return False


def smart_cut_music(input_path: str, target_duration: float = 15.0) -> Optional[str]:
    """
    Main function: Analyze music and extract the best segment
    
    Args:
        input_path: Path to original music file (can be long)
        target_duration: Desired output duration in seconds
    
    Returns:
        Path to cut music file, or None if failed
    """
    if not os.path.exists(input_path):
        print(f"❌ Music file not found: {input_path}")
        return None
    
    # Find the best segment
    start_time, duration = find_best_segment(
        input_path, 
        target_duration=target_duration,
        skip_intro=8.0  # Skip first 8 seconds
    )
    
    # Create output path
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(
        tempfile.gettempdir(),
        f"cut_{base_name}_{int(start_time)}s.m4a"
    )
    
    # Cut the segment
    success = cut_music_segment(
        input_path=input_path,
        output_path=output_path,
        start_time=start_time,
        duration=duration,
        fade_in=1.0,
        fade_out=2.0
    )
    
    if success:
        return output_path
    return None


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        duration = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
        
        print(f"Testing smart cut on: {input_file}")
        result = smart_cut_music(input_file, duration)
        
        if result:
            print(f"✅ Output: {result}")
        else:
            print("❌ Cut failed")
    else:
        print("Usage: python smart_music_cutter.py <input_file> [duration]")
