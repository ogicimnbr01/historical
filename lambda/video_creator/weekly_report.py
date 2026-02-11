"""
Weekly Performance Report
=========================
Generates weekly summary of video performance metrics.
Triggered by EventBridge every Sunday at 20:00 UTC.

Report includes:
- Total eligible & complete videos
- Average predicted vs actual retention
- MAE (Mean Absolute Error)
- Top 3 / Bottom 3 by actual retention
- Mode comparison (FAST vs QUALITY)
"""

import json
import os
import boto3  # pyre-ignore[21]: third-party module without configured stubs
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional


# Configuration
METRICS_TABLE_NAME = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")


def lambda_handler(event, context):
    """
    Lambda entry point for weekly report generation.
    """
    print("[WEEKLY_REPORT] Starting weekly performance report...")
    
    region = os.environ.get("AWS_REGION_NAME", "us-east-1")
    
    try:
        report = generate_weekly_report(region)
        send_report_notification(report, region)
        return {"statusCode": 200, "body": json.dumps(report)}
    except Exception as e:
        print(f"[ERROR] Weekly report failed: {e}")
        return {"statusCode": 500, "body": str(e)}


def generate_weekly_report(region_name: Optional[str] = None) -> Dict:
    """
    Generate weekly performance report from DynamoDB data.
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    # Calculate date range (last 7 days)
    now = datetime.now()
    week_ago = now - timedelta(days=7)
    
    # Scan for complete, eligible videos
    response = table.scan(
        FilterExpression="calibration_eligible = :eligible AND #st = :status",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":eligible": True,
            ":status": "complete"
        }
    )
    
    videos = response.get("Items", [])
    
    # Filter to last 7 days (by analytics_fetched_at_utc)
    weekly_videos = []
    for video in videos:
        fetch_date = video.get("analytics_fetched_at_utc", "")
        if fetch_date:
            try:
                fetch_dt = datetime.fromisoformat(fetch_date.replace("Z", "+00:00"))
                if fetch_dt.replace(tzinfo=None) >= week_ago:
                    weekly_videos.append(video)
            except:
                pass
    
    # If no weekly videos, use all videos
    if not weekly_videos:
        weekly_videos = videos
    
    # Calculate metrics
    n = len(weekly_videos)
    
    if n == 0:
        return {
            "n": 0,
            "message": "No complete videos in the selected period"
        }
    
    # Extract predicted and actual values
    data = []
    for v in weekly_videos:
        try:
            predicted = float(v.get("predicted_retention", 0))
            actual = float(v.get("actual_retention", 0))
            data.append({
                "video_id": v.get("video_id"),
                "title_used": v.get("title_used", "N/A"),
                "topic_entity": v.get("topic_entity", "N/A"),
                "era": v.get("era", "N/A"),
                "mode": v.get("mode", "N/A"),
                "predicted": predicted,
                "actual": actual,
                "error": abs(predicted - actual)
            })
        except:
            pass
    
    if not data:
        return {"n": 0, "message": "Could not parse video data"}
    
    # Calculate averages
    avg_predicted = float(sum(d["predicted"] for d in data)) / len(data)
    avg_actual = float(sum(d["actual"] for d in data)) / len(data)
    mae = float(sum(d["error"] for d in data)) / len(data)
    
    # Sort by actual retention
    sorted_by_actual = sorted(data, key=lambda x: x["actual"], reverse=True)
    top_3 = list(sorted_by_actual[:3])  # pyre-ignore[16]
    bottom_3 = list(sorted_by_actual[-3:]) if len(sorted_by_actual) >= 3 else list(sorted_by_actual)  # pyre-ignore[16]
    
    # Mode comparison
    quality_videos = [d for d in data if str(d["mode"]).lower() == "quality"]
    fast_videos = [d for d in data if str(d["mode"]).lower() == "fast"]
    
    quality_avg = float(sum(d["actual"] for d in quality_videos)) / len(quality_videos) if quality_videos else 0
    fast_avg = float(sum(d["actual"] for d in fast_videos)) / len(fast_videos) if fast_videos else 0
    
    # Entity/Era distribution
    entity_performance = {}
    era_performance = {}
    
    for d in data:
        entity = d["topic_entity"]
        era = d["era"]
        
        if entity not in entity_performance:
            entity_performance[entity] = []
        entity_performance[entity].append(d["actual"])
        
        if era not in era_performance:
            era_performance[era] = []
        era_performance[era].append(d["actual"])
    
    # Average by entity/era
    entity_avg = {k: float(sum(v))/len(v) for k, v in entity_performance.items()}
    era_avg = {k: float(sum(v))/len(v) for k, v in era_performance.items()}
    
    # Top/bottom entities
    sorted_entities = sorted(entity_avg.items(), key=lambda x: x[1], reverse=True)
    sorted_eras = sorted(era_avg.items(), key=lambda x: x[1], reverse=True)
    
    report = {
        "period": f"{week_ago.strftime('%Y-%m-%d')} to {now.strftime('%Y-%m-%d')}",
        "n": n,
        "avg_predicted": round(float(avg_predicted), 1),  # pyre-ignore[6]
        "avg_actual": round(float(avg_actual), 1),  # pyre-ignore[6]
        "mae": round(float(mae), 1),  # pyre-ignore[6]
        "top_3": top_3,
        "bottom_3": bottom_3,
        "mode_comparison": {
            "QUALITY": {"n": len(quality_videos), "avg_actual": round(float(quality_avg), 1)},  # pyre-ignore[6]
            "FAST": {"n": len(fast_videos), "avg_actual": round(float(fast_avg), 1)}  # pyre-ignore[6]
        },
        "top_entities": list(sorted_entities[:3]),  # pyre-ignore[16]
        "bottom_entities": list(sorted_entities[-3:]) if len(sorted_entities) >= 3 else [],  # pyre-ignore[16]
        "top_eras": list(sorted_eras[:3]),  # pyre-ignore[16]
        "bottom_eras": list(sorted_eras[-3:]) if len(sorted_eras) >= 3 else []  # pyre-ignore[16]
    }
    
    return report


def send_report_notification(report: Dict, region_name: Optional[str] = None):
    """
    Send weekly report via SNS.
    """
    if not SNS_TOPIC_ARN:
        print("⚠️ SNS_TOPIC_ARN not set, skipping weekly report notification")
        return
    
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    sns = boto3.client("sns", region_name=region)
    
    # Build message
    n = report.get("n", 0)
    
    if n == 0:
        message = f"""📊 WEEKLY PERFORMANCE REPORT
