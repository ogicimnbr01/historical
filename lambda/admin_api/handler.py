"""
Calibration Admin Panel API
============================
CRUD operations for managing video metrics calibration data.

Endpoints:
- GET /videos - List videos with filters (uses GSI for efficiency)
- GET /videos/{id} - Get single video
- PATCH /videos/{id} - Update video fields (with audit log)
- POST /videos/bulk - Bulk update (max 50)
- GET /stats - Dashboard statistics
"""

import json
import os
import boto3
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List

# Config
METRICS_TABLE_NAME = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")
GSI_NAME = "gsi1_publish_time"
MAX_BULK_ITEMS = 50

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(METRICS_TABLE_NAME)


def lambda_handler(event, context):
    """Main handler for API Gateway requests."""
    print(f"[ADMIN_API] Event: {json.dumps(event)}")
    
    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}
    body = event.get("body")
    
    if body:
        try:
            body = json.loads(body)
        except:
            body = {}
    else:
        body = {}
    
    try:
        # Route requests
        if path == "/stats" and http_method == "GET":
            return get_stats()
        
        elif path == "/videos" and http_method == "GET":
            return list_videos(query_params)
        
        elif path == "/videos/bulk" and http_method == "POST":
            return bulk_update(body)
        
        elif path.startswith("/videos/") and http_method == "GET":
            video_id = path_params.get("id") or path.split("/")[-1]
            return get_video(video_id)
        
        elif path.startswith("/videos/") and http_method == "PATCH":
            video_id = path_params.get("id") or path.split("/")[-1]
            return update_video(video_id, body)
        
        elif path.startswith("/videos/") and http_method == "DELETE":
            video_id = path_params.get("id") or path.split("/")[-1]
            return delete_video(video_id)
        
        else:
            return response(404, {"error": "Not found"})
    
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return response(500, {"error": str(e)})


def response(status_code: int, body: Dict) -> Dict:
    """Create API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Api-Key,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS"
        },
        "body": json.dumps(body, default=str)
    }


def decimal_to_float(obj):
    """Convert DynamoDB Decimals to floats."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_float(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_float(i) for i in obj]
    return obj


# ============================================================================
# GET /stats - Dashboard statistics
# ============================================================================
def get_stats() -> Dict:
    """Get dashboard statistics."""
    # Get last 30 days of data
    cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    
    result = table.query(
        IndexName=GSI_NAME,
        KeyConditionExpression="gsi1pk = :pk AND publish_time_utc >= :cutoff",
        ExpressionAttributeValues={
            ":pk": "VIDEOS",
            ":cutoff": cutoff
        }
    )
    
    items = result.get("Items", [])
    
    # Calculate stats
    total = len(items)
    eligible = sum(1 for i in items if i.get("calibration_eligible") is True)
    pending = sum(1 for i in items if i.get("status") == "pending")
    complete = sum(1 for i in items if i.get("status") == "complete")
    failed = sum(1 for i in items if i.get("status") == "failed")
    test = sum(1 for i in items if i.get("status") == "test")
    fallback_count = sum(1 for i in items if i.get("pipeline_executed") == "fallback")
    
    # Calculate MAE and correlation for complete + eligible videos
    eligible_complete = [
        i for i in items 
        if i.get("calibration_eligible") is True 
        and i.get("status") == "complete"
        and i.get("actual_retention") is not None
    ]
    
    mae = None
    correlation = None
    
    if len(eligible_complete) >= 3:
        predicted = [float(i.get("predicted_retention", 50)) for i in eligible_complete]
        actual = [float(i.get("actual_retention", 0)) for i in eligible_complete]
        
        # MAE
        mae = sum(abs(p - a) for p, a in zip(predicted, actual)) / len(predicted)
        
        # Simple correlation
        n = len(predicted)
        mean_p = sum(predicted) / n
        mean_a = sum(actual) / n
        
        num = sum((p - mean_p) * (a - mean_a) for p, a in zip(predicted, actual))
        den_p = sum((p - mean_p) ** 2 for p in predicted)
        den_a = sum((a - mean_a) ** 2 for a in actual)
        
        if den_p > 0 and den_a > 0:
            correlation = num / ((den_p * den_a) ** 0.5)
    
    stats = {
        "total": total,
        "eligible": eligible,
        "pending": pending,
        "complete": complete,
        "failed": failed,
        "test": test,
        "fallback_count": fallback_count,
        "eligible_rate": round(eligible / total * 100, 1) if total > 0 else 0,
        "mae": round(mae, 2) if mae else None,
        "correlation": round(correlation, 3) if correlation else None,
        "sample_size_for_metrics": len(eligible_complete)
    }
    
    return response(200, stats)


