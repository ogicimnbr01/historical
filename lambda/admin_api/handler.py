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
- POST /generate - Trigger on-demand video generation
- GET /jobs - List recent generation jobs
- GET /jobs/{id} - Get job details
- GET /logs - Get structured run logs for a job
"""

import json
import os
import boto3  # pyre-ignore[21]
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Dict, Any, List

# Config
METRICS_TABLE_NAME = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")
JOBS_TABLE_NAME = os.environ.get("JOBS_TABLE_NAME", "shorts_jobs")
RUN_LOGS_TABLE_NAME = os.environ.get("RUN_LOGS_TABLE_NAME", "shorts_run_logs")
RATE_LIMITS_TABLE_NAME = os.environ.get("RATE_LIMITS_TABLE_NAME", "shorts_rate_limits")
VIDEO_CREATOR_FUNC_NAME = os.environ.get("VIDEO_CREATOR_FUNC_NAME", "youtube-shorts-video-generator")
AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-east-1")
GSI_NAME = "gsi1_publish_time"
MAX_BULK_ITEMS = 50
GENERATE_RATE_LIMIT = 2  # Max 2 generates per minute per API key

# AWS Clients
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(METRICS_TABLE_NAME)
jobs_table = dynamodb.Table(JOBS_TABLE_NAME)
logs_table = dynamodb.Table(RUN_LOGS_TABLE_NAME)
rate_table = dynamodb.Table(RATE_LIMITS_TABLE_NAME)
lambda_client = boto3.client("lambda", region_name=AWS_REGION)


def lambda_handler(event, context):
    """Main handler for API Gateway requests."""
    print(f"[ADMIN_API] Event: {json.dumps(event)}")
    
    http_method = event.get("httpMethod", "GET")
    path = event.get("path", "/")
    path_params = event.get("pathParameters") or {}
    query_params = event.get("queryStringParameters") or {}
    body = event.get("body")
    
    # Extract API key for rate limiting (from header or context)
    api_key = event.get("requestContext", {}).get("identity", {}).get("apiKey", "unknown")
    
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
        
        # === NEW ENDPOINTS ===
        elif path == "/generate" and http_method == "POST":
            return generate_video(body, api_key)
        
        elif path == "/jobs" and http_method == "GET":
            return list_jobs(query_params)
        
        elif path.startswith("/jobs/") and http_method == "GET":
            job_id = path_params.get("id") or path.split("/")[-1]
            return get_job(job_id)
        
        elif path.startswith("/jobs/") and http_method == "DELETE":
            job_id = path_params.get("id") or path.split("/")[-1]
            return delete_job(job_id)
        
        elif path == "/logs" and http_method == "GET":
            return get_logs(query_params)
        
        else:
            return response(404, {"error": "Not found"})
    
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return response(500, {"error": str(e)})


def response(status_code: int, body: Dict) -> Dict:
    """Create API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Api-Key,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS"
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
        "eligible_rate": round(eligible / total * 100, 1) if total > 0 else 0,  # pyre-ignore[6]
        "mae": round(mae, 2) if mae else None,  # pyre-ignore[6]
        "correlation": round(correlation, 3) if correlation else None,  # pyre-ignore[6]
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

def parse_youtube_url(url_or_id: str) -> str:  # pyre-ignore[3]
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
        return None  # pyre-ignore[7]
    
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
    
    return None  # pyre-ignore[7]


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
            # Auto-update status to linked if currently pending/test/failed
            if updates.get("status") is None:
                updates["status"] = "linked"
                updates["_auto_linked"] = True  # Flag: status was auto-set, not explicit
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
    
    # If status was AUTO-SET to "linked" (from YouTube URL linking), only apply
    # if current status allows it (pending, test, failed). If user explicitly
    # chose "linked" via saveVideoChanges(), always respect their choice.
    if "status" in safe_updates and safe_updates["status"] == "linked":
        is_auto_linked = updates.get("_auto_linked", False)
        if is_auto_linked:
            # Auto-linked: allow from pending, test, and failed
            if current.get("status") not in ("pending", "test", "failed", None, ""):
                del safe_updates["status"]  # pyre-ignore[16]
        # else: user explicitly set status to "linked" — always allow
    
    # Remove internal flag before processing
    safe_updates.pop("_auto_linked", None)
    
    # When transitioning TO linked or pending, clean up test-mode fields
    if safe_updates.get("status") in ("linked", "pending"):
        # Restore calibration eligibility unless explicitly set
        if "calibration_eligible" not in safe_updates:
            safe_updates["calibration_eligible"] = True
        # Clear invalid_reason unless explicitly set
        if "invalid_reason" not in safe_updates:
            safe_updates["invalid_reason"] = None
    
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
                results["failed"].append({"video_id": video_id, "error": "Update failed"})  # pyre-ignore[6]
        except Exception as e:
            results["failed"].append({"video_id": video_id, "error": str(e)})  # pyre-ignore[6]
    
    return response(200, results)


