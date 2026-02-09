"""
YouTube Shorts History Video Generator - Main Handler
Generates fascinating historical content for global audience
Uses AWS Bedrock (Claude) for scripts + Titan for images + Polly for voice
All content is AI-generated and copyright-safe
"""

import json
import os
import random
import boto3
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

from script_gen import generate_history_script
from script_pipeline import generate_script_with_fallback
from stock_fetcher import fetch_videos_by_segments
from tts import generate_voiceover
from video_composer import compose_video
from music_fetcher import generate_historical_music
from copyright_safety import reset_copyright_tracker, get_copyright_tracker

# YouTube Analytics integration (optional - for correlation tracking)
try:
    from youtube_analytics import save_video_with_predictions
    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False

# Setup logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# AWS clients
s3 = boto3.client('s3')
sns = boto3.client('sns')

# DynamoDB for job tracking and structured logging
dynamodb = boto3.resource('dynamodb')
JOBS_TABLE_NAME = os.environ.get('JOBS_TABLE_NAME', 'shorts_jobs')
RUN_LOGS_TABLE_NAME = os.environ.get('RUN_LOGS_TABLE_NAME', 'shorts_run_logs')

try:
    jobs_table = dynamodb.Table(JOBS_TABLE_NAME)
    logs_table = dynamodb.Table(RUN_LOGS_TABLE_NAME)
    JOB_TRACKING_ENABLED = True
except Exception as e:
    logger.warning(f"Job tracking disabled: {e}")
    JOB_TRACKING_ENABLED = False


# =============================================================================
# JOB STATUS & STRUCTURED LOGGING HELPERS
# =============================================================================

def update_job_status(job_id: str, status: str, **extra_fields):
    """
    Update job status in DynamoDB.
    Status: queued -> running -> completed | failed
    """
    if not JOB_TRACKING_ENABLED or not job_id:
        return
    
    try:
        update_expr = "SET #status = :status, updated_at_utc = :updated"
        expr_values = {
            ":status": status,
            ":updated": datetime.utcnow().isoformat() + "Z"
        }
        expr_names = {"#status": "status"}
        
        for key, value in extra_fields.items():
            update_expr += f", {key} = :{key}"
            expr_values[f":{key}"] = value
        
        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values
        )
        logger.info(f"[JOB] {job_id} -> {status}")
    except Exception as e:
        logger.warning(f"Failed to update job status: {e}")


def log_event(job_id: str, component: str, level: str, event: str, message: str, payload: dict = None):
    """
    Write structured log entry to DynamoDB run_logs table.
    
    Args:
        job_id: The job this log belongs to
        component: video_generator / analytics_fetcher / decision_engine
        level: INFO / WARN / ERROR
        event: STEP_START / METRICS / FALLBACK_USED / COMPLETE / etc.
        message: Human-readable message
        payload: Optional structured data
    """
    if not JOB_TRACKING_ENABLED or not job_id:
        return
    
    try:
        ts = datetime.utcnow()
        seq = uuid.uuid4().hex[:8]
        sk = f"{ts.isoformat()}Z#{component}#{seq}"
        
        item = {
            "pk": job_id,
            "sk": sk,
            "job_id": job_id,
            "ts_utc": ts.isoformat() + "Z",
            "component": component,
            "level": level,
            "event": event,
            "message": message,
            "expires_at": int((ts + timedelta(days=14)).timestamp()),
            # GSI for querying by component/day
            "gsi1pk": f"{component}#{ts.strftime('%Y-%m-%d')}",
            "gsi1sk": ts.isoformat() + "Z"
        }
        
        if payload:
            # Convert any Decimal-incompatible types
            item["payload"] = json.loads(json.dumps(payload, default=str))
        
        logs_table.put_item(Item=item)
        logger.info(f"[LOG] {component}/{level}/{event}: {message}")
    except Exception as e:
        logger.warning(f"Failed to write log event: {e}")