Period: {report.get('period', 'N/A')}

No complete videos in this period.
"""
    else:
        # Format top/bottom 3
        top_3_str = "\n".join([
            f"   • {v['title_used'][:35]}: {v['actual']:.0f}%" 
            for v in report.get("top_3", [])
        ])
        bottom_3_str = "\n".join([
            f"   • {v['title_used'][:35]}: {v['actual']:.0f}%" 
            for v in report.get("bottom_3", [])
        ])
        
        # Mode comparison
        mode = report.get("mode_comparison", {})
        quality = mode.get("QUALITY", {})
        fast = mode.get("FAST", {})
        
        # Entity/Era top performers
        top_entities = report.get("top_entities", [])
        top_entities_str = ", ".join([f"{e[0]}({e[1]:.0f}%)" for e in top_entities[:3]])
        
        bottom_entities = report.get("bottom_entities", [])
        bottom_entities_str = ", ".join([f"{e[0]}({e[1]:.0f}%)" for e in bottom_entities[-3:]])
        
        message = f"""📊 WEEKLY PERFORMANCE REPORT
Period: {report.get('period', 'N/A')}

📈 SUMMARY (n={n})
   Avg Predicted: {report.get('avg_predicted', 0)}%
   Avg Actual:    {report.get('avg_actual', 0)}%
   MAE:           {report.get('mae', 0)}%

🏆 TOP 3 PERFORMERS
{top_3_str}

📉 BOTTOM 3 PERFORMERS
{bottom_3_str}

🎬 MODE COMPARISON
   QUALITY: n={quality.get('n', 0)}, avg={quality.get('avg_actual', 0)}%
   FAST:    n={fast.get('n', 0)}, avg={fast.get('avg_actual', 0)}%

👤 TOP ENTITIES: {top_entities_str}
👤 BOTTOM ENTITIES: {bottom_entities_str}

---
Recommendation:
• Focus on high-performing entities/eras
• Review bottom performers for pattern insights
• Compare QUALITY vs FAST mode results
"""
    
    try:
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Subject=f"📊 Weekly Report: n={n}, avg={report.get('avg_actual', 0):.0f}%",
            Message=message
        )
        print(f"📧 Weekly report sent (n={n})")
    except Exception as e:
        print(f"⚠️ Failed to send weekly report: {e}")


if __name__ == "__main__":
    # Test locally
    print("Testing weekly report...")
    report = generate_weekly_report()
    print(json.dumps(report, indent=2, default=str))