# ============================================================================
# POST /generate - Trigger on-demand video generation
# ============================================================================
def check_rate_limit(api_key: str) -> bool:
    """
    Check if API key is within rate limit (2 generates per minute).
    Uses atomic DynamoDB update with condition expression.
    Returns True if request is allowed, False if rate limited.
    """
    # Create minute bucket key
    minute_bucket = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    pk = f"rate#generate#{api_key}#{minute_bucket}"
    
    try:
        # Try atomic increment with condition
        rate_table.update_item(
            Key={"pk": pk},
            UpdateExpression="SET #count = if_not_exists(#count, :zero) + :one, expires_at = :ttl",
            ConditionExpression="attribute_not_exists(#count) OR #count < :limit",
            ExpressionAttributeNames={"#count": "count"},
            ExpressionAttributeValues={
                ":zero": 0,
                ":one": 1,
                ":limit": GENERATE_RATE_LIMIT,
                ":ttl": int((datetime.now(timezone.utc) + timedelta(minutes=2)).timestamp())
            }
        )
        return True
    except dynamodb.meta.client.exceptions.ConditionalCheckFailedException:
        return False


def check_idempotency(client_request_id: str):  # pyre-ignore[3]
    """
    Check if a request with same client_request_id already exists.
    Returns existing job if found, None otherwise.
    """
    if not client_request_id:
        return None  # pyre-ignore[7]
    
    try:
        # Query jobs table for matching client_request_id
        result = jobs_table.query(
            IndexName="by_date",
            KeyConditionExpression="gsi1pk = :pk",
            FilterExpression="client_request_id = :crid",
            ExpressionAttributeValues={
                ":pk": "JOBS",
                ":crid": client_request_id
            },
            Limit=1
        )
        items = result.get("Items", [])
        if items:
            return decimal_to_float(items[0])
    except Exception as e:
        print(f"[WARN] Idempotency check failed: {e}")
    
    return None  # pyre-ignore[7]


def generate_video(body: Dict, api_key: str) -> Dict:
    """
    Trigger on-demand video generation.
    
    Body params:
    - mode: auto/quality/fast (default: auto)
    - title_variant: auto/bold/safe/experimental (default: auto)
    - topic_override: optional custom topic
    - calibration_eligible: bool (default: true)
    - mark_as_test: bool (default: false, sets eligible=false + status=test)
    - client_request_id: optional UUID for idempotency
    """
    # Check rate limit
    if not check_rate_limit(api_key):
        return response(429, {
            "error": "Rate limit exceeded",
            "message": f"Max {GENERATE_RATE_LIMIT} generate requests per minute"
        })
    
    # Check idempotency
    client_request_id = body.get("client_request_id")
    existing = check_idempotency(client_request_id)  # pyre-ignore[6]
    if existing:
        print(f"[IDEMPOTENCY] Returning existing job for client_request_id={client_request_id}")
        return response(200, {
            "job_id": existing["job_id"],
            "status": existing["status"],
            "message": "Existing job returned (idempotent)"
        })
    
    # Parse parameters
    mode = body.get("mode", "auto")
    title_variant = body.get("title_variant", "auto")
    topic_override = body.get("topic_override")
    mark_as_test = body.get("mark_as_test", False)
    calibration_eligible = False if mark_as_test else body.get("calibration_eligible", True)
    
    # Generate job ID
    job_id = f"job_{uuid.uuid4().hex[:12]}"  # pyre-ignore[16]
    requested_at = datetime.now(timezone.utc).isoformat()
    expires_at = int((datetime.now(timezone.utc) + timedelta(days=30)).timestamp())
    
    # Create job record
    job_item = {
        "job_id": job_id,
        "gsi1pk": "JOBS",
        "requested_at_utc": requested_at,
        "requested_by": "admin",
        "status": "queued",
        "params": {
            "mode": mode,
            "title_variant": title_variant,
            "topic_override": topic_override,
            "calibration_eligible": calibration_eligible,
            "mark_as_test": mark_as_test
        },
        "expires_at": expires_at
    }
    
    if client_request_id:
        job_item["client_request_id"] = client_request_id
    
    jobs_table.put_item(Item=job_item)
    print(f"[GENERATE] Created job {job_id}")
    
    # Prepare Lambda payload
    lambda_payload = {
        "job_id": job_id,
        "mode": mode,
        "title_variant": title_variant,
        "calibration_eligible": calibration_eligible,
        "mark_as_test": mark_as_test
    }
    
    if topic_override:
        lambda_payload["topic"] = topic_override
    
    # Force mode if not auto
    if mode == "quality":
        lambda_payload["force_mode"] = "QUALITY"
    elif mode == "fast":
        lambda_payload["force_mode"] = "FAST"
    
    # Async invoke video creator Lambda
    try:
        lambda_client.invoke(
            FunctionName=VIDEO_CREATOR_FUNC_NAME,
            InvocationType="Event",  # Async
            Payload=json.dumps(lambda_payload)
        )
        print(f"[GENERATE] Async invoked {VIDEO_CREATOR_FUNC_NAME} for job {job_id}")
    except Exception as e:
        # Update job status to failed if invoke fails
        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #status = :status, error_message = :err",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": "failed",
                ":err": f"Lambda invoke failed: {str(e)}"
            }
        )
        print(f"[ERROR] Failed to invoke Lambda: {e}")
        return response(500, {"error": "Failed to start video generation", "job_id": job_id})
    
    return response(200, {
        "job_id": job_id,
        "status": "queued",
        "message": "Video generation started"
    })