# =============================================================================
# AUTOPILOT HELPERS
# =============================================================================

def load_autopilot_config(region_name: str = None) -> dict:
    """
    Load autopilot configuration from DynamoDB.
    Returns default config if not found.
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    table_name = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")
    
    try:
        dynamodb = boto3.resource("dynamodb", region_name=region)
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"video_id": "autopilot_config"})
        
        if "Item" in response:
            logger.info("🤖 Loaded autopilot config from DynamoDB")
            return response["Item"]
    except Exception as e:
        logger.warning(f"⚠️ Failed to load autopilot config: {e}")
    
    # Return default config
    logger.info("🤖 Using default autopilot config")
    return {
        "mode_weights": {"QUALITY": 0.7, "FAST": 0.3},
        "title_weights": {"bold": 0.5, "safe": 0.3, "experimental": 0.2},
        "hook_family_weights": {
            "contradiction": 0.3,
            "revelation": 0.25,
            "challenge": 0.25,
            "contrast": 0.2
        },
        "explore_rate": 0.2,
        "prompt_memory": {},
        "recovery_mode": False
    }


def weighted_random_choice(weights: dict) -> str:
    """
    Select a random key based on weights.
    
    Args:
        weights: Dict like {"QUALITY": 0.7, "FAST": 0.3}
    
    Returns:
        Selected key
    """
    if not weights:
        return "QUALITY"  # Default
    
    # Convert to lists
    options = list(weights.keys())
    probs = [float(weights[k]) for k in options]
    
    # Normalize
    total = sum(probs)
    if total <= 0:
        return options[0]
    
    probs = [p / total for p in probs]
    
    # Random selection
    r = random.random()
    cumulative = 0
    for option, prob in zip(options, probs):
        cumulative += prob
        if r <= cumulative:
            return option
    
    return options[-1]  # Fallback


def lambda_handler(event, context):
    """
    Main Lambda handler for history video generation
    
    Event can contain:
    - job_id: Optional job ID for tracking (from admin panel)
    - topic: Specific topic to generate (e.g., "Atatürk's favorite foods")
    - era: Historical era (ancient, medieval, ottoman, early_20th, etc.)
    - use_pipeline: Use new iterative pipeline (default: True)
    - mark_as_test: Mark video as test (calibration_eligible=false)
    
    If no topic provided, random topic is selected from built-in list
    """
    logger.info("🏛️ Starting History Shorts video generation...")
    
    # Extract job_id for tracking (if coming from admin panel)
    job_id = event.get('job_id') if event else None
    mark_as_test = event.get('mark_as_test', False) if event else False
    
    # Update job status to running
    if job_id:
        update_job_status(job_id, "running", started_at_utc=datetime.utcnow().isoformat() + "Z")
        log_event(job_id, "video_generator", "INFO", "STEP_START", "Video generation started")
    
    # Reset copyright tracker for this new video
    tracker = reset_copyright_tracker()
    logger.info("📋 Copyright tracker initialized")
    
    try:
        region = os.environ.get('AWS_REGION_NAME', 'us-east-1')
        
        # =====================================================================
        # AUTOPILOT: Load config and select production parameters
        # =====================================================================
        autopilot_config = load_autopilot_config(region)
        config_version = autopilot_config.get('version', 0)
        
        # Weighted random selection for mode (QUALITY vs FAST)
        mode_weights = autopilot_config.get('mode_weights', {'QUALITY': 0.7, 'FAST': 0.3})
        selected_mode = weighted_random_choice(mode_weights)
        use_pipeline = (selected_mode == 'QUALITY')  # QUALITY uses full pipeline
        
        # Weighted random selection for title type
        title_weights = autopilot_config.get('title_weights', {'bold': 0.5, 'safe': 0.3, 'experimental': 0.2})
        selected_title_type = weighted_random_choice(title_weights)
        
        # Weighted random selection for hook family
        hook_family_weights = autopilot_config.get('hook_family_weights', {
            'contradiction': 0.25, 'revelation': 0.25, 'challenge': 0.25, 'contrast': 0.25
        })
        selected_hook_family = weighted_random_choice(hook_family_weights)
        
        # Get prompt memory for writer/evaluator
        prompt_memory = autopilot_config.get('prompt_memory', {})
        
        # Check recovery mode
        recovery_mode = autopilot_config.get('recovery_mode', False)
        if recovery_mode:
            # Override with recovery preset
            selected_mode = 'QUALITY'
            selected_title_type = 'safe'
            selected_hook_family = 'contradiction'  # High-clarity hook family
            use_pipeline = True
            logger.warning(f"⚠️ AUTOPILOT: Recovery mode active, {autopilot_config.get('recovery_videos_remaining', 0)} videos remaining")
        
        # COMPREHENSIVE SINGLE-LINE LOG for debugging and tracking
        weights_snapshot = {
            'mode': {k: float(v) for k, v in mode_weights.items()},
            'title': {k: float(v) for k, v in title_weights.items()},
            'hook': {k: float(v) for k, v in hook_family_weights.items()}
        }
        logger.info(f"🤖 AUTOPILOT_DECISION | v={config_version} | mode={selected_mode} | title={selected_title_type} | hook={selected_hook_family} | recovery={recovery_mode} | weights={json.dumps(weights_snapshot)}")
        
        # Get parameters from event (can override autopilot)
        topic = event.get('topic') if event else None
        era = event.get('era') if event else None
        
        # Event can force specific mode/title (for testing)
        if event and event.get('force_mode'):
            selected_mode = event.get('force_mode')
            use_pipeline = (selected_mode == 'QUALITY')
            logger.info(f"🔧 Force override: mode={selected_mode}")
        
        if topic:
            logger.info(f"📜 Generating script for topic: {topic}")
        else:
            logger.info("📜 Generating script with random historical topic...")
        
        # Step 1: Generate history script using Bedrock Claude
        # Uses new pipeline with scoring/refinement, or falls back to old system
        logger.info(f"🔧 Pipeline mode: {'NEW (v2.0)' if use_pipeline else 'LEGACY (v1.0)'}")
        script = generate_script_with_fallback(
            topic=topic, 
            era=era, 
            region_name=region, 
            use_pipeline=use_pipeline,
            prompt_memory=prompt_memory  # Pass DO/DON'T examples
        )
        
        # Inject selected title type
        script['title_variant_type'] = selected_title_type
        script['autopilot_mode'] = selected_mode
        script['autopilot_hook_family'] = selected_hook_family
        script['autopilot_config_version'] = config_version
        
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
        logger.info("🎵 Analyzing story for music selection...")
        from tts import get_audio_duration
        from story_music_matcher import get_music_category_for_script
        
        audio_duration = get_audio_duration(audio_path)
        
        # Analyze script content to find best music category
        music_category, confidence = get_music_category_for_script(script)
        logger.info(f"🎵 Music category: {music_category} (confidence: {confidence:.0%})")
        
        music_result = generate_historical_music(
            duration=audio_duration + 2,
            music_style=music_category,  # Use analyzed category
            mood=mood,
            era=script_era
        )
        music_path = music_result.get('path') if music_result else None
        
        if music_path:
            logger.info(f"Background music generated ({music_category})")
            # DEBUG: Upload music to S3 for inspection
            try:
                bucket = os.environ['S3_BUCKET_NAME']
                timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                music_s3_key = f"debug/music/{timestamp}_{music_category}.m4a"
                s3.upload_file(music_path, bucket, music_s3_key)
                logger.info(f"🎵 DEBUG: Music uploaded to s3://{bucket}/{music_s3_key}")
            except Exception as e:
                logger.warning(f"⚠️ DEBUG: Failed to upload music: {e}")
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
        
        # Step 6.5: Save video metrics for YouTube correlation tracking (optional)
        if ANALYTICS_AVAILABLE:
            try:
                # Extract pipeline predictions
                pipeline_scores = script.get('pipeline_scores', {})
                hook_kpi = pipeline_scores.get('hook_kpi', {})
                
                # Get mode from AUTOPILOT selection (not env var)
                pipeline_mode = script.get('autopilot_mode', 'QUALITY')
                
                # CRITICAL: Check if fallback was used (pollutes calibration data)
                fallback_used = script.get('fallback_used', False)
                pipeline_executed = "fallback" if fallback_used else "v2.3"
                calibration_eligible = not fallback_used
                
                # Extract all calibration fields
                predicted_retention = hook_kpi.get('predicted_retention', 50)
                hook_score = pipeline_scores.get('hook_score', 0)
                instant_clarity = hook_kpi.get('instant_clarity', 5)
                curiosity_gap = hook_kpi.get('curiosity_gap', 5)
                swipe_risk = hook_kpi.get('swipe_risk', 5)
                visual_relevance = pipeline_scores.get('visual_relevance', 5)
                
                # Content tags
                era = script.get('era', 'unknown')
                topic_entity = script.get('topic_entity', script.get('original_topic', 'unknown'))
                
                # Autopilot selections (for full traceability)
                title_variant_type = script.get('title_variant_type', 'safe')
                title_used = script.get('title', '')
                hook_family = script.get('autopilot_hook_family', 'unknown')
                autopilot_config_version = script.get('autopilot_config_version', 0)
                
                # Use timestamp-based ID (will be updated with YouTube ID after upload)
                internal_video_id = f"pending_{timestamp}"
                publish_time = datetime.now().isoformat()
                
                save_video_with_predictions(
                    video_id=internal_video_id,
                    publish_time_utc=publish_time,
                    pipeline_version="2.3",
                    pipeline_executed=pipeline_executed,
                    mode=pipeline_mode,
                    hook_score=hook_score,
                    predicted_retention=predicted_retention,
                    instant_clarity=instant_clarity,
                    curiosity_gap=curiosity_gap,
                    swipe_risk=swipe_risk,
                    visual_relevance=visual_relevance,
                    era=era,
                    topic_entity=topic_entity[:100] if topic_entity else "unknown",
                    title_variant_type=title_variant_type,
                    title_used=title_used[:200] if title_used else "",
                    calibration_eligible=calibration_eligible,
                    hook_family=hook_family,
                    autopilot_config_version=autopilot_config_version,
                    region_name=region
                )
                logger.info(f"[CALIBRATION] Saved: {pipeline_executed} | mode={pipeline_mode} | hook_family={hook_family} | config_v={autopilot_config_version}")
            except Exception as e:
                logger.warning(f"[WARNING] Failed to save video metrics: {e}")
        
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
🎵 Music: {music_category}

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
        
        # Update job status to completed
        if job_id:
            result_video_id = internal_video_id if ANALYTICS_AVAILABLE else s3_key
            update_job_status(
                job_id, "completed",
                completed_at_utc=datetime.utcnow().isoformat() + "Z",
                result_video_id=result_video_id,
                result_s3_key=s3_key
            )
            log_event(job_id, "video_generator", "INFO", "COMPLETE", 
                      f"Video generated successfully: {script['title']}", 
                      {"s3_key": s3_key, "title": script['title']})
        
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
                'license_report': license_s3_key,
                'job_id': job_id
            })
        }
        
    except Exception as e:
        logger.error(f"❌ Error generating video: {str(e)}")
        
        # Update job status to failed
        if job_id:
            update_job_status(
                job_id, "failed",
                completed_at_utc=datetime.utcnow().isoformat() + "Z",
                error_message=str(e)
            )
            log_event(job_id, "video_generator", "ERROR", "FAILED", 
                      f"Video generation failed: {str(e)}")
        
        raise e


# Backward compatibility - keep old function names working
def generate_absurd_script(*args, **kwargs):
    """Legacy alias"""
    return generate_history_script(*args, **kwargs)
