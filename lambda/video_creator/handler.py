"""
YouTube Shorts History Video Generator - Main Handler
Generates fascinating historical content for global audience
Uses AWS Bedrock (Claude) for scripts + Titan for images + Polly for voice
All content is AI-generated and copyright-safe
"""

import json
import os
import boto3
import logging
from datetime import datetime

from script_gen import generate_history_script
from stock_fetcher import fetch_videos_by_segments
from tts import generate_voiceover
from video_composer import compose_video
from music_fetcher import generate_historical_music
from copyright_safety import reset_copyright_tracker, get_copyright_tracker

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client('s3')
sns = boto3.client('sns')


def lambda_handler(event, context):
    """
    Main Lambda handler for history video generation
    
    Event can contain:
    - topic: Specific topic to generate (e.g., "Atatürk's favorite foods")
    - era: Historical era (ancient, medieval, ottoman, early_20th, etc.)
    
    If no topic provided, random topic is selected from built-in list
    """
    logger.info("🏛️ Starting History Shorts video generation...")
    
    # Reset copyright tracker for this new video
    tracker = reset_copyright_tracker()
    logger.info("📋 Copyright tracker initialized")
    
    try:
        region = os.environ.get('AWS_REGION_NAME', 'us-east-1')
        
        # Get topic from event (optional)
        topic = event.get('topic') if event else None
        era = event.get('era') if event else None
        
        if topic:
            logger.info(f"📜 Generating script for topic: {topic}")
        else:
            logger.info("📜 Generating script with random historical topic...")
        
        # Step 1: Generate history script using Bedrock Claude
        script = generate_history_script(topic=topic, era=era, region_name=region)
        logger.info(f"Script generated: {script['title']}")
        logger.info(f"Era: {script.get('era', 'unknown')}, Mood: {script.get('mood', 'documentary')}")
        
        # Step 2: Generate AI historical images for each segment
        logger.info("🎨 Generating historical images with AWS Titan...")
        
        segments = script.get('segments', [])
        script_era = script.get('era', 'early_20th')
        
        if segments:
            logger.info(f"📍 Generating {len(segments)} historical images...")
            video_paths = fetch_videos_by_segments(segments, era=script_era)
        else:
            # Fallback: use search keywords as prompts
            logger.info("📍 No segments found, using keyword-based generation (fallback)")
            from stock_fetcher import fetch_stock_videos
            keywords = script.get('search_keywords', ['historical scene'])
            video_paths = fetch_stock_videos(keywords=keywords, num_clips=4)
        
        # CRITICAL: Ensure we have at least SOME video clips
        # If AI generation completely failed, create visible color fallbacks
        if not video_paths or len(video_paths) == 0:
            logger.warning("⚠️ No video clips generated! Creating visible fallbacks...")
            from stock_fetcher import create_simple_color_fallback
            video_paths = []
            for i in range(4):  # Create 4 fallback clips
                fallback = create_simple_color_fallback(i)
                if fallback:
                    video_paths.append(fallback)
            logger.info(f"Created {len(video_paths)} fallback clips")
        
        logger.info(f"Generated {len(video_paths)} video clips (all AI-generated, copyright-safe)")
        
        # Step 3: Generate voiceover with AWS Polly (documentary style)
        logger.info("🎙️ Generating documentary voiceover...")
        mood = script.get('mood', 'documentary')
        audio_path = generate_voiceover(script['voiceover_text'], mood=mood)
        tracker.add_audio("aws_polly", "Documentary", script['voiceover_text'])
        logger.info(f"Voiceover generated (mood: {mood})")
        
        # Step 4: Generate period-appropriate background music
        logger.info("🎵 Generating period background music...")
        from tts import get_audio_duration
        audio_duration = get_audio_duration(audio_path)
        
        music_style = script.get('music_style', 'nostalgic_piano')
        music_result = generate_historical_music(
            duration=audio_duration + 2,
            music_style=music_style,
            mood=mood,
            era=script_era
        )
        music_path = music_result.get('path') if music_result else None
        
        if music_path:
            logger.info(f"Background music generated ({music_style})")
        else:
            logger.warning("Could not generate background music, proceeding without it")
        
        # Step 5: Compose final video with historical effects
        logger.info("🎬 Composing final historical video...")
        output_path = compose_video(
            video_paths=video_paths,
            audio_path=audio_path,
            title=script['title'],
            subtitle_text=script['voiceover_text'],
            music_path=music_path,
            era=script_era
        )
        logger.info("Video composed successfully")
        
        # Get license summary
        license_summary = tracker.get_license_summary()
        logger.info(f"📜 License summary: {len(license_summary['media_items'])} items, all AI-generated")
        
        # Step 6: Upload video to S3
        bucket = os.environ['S3_BUCKET_NAME']
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        s3_key = f"videos/{timestamp}_{script['safe_title']}.mp4"
        
        logger.info(f"☁️ Uploading to S3: {s3_key}")
        s3.upload_file(output_path, bucket, s3_key)
        
        # Also save license report to S3
        license_report_path = tracker.save_license_report()
        license_s3_key = f"licenses/{timestamp}_{script['safe_title']}_license.json"
        s3.upload_file(license_report_path, bucket, license_s3_key)
        logger.info(f"📄 License report uploaded: {license_s3_key}")
        
        # Generate presigned URL (valid for 7 days)
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket, 'Key': s3_key},
            ExpiresIn=604800  # 7 days
        )
        
        # Step 7: Send notification via SNS
        logger.info("📧 Sending notification...")
        sns_topic = os.environ['SNS_TOPIC_ARN']
        
        sources_used = ', '.join(license_summary.get('sources_used', ['AI-Generated']))
        
        sns.publish(
            TopicArn=sns_topic,
            Subject=f"🏛️ New History Short Ready: {script['title']}",
            Message=f"""
Your new History Short is ready!

📌 Title: {script['title']}
📜 Topic: {script.get('original_topic', 'Random')}
🕰️ Era: {script_era}
🎵 Music: {music_style}

📝 Script: {script['voiceover_text']}

🔗 Download Link (valid for 7 days):
{presigned_url}

---
✅ COPYRIGHT STATUS: ALL CONTENT IS AI-GENERATED
📋 Sources: {sources_used}
---
Generated by History Shorts AI System
Historical Script: AWS Bedrock Claude
Historical Visuals: AWS Titan Image Generator
Voice: AWS Polly Neural
Music: AI-Generated
            """.strip()
        )
        
        logger.info("✅ History video generation complete!")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'History video generated successfully',
                'title': script['title'],
                'topic': script.get('original_topic', 'Random'),
                'era': script_era,
                's3_key': s3_key,
                'download_url': presigned_url,
                'copyright_status': 'All content is AI-generated',
                'sources_used': sources_used,
                'license_report': license_s3_key
            })
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating video: {str(e)}")
        raise e


# Backward compatibility - keep old function names working
def generate_absurd_script(*args, **kwargs):
    """Legacy alias"""
    return generate_history_script(*args, **kwargs)