# ============================================================================
# GET /jobs - List recent generation jobs
# ============================================================================
def list_jobs(query_params: Dict) -> Dict:
    """
    List recent jobs with optional filters.
    
    Query params:
    - limit: max results (default: 50)
    - status: filter by status (queued/running/completed/failed)
    - from_date: ISO date string
    """
    limit = int(query_params.get("limit", 50))
    status_filter = query_params.get("status")
    from_date = query_params.get("from_date")
    
    if not from_date:
        from_date = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    
    # Query GSI by date
    result = jobs_table.query(
        IndexName="by_date",
        KeyConditionExpression="gsi1pk = :pk AND requested_at_utc >= :from_date",
        ExpressionAttributeValues={
            ":pk": "JOBS",
            ":from_date": from_date
        },
        ScanIndexForward=False,  # Newest first
        Limit=limit * 2  # Extra for filtering
    )
    
    items = result.get("Items", [])
    
    # Apply status filter
    if status_filter:
        items = [i for i in items if i.get("status") == status_filter]
    
    # Limit results
    items = items[:limit]  # pyre-ignore[16]
    
    return response(200, {
        "jobs": [decimal_to_float(i) for i in items],
        "count": len(items)
    })


# ============================================================================
# GET /jobs/{id} - Get job details
# ============================================================================
def get_job(job_id: str) -> Dict:
    """Get single job by ID."""
    result = jobs_table.get_item(Key={"job_id": job_id})
    
    item = result.get("Item")
    if not item:
        return response(404, {"error": "Job not found"})
    
    return response(200, decimal_to_float(item))


# ============================================================================
# GET /logs - Get structured run logs
# ============================================================================
def get_logs(query_params: Dict) -> Dict:
    """
    Get structured run logs for a job.
    
    Query params:
    - job_id: required - the job to get logs for
    - component: optional filter (video_generator/analytics_fetcher/decision_engine)
    - level: optional filter (INFO/WARN/ERROR)
    - limit: max results (default: 100)
    """
    job_id = query_params.get("job_id")
    if not job_id:
        return response(400, {"error": "job_id is required"})
    
    component_filter = query_params.get("component")
    level_filter = query_params.get("level")
    limit = int(query_params.get("limit", 100))
    
    # Query logs by job_id (pk)
    result = logs_table.query(
        KeyConditionExpression="pk = :job_id",
        ExpressionAttributeValues={
            ":job_id": job_id
        },
        ScanIndexForward=True,  # Oldest first (chronological)
        Limit=limit * 2  # Extra for filtering
    )
    
    items = result.get("Items", [])
    
    # Apply filters
    if component_filter:
        items = [i for i in items if i.get("component") == component_filter]
    if level_filter:
        items = [i for i in items if i.get("level") == level_filter]
    
    # Limit results
    items = items[:limit]  # pyre-ignore[16]
    
    return response(200, {
        "job_id": job_id,
        "logs": [decimal_to_float(i) for i in items],
        "count": len(items)
    })


# ============================================================================
# DELETE /jobs/{id} - Delete job and its logs
# ============================================================================
def delete_job(job_id: str) -> Dict:
    """Delete a job and all its associated logs."""
    try:
        # 1. Delete job record
        jobs_table.delete_item(Key={"job_id": job_id})
        
        # 2. Delete associated logs (Batch delete)
        # Query all logs for this job
        logs = logs_table.query(
            KeyConditionExpression="pk = :job_id",
            ExpressionAttributeValues={":job_id": job_id}
        )
        
        items = logs.get("Items", [])
        if items:
            with logs_table.batch_writer() as batch:
                for item in items:
                    batch.delete_item(Key={
                        "pk": item["pk"],
                        "sk": item["sk"]
                    })
        
        return response(200, {"message": "Job deleted", "logs_deleted": len(items)})
        
    except Exception as e:
        print(f"[ERROR] Failed to delete job {job_id}: {str(e)}")
        return response(500, {"error": str(e)})
