"""
YouTube Analytics API Integration
Fetches video performance metrics for correlation with pipeline predictions.
"""

import json
import os
import boto3
from datetime import datetime, timedelta
from typing import Optional, Dict, List

# Google API client (installed via Lambda layer)
try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    print("[WARNING] Google API client not available (install google-api-python-client)")


# ============================================================================
# CONFIGURATION
# ============================================================================

YOUTUBE_ANALYTICS_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly"
]

METRICS_TABLE_NAME = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")
OAUTH_SECRET_NAME = os.environ.get("YOUTUBE_OAUTH_SECRET", "shorts/youtube-oauth")


# ============================================================================
# SECRETS MANAGEMENT
# ============================================================================

def get_oauth_credentials(region_name: str = None) -> Optional[dict]:
    """
    Retrieve YouTube OAuth credentials from AWS Secrets Manager.
    
    Expected secret format:
    {
        "client_id": "...",
        "client_secret": "...",
        "refresh_token": "...",
        "token_uri": "https://oauth2.googleapis.com/token"
    }
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    
    try:
        client = boto3.client("secretsmanager", region_name=region)
        response = client.get_secret_value(SecretId=OAUTH_SECRET_NAME)
        return json.loads(response["SecretString"])
    except Exception as e:
        print(f"❌ Failed to get OAuth credentials: {e}")
        return None


def build_youtube_client(region_name: str = None):
    """
    Build authenticated YouTube Analytics API client.
    """
    if not GOOGLE_API_AVAILABLE:
        raise ImportError("Google API client not installed")
    
    creds_data = get_oauth_credentials(region_name)
    if not creds_data:
        raise ValueError("OAuth credentials not found in Secrets Manager")
    
    credentials = Credentials(
        token=None,  # Will be refreshed
        refresh_token=creds_data["refresh_token"],
        token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=creds_data["client_id"],
        client_secret=creds_data["client_secret"],
        scopes=YOUTUBE_ANALYTICS_SCOPES
    )
    
    # Build YouTube Analytics API client
    youtube_analytics = build("youtubeAnalytics", "v2", credentials=credentials)
    
    # Build YouTube Data API client (for video list)
    youtube_data = build("youtube", "v3", credentials=credentials)
    
    return youtube_analytics, youtube_data


# ============================================================================
# METRICS FETCHING
# ============================================================================

def get_channel_videos(youtube_data, max_results: int = 50) -> List[Dict]:
    """
    Get list of recent videos from the authenticated channel.
    """
    # Get uploads playlist ID
    channels_response = youtube_data.channels().list(
        part="contentDetails",
        mine=True
    ).execute()
    
    if not channels_response.get("items"):
        return []
    
    uploads_playlist_id = channels_response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    # Get videos from uploads playlist
    videos = []
    playlist_response = youtube_data.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=uploads_playlist_id,
        maxResults=max_results
    ).execute()
    
    for item in playlist_response.get("items", []):
        videos.append({
            "video_id": item["contentDetails"]["videoId"],
            "title": item["snippet"]["title"],
            "published_at": item["snippet"]["publishedAt"]
        })
    
    return videos


def get_video_metrics(youtube_analytics, video_id: str, days_back: int = 7) -> Dict:
    """
    Fetch analytics metrics for a specific video.
    
    Returns:
        {
            "views": int,
            "avg_view_duration_seconds": float,
            "avg_view_percentage": float,  # This is the key metric!
            "likes": int,
            "shares": int
        }
    """
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    
    try:
        response = youtube_analytics.reports().query(
            ids="channel==MINE",
            startDate=start_date,
            endDate=end_date,
            metrics="views,averageViewDuration,averageViewPercentage,likes,shares",
            dimensions="video",
            filters=f"video=={video_id}",
            sort="-views"
        ).execute()
        
        if response.get("rows"):
            row = response["rows"][0]
            return {
                "video_id": video_id,
                "views": row[1],
                "avg_view_duration_seconds": row[2],
                "avg_view_percentage": row[3],  # 0-100, key correlation metric
                "likes": row[4],
                "shares": row[5],
                "fetch_date": datetime.now().isoformat()
            }
        
        return {"video_id": video_id, "error": "no_data"}
        
    except Exception as e:
        return {"video_id": video_id, "error": str(e)}


# ============================================================================
# DYNAMODB OPERATIONS
# ============================================================================

def save_video_with_predictions(
    video_id: str,
    publish_time_utc: str,
    # Pipeline metadata
    pipeline_version: str = "2.3",
    mode: str = "quality",  # "fast" or "quality"
    # Predictions
    hook_score: float = 0.0,
    predicted_retention: float = 50.0,
    # Hook KPI breakdown
    instant_clarity: float = 5.0,
    curiosity_gap: float = 5.0,
    swipe_risk: float = 5.0,
    # Visual
    visual_relevance: float = 5.0,
    # Content tags
    era: str = "unknown",
    topic_entity: str = "unknown",
    # Distribution
    title_variant_type: str = "safe",  # "safe", "bold", "experimental"
    title_used: str = "",
    # AWS
    region_name: str = None
) -> bool:
    """
    Save video with full pipeline predictions for calibration analysis.
    
    This creates the baseline record. After 24-72 hours, analytics fetcher
    will update with actual_retention from YouTube.
    
    CALIBRATION FIELDS:
    - Predictions: predicted_retention, hook_score, instant_clarity, curiosity_gap, swipe_risk
    - Content: era, topic_entity, visual_relevance
    - Distribution: mode, title_variant_type
    - Results (filled later): actual_retention, analytics_fetched_at_utc
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        item = {
            # Identity
            "video_id": video_id,
            "publish_time_utc": publish_time_utc,
            
            # Pipeline metadata
            "pipeline_version": pipeline_version,
            "mode": mode,
            
            # Predictions (stored as strings for DynamoDB compatibility)
            "hook_score": str(hook_score),
            "predicted_retention": str(predicted_retention),
            
            # Hook KPI breakdown (for feature analysis)
            "instant_clarity": str(instant_clarity),
            "curiosity_gap": str(curiosity_gap),
            "swipe_risk": str(swipe_risk),
            
            # Visual alignment
            "visual_relevance": str(visual_relevance),
            
            # Content tags (for segmented analysis)
            "era": era,
            "topic_entity": topic_entity,
            
            # Distribution (for A/B analysis)
            "title_variant_type": title_variant_type,
            "title_used": title_used,
            
            # Results (filled by analytics fetcher)
            "actual_retention": None,
            "analytics_fetched_at_utc": None,
            
            # Retry tracking
            "status": "pending",
            "retry_count": 0
        }
        
        table.put_item(Item=item)
        print(f"[OK] Saved video {video_id} | mode={mode} | predicted={predicted_retention}% | era={era}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to save video metrics: {e}")
        return False