# ============================================================================
# GET /videos - List videos with filters
# ============================================================================
def list_videos(query_params: Dict) -> Dict:
    """List videos with filters. Uses GSI for date-range queries."""
    
    # Date range
    from_date = query_params.get("from_date")
    to_date = query_params.get("to_date")
    limit = int(query_params.get("limit", 50))
    
    # Default: last 30 days
    if not from_date:
        from_date = (datetime.now() - timedelta(days=30)).isoformat()
    if not to_date:
        to_date = datetime.now().isoformat()
    
    # Query GSI
    result = table.query(
        IndexName=GSI_NAME,
        KeyConditionExpression="gsi1pk = :pk AND publish_time_utc BETWEEN :from AND :to",
        ExpressionAttributeValues={
            ":pk": "VIDEOS",
            ":from": from_date,
            ":to": to_date
        },
        ScanIndexForward=False,  # Newest first
        Limit=limit * 2  # Get extra for filtering
    )
    
    items = result.get("Items", [])
    
    # Apply filters
    status_filter = query_params.get("status")
    eligible_filter = query_params.get("eligible")
    mode_filter = query_params.get("mode")
    fallback_filter = query_params.get("fallback")
    
    filtered = []
    for item in items:
        if status_filter and item.get("status") != status_filter:
            continue
        if eligible_filter is not None:
            is_eligible = item.get("calibration_eligible") is True
            if eligible_filter == "true" and not is_eligible:
                continue
            if eligible_filter == "false" and is_eligible:
                continue
        if mode_filter and item.get("mode") != mode_filter:
            continue
        if fallback_filter is not None:
            is_fallback = item.get("pipeline_executed") == "fallback"
            if fallback_filter == "true" and not is_fallback:
                continue
            if fallback_filter == "false" and is_fallback:
                continue
        
        filtered.append(item)
        if len(filtered) >= limit:
            break
    
    # Clean up for JSON response
    cleaned = [decimal_to_float(i) for i in filtered]
    
    return response(200, {
        "videos": cleaned,
        "count": len(cleaned),
        "filters_applied": {
            "from_date": from_date,
            "to_date": to_date,
            "status": status_filter,
            "eligible": eligible_filter,
            "mode": mode_filter,
            "fallback": fallback_filter
        }
    })


# ============================================================================
# GET /videos/{id} - Get single video
# ============================================================================
def get_video(video_id: str) -> Dict:
    """Get single video by ID."""
    result = table.get_item(Key={"video_id": video_id})
    
    item = result.get("Item")
    if not item:
        return response(404, {"error": "Video not found"})
    
    return response(200, decimal_to_float(item))


# ============================================================================
# PATCH /videos/{id} - Update video with audit log
# ============================================================================

def parse_youtube_url(url_or_id: str) -> str:
    """
    Extract YouTube video ID from URL or return the ID if already an ID.
    
    Handles:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://youtube.com/shorts/VIDEO_ID
    - VIDEO_ID (11 chars)
    """
    import re
    
    if not url_or_id:
        return None
    
    url_or_id = url_or_id.strip()
    
    # Already a video ID (11 chars alphanumeric with - and _)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
        return url_or_id
    
    # youtube.com/watch?v=VIDEO_ID
    match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url_or_id)
    if match:
        return match.group(1)
    
    # youtu.be/VIDEO_ID
    match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url_or_id)
    if match:
        return match.group(1)
    
    # youtube.com/shorts/VIDEO_ID
    match = re.search(r'shorts/([a-zA-Z0-9_-]{11})', url_or_id)
    if match:
        return match.group(1)
    
    return None


