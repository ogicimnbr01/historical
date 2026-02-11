"""
Metrics Correlator v2
Analyzes correlation between pipeline predictions and actual YouTube performance.
Now with feature-level analysis, MAE calculation, and mode segmentation.
"""

import json
import os
import boto3  # pyre-ignore[21]: third-party module without configured stubs
from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta

METRICS_TABLE_NAME = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")


def get_completed_videos(days_back: int = 30, region_name: Optional[str] = None) -> List[Dict]:
    """Get videos with both predicted and actual metrics.
    
    IMPORTANT: Only returns calibration_eligible=True videos.
    Fallback runs are excluded to prevent data pollution.
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    try:
        scan_kwargs = {
            "FilterExpression": "#st = :s",
            "ExpressionAttributeNames": {"#st": "status"},
            "ExpressionAttributeValues": {":s": "complete"},
        }
        
        cutoff = (datetime.now() - timedelta(days=days_back)).isoformat()
        items = []
        excluded_count: int = 0
        
        # Paginate through all results
        while True:
            response = table.scan(**scan_kwargs)
            
            for item in response.get("Items", []):
                # Date filter
                if item.get("publish_time_utc", item.get("upload_date", "")) < cutoff:
                    continue
                
                # CRITICAL: Skip fallback runs (calibration_eligible=False)
                # These have mismatched predictions vs published content
                if item.get("calibration_eligible") is False:
                    excluded_count += 1  # pyre-ignore[58]: Pyre2 loses int type through while-True branches
                    continue
                    
                items.append(item)
            
            # Check if there are more pages
            if "LastEvaluatedKey" in response:
                scan_kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]
            else:
                break
        
        if excluded_count > 0:
            print(f"[INFO] Excluded {excluded_count} ineligible videos (fallback runs)")
        
        return items
    except Exception as e:
        print(f"[ERROR] Failed to get completed videos: {e}")
        return []


def safe_float(value, default=0.0) -> float:
    """Safely convert value to float."""
    try:
        return float(value) if value is not None else default
    except (ValueError, TypeError):
        return default


def calculate_pearson_correlation(x: List[float], y: List[float]) -> float:
    """Calculate Pearson correlation coefficient."""
    n = len(x)
    if n < 3 or n != len(y):
        return 0.0
    
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    
    numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
    sum_sq_x = sum((xi - mean_x) ** 2 for xi in x)
    sum_sq_y = sum((yi - mean_y) ** 2 for yi in y)
    
    denominator = (sum_sq_x * sum_sq_y) ** 0.5
    
    return numerator / denominator if denominator != 0 else 0.0


def calculate_mae(predicted: List[float], actual: List[float]) -> float:
    """Calculate Mean Absolute Error."""
    if len(predicted) != len(actual) or len(predicted) == 0:
        return 0.0
    return sum(abs(p - a) for p, a in zip(predicted, actual)) / len(predicted)


def analyze_correlations(region_name: Optional[str] = None) -> Dict:
    """
    Comprehensive correlation analysis with:
    - Overall correlation
    - MAE (Mean Absolute Error)
    - Mode-based segmentation (fast vs quality)
    - Feature-level analysis
    """
    videos = get_completed_videos(days_back=30, region_name=region_name)
    
    if len(videos) < 5:
        return {
            "sample_size": len(videos),
            "error": "Need at least 5 videos for correlation analysis",
            "correlations": {},
            "mae": None,
            "insights": [],
            "rubric_adjustments": []
        }
    
    # Extract all data points
    data = {
        "predicted_retention": [],
        "actual_retention": [],
        "hook_score": [],
        "instant_clarity": [],
        "curiosity_gap": [],
        "swipe_risk": [],
        "visual_relevance": [],
        "mode": [],
        "era": [],
        "title_variant_type": []
    }
    
    for video in videos:
        pr = safe_float(video.get("predicted_retention"), 50)
        ar = safe_float(video.get("actual_retention"), 0)
        
        # Skip videos without actual retention
        if ar == 0:
            continue
        
        data["predicted_retention"].append(pr)
        data["actual_retention"].append(ar)
        data["hook_score"].append(safe_float(video.get("hook_score"), 0))
        data["instant_clarity"].append(safe_float(video.get("instant_clarity"), 5))
        data["curiosity_gap"].append(safe_float(video.get("curiosity_gap"), 5))
        data["swipe_risk"].append(safe_float(video.get("swipe_risk"), 5))
        data["visual_relevance"].append(safe_float(video.get("visual_relevance"), 5))
        data["mode"].append(video.get("mode", "quality"))
        data["era"].append(video.get("era", "unknown"))
        data["title_variant_type"].append(video.get("title_variant_type", "safe"))
    
    n = len(data["predicted_retention"])
    if n < 5:
        return {
            "sample_size": n,
            "error": "Not enough videos with actual retention data",
            "correlations": {},
            "mae": None,
            "insights": [],
            "rubric_adjustments": []
        }
    
    # === OVERALL METRICS ===
    
    corr_main = calculate_pearson_correlation(
        data["predicted_retention"], data["actual_retention"]
    )
    mae = calculate_mae(data["predicted_retention"], data["actual_retention"])
    
    # === FEATURE CORRELATIONS ===
    
    feature_correlations = {
        "instant_clarity_vs_retention": calculate_pearson_correlation(
            data["instant_clarity"], data["actual_retention"]
        ),
        "curiosity_gap_vs_retention": calculate_pearson_correlation(
            data["curiosity_gap"], data["actual_retention"]
        ),
        "swipe_risk_vs_retention": calculate_pearson_correlation(
            data["swipe_risk"], data["actual_retention"]
        ),
        "visual_relevance_vs_retention": calculate_pearson_correlation(
            data["visual_relevance"], data["actual_retention"]
        ),
        "hook_score_vs_retention": calculate_pearson_correlation(
            data["hook_score"], data["actual_retention"]
        )
    }
    
    # === MODE-BASED ANALYSIS ===
    
    mode_analysis = {}
    for mode in ["fast", "quality"]:
        mode_indices = [i for i, m in enumerate(data["mode"]) if m == mode]
        if len(mode_indices) >= 3:
            mode_pred = [data["predicted_retention"][i] for i in mode_indices]
            mode_actual = [data["actual_retention"][i] for i in mode_indices]
            mode_analysis[mode] = {
                "count": len(mode_indices),
                "correlation": round(float(calculate_pearson_correlation(mode_pred, mode_actual)), 3),  # pyre-ignore[6]
                "mae": round(float(calculate_mae(mode_pred, mode_actual)), 1),  # pyre-ignore[6]
                "avg_predicted": round(float(sum(mode_pred)) / len(mode_pred), 1),  # pyre-ignore[6]
                "avg_actual": round(float(sum(mode_actual)) / len(mode_actual), 1)  # pyre-ignore[6]
            }
    
    # === TITLE VARIANT ANALYSIS ===
    
    title_analysis = {}
    for variant in ["safe", "bold", "experimental"]:
        variant_indices = [i for i, t in enumerate(data["title_variant_type"]) if t == variant]
        if len(variant_indices) >= 2:
            variant_actual = [data["actual_retention"][i] for i in variant_indices]
            title_analysis[variant] = {
                "count": len(variant_indices),
                "avg_retention": round(float(sum(variant_actual)) / len(variant_actual), 1)  # pyre-ignore[6]
            }
    
    # === INSIGHTS GENERATION ===
    
    insights = []
    adjustments = []
    
    # Main correlation insight
    if corr_main >= 0.7:
        insights.append("[STRONG] Pipeline predictions are accurate")
    elif corr_main >= 0.4:
        insights.append("[MODERATE] Predictions somewhat reliable")
        adjustments.append("Consider refining KPI weights")
    else:
        insights.append("[WEAK] Predictions need recalibration")
        adjustments.append("Major rubric revision needed")
    
    # MAE insight
    if mae <= 10:
        insights.append(f"[MAE] {mae:.1f}% - Excellent prediction accuracy")
    elif mae <= 20:
        insights.append(f"[MAE] {mae:.1f}% - Acceptable accuracy")
    else:
        insights.append(f"[MAE] {mae:.1f}% - Poor accuracy, scale may be wrong")
        adjustments.append("Expand predicted_retention range (model may be stuck in narrow band)")
    
    # Feature insights
    best_feature = max(feature_correlations, key=lambda k: abs(feature_correlations[k]))
    best_corr = feature_correlations[best_feature]
    insights.append(f"[BEST PREDICTOR] {best_feature.replace('_vs_retention', '')}: {best_corr:.2f}")
    
    # Visual relevance warning
    vis_corr = feature_correlations.get("visual_relevance_vs_retention", 0)
    if vis_corr > 0.3:
        insights.append("[VISUAL] Visual relevance strongly affects retention")
        adjustments.append("Focus on visual-script alignment in Titan prompts")
    
    return {
        "sample_size": n,
        "correlations": {
            "predicted_vs_actual": round(float(corr_main), 3),  # pyre-ignore[6]
            **{k: round(float(v), 3) for k, v in feature_correlations.items()}  # pyre-ignore[6]
        },
        "mae": round(float(mae), 1),  # pyre-ignore[6]
        "avg_predicted": round(float(sum(data["predicted_retention"])) / n, 1),  # pyre-ignore[6]
        "avg_actual": round(float(sum(data["actual_retention"])) / n, 1),  # pyre-ignore[6]
        "mode_analysis": mode_analysis,
        "title_analysis": title_analysis,
        "insights": insights,
        "rubric_adjustments": adjustments
    }


def generate_calibration_report(region_name: Optional[str] = None) -> str:
    """Generate human-readable calibration report."""
    analysis = analyze_correlations(region_name)
    
    lines = []
    lines.append("=" * 60)
    lines.append("PIPELINE CALIBRATION REPORT v2")
    lines.append("=" * 60)
    lines.append(f"\nSample Size: {analysis['sample_size']} videos")
    
    if "error" in analysis:
        lines.append(f"\n[WARNING] {analysis['error']}")
        return "\n".join(lines)
    
    # Main metrics
    lines.append(f"\n--- MAIN METRICS ---")
    lines.append(f"Correlation (predicted vs actual): {analysis['correlations'].get('predicted_vs_actual', 0)}")
    lines.append(f"MAE (Mean Absolute Error): {analysis['mae']}%")
    lines.append(f"Avg Predicted: {analysis['avg_predicted']}%")
    lines.append(f"Avg Actual: {analysis['avg_actual']}%")
    
    # Feature correlations
    lines.append(f"\n--- FEATURE CORRELATIONS ---")
    for key, value in analysis.get("correlations", {}).items():
        if key != "predicted_vs_actual":
            feature_name = key.replace("_vs_retention", "").replace("_", " ").title()
            strength = "Strong" if abs(value) >= 0.5 else "Moderate" if abs(value) >= 0.3 else "Weak"
            lines.append(f"  {feature_name}: {value} ({strength})")
    
    # Mode analysis
    if analysis.get("mode_analysis"):
        lines.append(f"\n--- MODE ANALYSIS ---")
        for mode, stats in analysis["mode_analysis"].items():
            lines.append(f"  {mode.upper()}: n={stats['count']}, corr={stats['correlation']}, MAE={stats['mae']}%")
    
    # Title analysis
    if analysis.get("title_analysis"):
        lines.append(f"\n--- TITLE VARIANT ANALYSIS ---")
        for variant, stats in analysis["title_analysis"].items():
            lines.append(f"  {variant}: n={stats['count']}, avg_retention={stats['avg_retention']}%")
    
    # Insights
    lines.append(f"\n--- INSIGHTS ---")
    for insight in analysis.get("insights", []):
        lines.append(f"  {insight}")
    
    # Adjustments
    if analysis.get("rubric_adjustments"):
        lines.append(f"\n--- RECOMMENDED ADJUSTMENTS ---")
        for adj in analysis["rubric_adjustments"]:
            lines.append(f"  * {adj}")
    
    lines.append("\n" + "=" * 60)
    
    return "\n".join(lines)


if __name__ == "__main__":
    print(generate_calibration_report())