def update_with_actual_metrics(video_id: str, metrics: Dict, region_name: str = None) -> bool:
    """
    Update video record with actual YouTube metrics.
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET actual_retention = :ar, views = :v, avg_duration_s = :ad, fetch_date = :fd, #st = :s",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":ar": str(metrics.get("avg_view_percentage", 0)),
                ":v": str(metrics.get("views", 0)),
                ":ad": str(metrics.get("avg_view_duration_seconds", 0)),
                ":fd": datetime.now().isoformat(),
                ":s": "complete"
            }
        )
        print(f"✅ Updated video {video_id} with actual retention: {metrics.get('avg_view_percentage')}%")
        return True
    except Exception as e:
        print(f"❌ Failed to update video metrics: {e}")
        return False


def get_pending_videos(region_name: str = None) -> List[Dict]:
    """
    Get videos that need analytics fetching (status = pending).
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        response = table.scan(
            FilterExpression="#st = :s",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":s": "pending"}
        )
        return response.get("Items", [])
    except Exception as e:
        print(f"❌ Failed to get pending videos: {e}")
        return []


# ============================================================================
# MAIN FETCHER (Lambda Handler)
# ============================================================================

def fetch_all_pending_metrics(region_name: str = None) -> Dict:
    """
    Main function: Fetch metrics for all pending videos.
    Called by scheduled Lambda.
    
    Retry window:
    - <24 hours: Skip (analytics not ready)
    - 24-72 hours: Try to fetch, if no_data -> retry next run
    - >72 hours with no_data: Mark as failed (give up)
    """
    results = {"success": 0, "failed": 0, "skipped": 0, "retry_later": 0}
    
    try:
        youtube_analytics, youtube_data = build_youtube_client(region_name)
    except Exception as e:
        return {"error": str(e), "results": results}
    
    pending = get_pending_videos(region_name)
    print(f"[INFO] Found {len(pending)} pending videos")
    
    now = datetime.now()
    
    for video in pending:
        video_id = video["video_id"]
        upload_date = video.get("upload_date", "")
        retry_count = int(video.get("retry_count", 0))
        
        # Calculate video age
        hours_old = 0
        if upload_date:
            try:
                upload_dt = datetime.fromisoformat(upload_date.replace("Z", "+00:00"))
                # Handle timezone-aware/naive datetime comparison
                if upload_dt.tzinfo:
                    now_aware = datetime.now(upload_dt.tzinfo)
                    hours_old = (now_aware - upload_dt).total_seconds() / 3600
                else:
                    hours_old = (now - upload_dt).total_seconds() / 3600
            except:
                hours_old = 48  # Assume middle range if can't parse
        
        # Skip if less than 24 hours old
        if hours_old < 24:
            print(f"[SKIP] {video_id} - only {hours_old:.1f} hours old (need 24+)")
            results["skipped"] += 1
            continue
        
        # Fetch metrics
        metrics = get_video_metrics(youtube_analytics, video_id)
        
        if "error" not in metrics:
            # Success - update with actual metrics
            update_with_actual_metrics(video_id, metrics, region_name)
            results["success"] += 1
        elif metrics.get("error") == "no_data":
            # No data yet - check if we should retry or give up
            if hours_old < 72:
                # Within retry window - will try again next run
                print(f"[RETRY] {video_id} - no data yet ({hours_old:.1f}h old, retry #{retry_count+1})")
                increment_retry_count(video_id, region_name)
                results["retry_later"] += 1
            else:
                # Past retry window - mark as failed
                print(f"[FAIL] {video_id} - no data after 72+ hours, giving up")
                mark_as_failed(video_id, "no_data_after_72h", region_name)
                results["failed"] += 1
        else:
            # Other error
            print(f"[ERROR] {video_id}: {metrics['error']}")
            results["failed"] += 1
    
    return {"results": results}


def increment_retry_count(video_id: str, region_name: str = None):
    """Increment retry count for a video."""
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET retry_count = if_not_exists(retry_count, :zero) + :one",
            ExpressionAttributeValues={":zero": 0, ":one": 1}
        )
    except Exception as e:
        print(f"[WARNING] Failed to increment retry count: {e}")


def mark_as_failed(video_id: str, reason: str, region_name: str = None):
    """Mark a video as failed after exhausting retries."""
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        table.update_item(
            Key={"video_id": video_id},
            UpdateExpression="SET #st = :s, failure_reason = :r",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={":s": "failed", ":r": reason}
        )
    except Exception as e:
        print(f"[WARNING] Failed to mark video as failed: {e}")


def lambda_handler(event, context):
    """
    Lambda entry point for scheduled analytics fetching.
    """
    print("🚀 Starting YouTube Analytics Fetcher")
    
    region = os.environ.get("AWS_REGION_NAME", "us-east-1")
    result = fetch_all_pending_metrics(region)
    
    print(f"📊 Results: {json.dumps(result)}")
    return result
