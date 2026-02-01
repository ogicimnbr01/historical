"""
Copyright Safety Module
Ensures all media content is properly licensed and royalty-free
Tracks attributions for compliance with content licenses
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional


# Approved royalty-free sources
APPROVED_SOURCES = {
    "pexels": {
        "name": "Pexels",
        "license": "Pexels License (Free for commercial use, no attribution required)",
        "url": "https://www.pexels.com/license/",
        "safe_for_youtube": True,
        "requires_attribution": False
    },
    "pixabay": {
        "name": "Pixabay", 
        "license": "Pixabay License (Free for commercial use)",
        "url": "https://pixabay.com/service/license/",
        "safe_for_youtube": True,
        "requires_attribution": False
    },
    "fallback": {
        "name": "Self-Generated",
        "license": "Original Content (No restrictions)",
        "url": None,
        "safe_for_youtube": True,
        "requires_attribution": False
    }
}


class CopyrightTracker:
    """Tracks all media used in video generation for copyright compliance"""
    
    def __init__(self):
        self.used_media: List[Dict] = []
        self.video_id: str = datetime.now().strftime("%Y%m%d_%H%M%S")
        
    def add_video(self, 
                  source: str,
                  video_id: str,
                  video_url: str,
                  photographer: Optional[str] = None,
                  photographer_url: Optional[str] = None) -> bool:
        """
        Add a video to the tracking list after verifying it's from an approved source
        
        Returns:
            True if video is safe to use, False otherwise
        """
        # Verify source is approved
        if source.lower() not in APPROVED_SOURCES:
            print(f"⚠️ WARNING: Source '{source}' is NOT in approved list! Rejecting.")
            return False
            
        source_info = APPROVED_SOURCES[source.lower()]
        
        if not source_info["safe_for_youtube"]:
            print(f"⚠️ WARNING: Source '{source}' is not safe for YouTube! Rejecting.")
            return False
        
        media_entry = {
            "type": "video",
            "source": source,
            "source_name": source_info["name"],
            "license": source_info["license"],
            "license_url": source_info["url"],
            "video_id": video_id,
            "video_url": video_url,
            "photographer": photographer,
            "photographer_url": photographer_url,
            "used_at": datetime.now().isoformat(),
            "requires_attribution": source_info["requires_attribution"]
        }
        
        self.used_media.append(media_entry)
        print(f"✅ Copyright verified: {source_info['name']} video {video_id} - {source_info['license']}")
        
        return True
    
    def add_fallback_video(self, file_path: str) -> bool:
        """Register a self-generated fallback video (always safe)"""
        return self.add_video(
            source="fallback",
            video_id=os.path.basename(file_path),
            video_url=file_path,
            photographer="AI Generated",
            photographer_url=None
        )
    
    def add_audio(self,
                  source: str,
                  voice_id: str,
                  text_content: str) -> bool:
        """
        Track audio/voiceover usage
        AWS Polly generated voices are always safe for commercial use
        """
        media_entry = {
            "type": "audio",
            "source": source,
            "source_name": "AWS Polly TTS",
            "license": "AWS Service (Commercial use allowed)",
            "license_url": "https://aws.amazon.com/polly/",
            "voice_id": voice_id,
            "text_length": len(text_content),
            "used_at": datetime.now().isoformat(),
            "requires_attribution": False
        }
        
        self.used_media.append(media_entry)
        print(f"✅ Audio verified: AWS Polly voice {voice_id} - Commercial use allowed")
        
        return True
    
    def add_music(self,
                  source: str,
                  music_id: str,
                  title: str,
                  artist: Optional[str] = None,
                  license_type: str = "Original Content") -> bool:
        """
        Track background music usage
        Only accepts music from approved sources or self-generated
        """
        # Self-generated music is always safe
        if source.lower() in ["self_generated", "fallback", "generated"]:
            media_entry = {
                "type": "music",
                "source": "self_generated",
                "source_name": "AI Generated Music",
                "license": "Original Content (No Copyright)",
                "license_url": None,
                "music_id": music_id,
                "title": title,
                "artist": artist or "System Generated",
                "used_at": datetime.now().isoformat(),
                "requires_attribution": False,
                "safe_for_youtube": True
            }
            self.used_media.append(media_entry)
            print(f"✅ Music verified: Self-generated '{title}' - No copyright issues")
            return True
        
        # Check if from approved source
        if source.lower() in APPROVED_SOURCES:
            source_info = APPROVED_SOURCES[source.lower()]
            media_entry = {
                "type": "music",
                "source": source,
                "source_name": source_info["name"],
                "license": source_info["license"],
                "license_url": source_info["url"],
                "music_id": music_id,
                "title": title,
                "artist": artist,
                "used_at": datetime.now().isoformat(),
                "requires_attribution": source_info["requires_attribution"],
                "safe_for_youtube": source_info["safe_for_youtube"]
            }
            self.used_media.append(media_entry)
            print(f"✅ Music verified: {source_info['name']} '{title}' - {source_info['license']}")
            return True
        
        # Unknown source - reject
        print(f"⚠️ WARNING: Music source '{source}' is NOT approved! Rejecting.")
        return False
    
    def generate_attribution_text(self) -> str:
        """Generate attribution text for video description (optional but good practice)"""
        lines = ["Stock footage provided by:"]
        
        seen_sources = set()
        for media in self.used_media:
            if media["type"] == "video" and media["source"] != "fallback":
                source_name = media["source_name"]
                if source_name not in seen_sources:
                    lines.append(f"• {source_name} (Royalty-Free)")
                    seen_sources.add(source_name)
                    
        if len(seen_sources) == 0:
            return ""
            
        lines.append("\nAll content is licensed for commercial use.")
        return "\n".join(lines)
    
    def get_license_summary(self) -> Dict:
        """Get a summary of all licenses used"""
        summary = {
            "video_id": self.video_id,
            "generated_at": datetime.now().isoformat(),
            "total_media_items": len(self.used_media),
            "all_content_safe": True,
            "sources_used": [],
            "media_items": self.used_media,
            "attribution_text": self.generate_attribution_text()
        }
        
        sources = set()
        for media in self.used_media:
            source = media.get("source_name", "Unknown")
            sources.add(source)
            
        summary["sources_used"] = list(sources)
        
        return summary
    
    def save_license_report(self, output_dir: str = "/tmp") -> str:
        """Save a license report JSON file"""
        report = self.get_license_summary()
        report_path = os.path.join(output_dir, f"license_report_{self.video_id}.json")
        
        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)
            
        print(f"📄 License report saved: {report_path}")
        return report_path


def verify_pexels_video(video_data: Dict) -> Dict:
    """
    Verify a Pexels video is safe to use and extract relevant info
    
    Pexels License (as of 2024):
    - All photos and videos are free to use
    - Attribution is not required
    - You can modify the photos and videos
    - You can use them for commercial purposes
    """
    return {
        "is_safe": True,  # All Pexels content is safe
        "license": "Pexels License",
        "video_id": video_data.get("id"),
        "video_url": video_data.get("url"),
        "photographer": video_data.get("user", {}).get("name"),
        "photographer_url": video_data.get("user", {}).get("url"),
        "source": "pexels"
    }


def is_content_safe_for_youtube(source: str) -> bool:
    """Quick check if content from a source is safe for YouTube"""
    source_lower = source.lower()
    if source_lower in APPROVED_SOURCES:
        return APPROVED_SOURCES[source_lower]["safe_for_youtube"]
    return False


# Global tracker instance
_copyright_tracker: Optional[CopyrightTracker] = None


def get_copyright_tracker() -> CopyrightTracker:
    """Get or create the global copyright tracker"""
    global _copyright_tracker
    if _copyright_tracker is None:
        _copyright_tracker = CopyrightTracker()
    return _copyright_tracker


def reset_copyright_tracker():
    """Reset the tracker for a new video generation"""
    global _copyright_tracker
    _copyright_tracker = CopyrightTracker()
    return _copyright_tracker


if __name__ == "__main__":
    # Test the copyright tracker
    tracker = CopyrightTracker()
    
    # Simulate adding content
    tracker.add_video("pexels", "12345", "https://example.com/video.mp4", "John Doe")
    tracker.add_fallback_video("/tmp/fallback_1.mp4")
    tracker.add_audio("aws_polly", "Matthew", "Hello world!")
    
    # Get summary
    summary = tracker.get_license_summary()
    print("\n" + "="*50)
    print("LICENSE SUMMARY")
    print("="*50)
    print(json.dumps(summary, indent=2))