def update_video(video_id: str, updates: Dict) -> Dict:
    """Update video fields with audit logging."""
    
    # Allowed fields to update
    allowed_fields = [
        "calibration_eligible",
        "status",
        "invalid_reason",
        "notes",
        "youtube_video_id",
        "youtube_url"
    ]
    
    # Handle YouTube URL/ID linking
    if "youtube_url" in updates or "youtube_video_id" in updates:
        youtube_input = updates.get("youtube_url") or updates.get("youtube_video_id")
        parsed_id = parse_youtube_url(youtube_input)
        
        if parsed_id:
            updates["youtube_video_id"] = parsed_id
            updates["youtube_url"] = f"https://www.youtube.com/shorts/{parsed_id}"
            # Auto-update status to linked if currently pending
            if updates.get("status") is None:
                updates["status"] = "linked"
        else:
            return response(400, {"error": "Invalid YouTube URL or video ID"})
    
    # Filter to only allowed fields
    safe_updates = {k: v for k, v in updates.items() if k in allowed_fields}
    
    if not safe_updates:
        return response(400, {"error": "No valid fields to update"})
    
    # Get current values for audit log
    current = table.get_item(Key={"video_id": video_id}).get("Item", {})
    if not current:
        return response(404, {"error": "Video not found"})
    
    # If status update to "linked" was auto-set, only apply if current status is pending
    if "status" in safe_updates and safe_updates["status"] == "linked":
        if current.get("status") not in ("pending", None, ""):
            # Keep existing status if not pending
            del safe_updates["status"]
    
    # Build update expression
    update_expr = "SET "
    expr_values = {}
    expr_names = {}
    
    audit_changes = []
    
    for field, new_value in safe_updates.items():
        old_value = current.get(field)
        
        expr_names[f"#{field}"] = field
        expr_values[f":{field}"] = new_value
        update_expr += f"#{field} = :{field}, "
        
        # Audit log entry
        if old_value != new_value:
            audit_changes.append({
                "field": field,
                "old": old_value,
                "new": new_value
            })
    
    # Add updated_at
    update_expr += "updated_at = :updated_at"
    expr_values[":updated_at"] = datetime.now().isoformat()
    
    # Perform update
    table.update_item(
        Key={"video_id": video_id},
        UpdateExpression=update_expr,
        ExpressionAttributeNames=expr_names,
        ExpressionAttributeValues=expr_values
    )
    
    # Audit log to CloudWatch
    if audit_changes:
        print(f"[AUDIT] video_id={video_id} changes={json.dumps(audit_changes)} user=admin timestamp={datetime.now().isoformat()}")
    
    return response(200, {
        "video_id": video_id,
        "updated": list(safe_updates.keys()),
        "audit": audit_changes
    })


# ============================================================================
# DELETE /videos/{id} - Delete video
# ============================================================================
def delete_video(video_id: str) -> Dict:
    """Delete video from DynamoDB. Only allows deletion of non-eligible or test videos."""
    
    # Get current video to check if safe to delete
    current = table.get_item(Key={"video_id": video_id}).get("Item", {})
    if not current:
        return response(404, {"error": "Video not found"})
    
    # Safety check - only allow deletion of ineligible or test videos
    is_eligible = current.get("calibration_eligible") is True
    status = current.get("status", "")
    
    if is_eligible and status == "complete":
        return response(400, {
            "error": "Cannot delete eligible completed videos. Mark as ineligible first."
        })
    
    # Delete the video
    table.delete_item(Key={"video_id": video_id})
    
    # Audit log
    print(f"[AUDIT] DELETED video_id={video_id} status={status} eligible={is_eligible} timestamp={datetime.now().isoformat()}")
    
    return response(200, {
        "video_id": video_id,
        "deleted": True
    })


# ============================================================================
# POST /videos/bulk - Bulk update
# ============================================================================
def bulk_update(body: Dict) -> Dict:
    """Bulk update videos (max 50)."""
    
    video_ids = body.get("video_ids", [])
    updates = body.get("updates", {})
    
    if not video_ids:
        return response(400, {"error": "No video_ids provided"})
    
    if len(video_ids) > MAX_BULK_ITEMS:
        return response(400, {"error": f"Max {MAX_BULK_ITEMS} items per request"})
    
    # Shortcut for "Mark as TEST"
    if body.get("action") == "mark_as_test":
        updates = {
            "calibration_eligible": False,
            "status": "test",
            "invalid_reason": "test_run"
        }
    
    if not updates:
        return response(400, {"error": "No updates provided"})
    
    # Process each video
    results = {"success": [], "failed": []}
    
    for video_id in video_ids:
        try:
            result = update_video(video_id, updates)
            if result["statusCode"] == 200:
                results["success"].append(video_id)
            else:
                results["failed"].append({"video_id": video_id, "error": "Update failed"})
        except Exception as e:
            results["failed"].append({"video_id": video_id, "error": str(e)})
    
    return response(200, results)
