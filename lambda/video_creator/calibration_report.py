"""
Calibration Report
==================
Statistical validation of the evaluation system.
Answers the single most important question:
"Is the LLM evaluator actually modeling viewer behavior, or flattering itself?"

6 Analyses:
1. Spearman Rank Correlation (hook_score vs actual_retention)
2. Calibration Curve (predicted retention buckets vs actual)
3. Bucket Error Analysis (per bucket MAE)
4. Refine Impact (refine_count vs retention)
5. Hook Score Impact (score bands vs retention)
6. Explore vs Exploit (hook_family diversity impact)

Triggered manually or by EventBridge.
Sends report via SNS.
"""

import json
import os
import boto3  # pyre-ignore[21]
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# Configuration
METRICS_TABLE_NAME = os.environ.get("METRICS_TABLE_NAME", "shorts_video_metrics")
SNS_TOPIC_ARN = os.environ.get("SNS_TOPIC_ARN")

# Minimum sample sizes for statistical validity
MIN_VIDEOS_FOR_REPORT = 10
MIN_VIDEOS_PER_BUCKET = 3


# ============================================================================
# STATISTICS (No external dependencies — Lambda-safe)
# ============================================================================

def spearman_rank_correlation(x: List[float], y: List[float]) -> Tuple[float, str]:
    """
    Compute Spearman rank correlation coefficient.
    Returns (rho, interpretation).
    
    Why Spearman, not Pearson?
    We care about RANKING accuracy, not linear fit.
    "Does higher hook_score mean higher retention?" is a rank question.
    """
    n = len(x)
    if n < 5:
        return 0.0, "insufficient_data"
    
    # Rank the values (average rank for ties)
    def rank(values: List[float]) -> List[float]:
        sorted_indices = sorted(range(len(values)), key=lambda i: values[i])
        ranks = [0.0] * len(values)
        i = 0
        while i < len(sorted_indices):
            # Find ties
            j = i
            while j < len(sorted_indices) and values[sorted_indices[j]] == values[sorted_indices[i]]:  # pyre-ignore[6]
                j += 1  # pyre-ignore[6]
            # Average rank for ties
            avg_rank = (i + j - 1) / 2.0 + 1  # 1-indexed  # pyre-ignore[6]
            for k in range(i, j):
                ranks[sorted_indices[k]] = avg_rank  # pyre-ignore[6]
            i = j
        return ranks
    
    rx = rank(x)
    ry = rank(y)
    
    # Spearman's rho = Pearson correlation of ranks
    mean_rx = sum(rx) / n
    mean_ry = sum(ry) / n
    
    numerator = sum((rx[i] - mean_rx) * (ry[i] - mean_ry) for i in range(n))
    denom_x = math.sqrt(sum((rx[i] - mean_rx) ** 2 for i in range(n)))
    denom_y = math.sqrt(sum((ry[i] - mean_ry) ** 2 for i in range(n)))
    
    if denom_x == 0 or denom_y == 0:
        return 0.0, "no_variance"
    
    rho = numerator / (denom_x * denom_y)
    
    # Interpretation
    abs_rho = abs(rho)
    if abs_rho >= 0.7:
        interp = "STRONG ✅ — evaluator is well-calibrated"
    elif abs_rho >= 0.5:
        interp = "MODERATE ⚠️ — evaluator is directionally correct"
    elif abs_rho >= 0.3:
        interp = "WEAK ⚠️ — evaluator needs rubric revision"
    else:
        interp = "NEGLIGIBLE ❌ — evaluator is NOT modeling viewer behavior"
    
    return round(rho, 3), interp  # pyre-ignore[6]


def mean(values: List[float]) -> float:
    """Safe mean."""
    return sum(values) / len(values) if values else 0.0


def median(values: List[float]) -> float:
    """Safe median."""
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    if n % 2 == 0:
        return (s[n // 2 - 1] + s[n // 2]) / 2
    return s[n // 2]


# ============================================================================
# DATA LOADING
# ============================================================================

def load_calibration_data(region_name: Optional[str] = None) -> List[Dict]:
    """
    Load all calibration-eligible, complete videos from DynamoDB.
    Only videos with BOTH predicted AND actual retention are useful.
    """
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    dynamodb = boto3.resource("dynamodb", region_name=region)
    table = dynamodb.Table(METRICS_TABLE_NAME)
    
    response = table.scan(
        FilterExpression="calibration_eligible = :eligible AND #st = :status",
        ExpressionAttributeNames={"#st": "status"},
        ExpressionAttributeValues={
            ":eligible": True,
            ":status": "complete"
        }
    )
    
    items = response.get("Items", [])
    
    # Handle DynamoDB pagination
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression="calibration_eligible = :eligible AND #st = :status",
            ExpressionAttributeNames={"#st": "status"},
            ExpressionAttributeValues={
                ":eligible": True,
                ":status": "complete"
            },
            ExclusiveStartKey=response["LastEvaluatedKey"]
        )
        items.extend(response.get("Items", []))
    
    # Parse and validate
    videos = []
    for item in items:
        try:
            predicted = float(item.get("predicted_retention", 0))
            actual = float(item.get("actual_retention", 0))
            hook_score = float(item.get("hook_score", 0))
            
            if actual <= 0:
                continue  # Skip videos without real analytics
            
            videos.append({
                "video_id": item.get("video_id", ""),
                "title_used": item.get("title_used", "N/A"),
                "predicted_retention": predicted,
                "actual_retention": actual,
                "hook_score": hook_score,
                "hook_family": item.get("hook_family", "unknown"),
                "mode": item.get("mode", "unknown"),
                "category": item.get("category", "unknown"),
                "era": item.get("era", "unknown"),
                "refine_total": int(item.get("refine_total", 0)),
                "hook_refines": int(item.get("hook_refines", 0)),
                "instant_clarity": float(item.get("instant_clarity", 0)),
                "curiosity_gap": float(item.get("curiosity_gap", 0)),
                "swipe_risk": float(item.get("swipe_risk", 0)),
            })
        except (ValueError, TypeError):
            continue
    
    return videos


# ============================================================================
# ANALYSIS 1: SPEARMAN RANK CORRELATION
# ============================================================================

def analyze_correlations(videos: List[Dict]) -> Dict:
    """
    Compute Spearman correlations for all prediction → actual pairs.
    This is THE most important analysis.
    """
    if len(videos) < MIN_VIDEOS_FOR_REPORT:
        return {"status": "insufficient_data", "n": len(videos)}
    
    hook_scores = [v["hook_score"] for v in videos]
    predicted = [v["predicted_retention"] for v in videos]
    actual = [v["actual_retention"] for v in videos]
    clarity = [v["instant_clarity"] for v in videos]
    curiosity = [v["curiosity_gap"] for v in videos]
    swipe = [v["swipe_risk"] for v in videos]
    
    rho_hook, interp_hook = spearman_rank_correlation(hook_scores, actual)
    rho_predicted, interp_predicted = spearman_rank_correlation(predicted, actual)
    rho_clarity, interp_clarity = spearman_rank_correlation(clarity, actual)
    rho_curiosity, interp_curiosity = spearman_rank_correlation(curiosity, actual)
    rho_swipe, interp_swipe = spearman_rank_correlation(swipe, actual)
    
    return {
        "n": len(videos),
        "hook_score_vs_retention": {"rho": rho_hook, "interpretation": interp_hook},
        "predicted_vs_actual": {"rho": rho_predicted, "interpretation": interp_predicted},
        "instant_clarity_vs_retention": {"rho": rho_clarity, "interpretation": interp_clarity},
        "curiosity_gap_vs_retention": {"rho": rho_curiosity, "interpretation": interp_curiosity},
        "swipe_risk_vs_retention": {"rho": rho_swipe, "interpretation": interp_swipe},
    }


# ============================================================================
# ANALYSIS 2: CALIBRATION CURVE
# ============================================================================

def analyze_calibration_curve(videos: List[Dict]) -> Dict:
    """
    Bucket predicted retention into bands, compare with actual.
    
    Ideal: Predicted 55 → Actual ~55 (diagonal line)
    Dangerous: Predicted 60 → Actual 42 (overconfident model)
    """
    bucket_ranges = {
        "30-40": (30, 40), "40-45": (40, 45), "45-50": (45, 50),
        "50-55": (50, 55), "55-60": (55, 60), "60+": (60, 100),
    }
    bucket_predicted: Dict[str, List[float]] = {k: [] for k in bucket_ranges}
    bucket_actual: Dict[str, List[float]] = {k: [] for k in bucket_ranges}
    
    for v in videos:
        p = v["predicted_retention"]
        for label, (lo, hi) in bucket_ranges.items():
            if lo <= p < hi or (label == "60+" and p >= 60):
                bucket_predicted[label].append(p)  # pyre-ignore[6]
                bucket_actual[label].append(v["actual_retention"])  # pyre-ignore[6]
                break
    
    results = {}
    overall_bias = 0.0
    counted = 0
    
    for label in bucket_ranges:
        n = len(bucket_predicted[label])
        if n < MIN_VIDEOS_PER_BUCKET:
            results[label] = {"n": n, "status": "insufficient_data"}
            continue
        
        avg_predicted = mean(bucket_predicted[label])
        avg_actual = mean(bucket_actual[label])
        error = avg_predicted - avg_actual  # Positive = overconfident
        
        if avg_actual > 0:
            pct_error = (error / avg_actual) * 100
        else:
            pct_error = 0.0
        
        results[label] = {
            "n": n,
            "avg_predicted": round(avg_predicted, 1),  # pyre-ignore[6]
            "avg_actual": round(avg_actual, 1),  # pyre-ignore[6]
            "error": round(error, 1),  # pyre-ignore[6]
            "pct_error": round(pct_error, 1),  # pyre-ignore[6]
            "direction": "OVERCONFIDENT" if error > 3 else "UNDERCONFIDENT" if error < -3 else "CALIBRATED ✅"
        }
        
        overall_bias += error * n
        counted += n
    
    return {
        "buckets": results,
        "overall_bias": round(overall_bias / counted, 1) if counted > 0 else 0,  # pyre-ignore[6]
        "bias_direction": "Model is OPTIMISTIC" if (overall_bias / counted if counted else 0) > 2 else 
                          "Model is PESSIMISTIC" if (overall_bias / counted if counted else 0) < -2 else 
                          "Model is WELL-CALIBRATED ✅"
    }


# ============================================================================
# ANALYSIS 3: REFINE IMPACT
# ============================================================================

def analyze_refine_impact(videos: List[Dict]) -> Dict:
    """
    Test: Does more refinement = better retention?
    
    Granular buckets to isolate each refine iteration's effect.
    hook_max_iterations=3 → max 2 hook refines per video.
    With 4 sections × 2 max refines each → total refines 0-8.
    """
    by_refine: Dict[str, List[float]] = {
        "0_refine": [],
        "1_refine": [],
        "2_refine": [],
        "3_refine": [],
        "4+_refine": [],
    }
    
    for v in videos:
        total = v["refine_total"]
        actual = v["actual_retention"]
        
        if total == 0:
            by_refine["0_refine"].append(actual)
        elif total == 1:
            by_refine["1_refine"].append(actual)
        elif total == 2:
            by_refine["2_refine"].append(actual)
        elif total == 3:
            by_refine["3_refine"].append(actual)
        else:
            by_refine["4+_refine"].append(actual)
    
    results = {}
    for label, retentions in by_refine.items():
        if len(retentions) < MIN_VIDEOS_PER_BUCKET:
            results[label] = {"n": len(retentions), "status": "insufficient_data"}
        else:
            results[label] = {
                "n": len(retentions),
                "avg_retention": round(mean(retentions), 1),  # pyre-ignore[6]
                "median_retention": round(median(retentions), 1),  # pyre-ignore[6]
            }
    
    # Detect sterilization: does retention DROP as refine count increases?
    sterilization_warning = False
    # Check if any higher bucket performs worse than a lower one
    ordered_labels = ["0_refine", "1_refine", "2_refine", "3_refine", "4+_refine"]
    prev_avg = None
    for label in ordered_labels:
        bucket = results.get(label, {})
        if "avg_retention" in bucket:
            curr_avg = bucket["avg_retention"]
            if prev_avg is not None and curr_avg < prev_avg - 2.0:  # pyre-ignore[6]
                sterilization_warning = True
            prev_avg = curr_avg
    
    return {
        "by_refine_count": results,
        "sterilization_warning": sterilization_warning,
        "verdict": "⚠️ STERILIZATION DETECTED — more refines correlate with WORSE retention" if sterilization_warning else
                   "✅ No sterilization detected"
    }


# ============================================================================
# ANALYSIS 4: HOOK SCORE BANDS
# ============================================================================

def analyze_hook_score_bands(videos: List[Dict]) -> Dict:
    """
    Is the 9.0 threshold too aggressive?
    Compare retention across hook score bands.
    """
    bands: Dict[str, List[float]] = {
        "7.0-7.9": [],
        "8.0-8.4": [],
        "8.5-8.9": [],
        "9.0-9.4": [],
        "9.5-10.0": [],
    }
    
    for v in videos:
        score = v["hook_score"]
        actual = v["actual_retention"]
        
        if 7.0 <= score < 8.0:
            bands["7.0-7.9"].append(actual)
        elif 8.0 <= score < 8.5:
            bands["8.0-8.4"].append(actual)
        elif 8.5 <= score < 9.0:
            bands["8.5-8.9"].append(actual)
        elif 9.0 <= score < 9.5:
            bands["9.0-9.4"].append(actual)
        elif score >= 9.5:
            bands["9.5-10.0"].append(actual)
    
    results = {}
    for label, retentions in bands.items():
        if len(retentions) < MIN_VIDEOS_PER_BUCKET:
            results[label] = {"n": len(retentions), "status": "insufficient_data"}
        else:
            results[label] = {
                "n": len(retentions),
                "avg_retention": round(mean(retentions), 1),  # pyre-ignore[6]
                "median_retention": round(median(retentions), 1),  # pyre-ignore[6]
            }
    
    # Check if 9.0+ is actually better than 8.5-8.9
    threshold_justified = None
    band_85 = results.get("8.5-8.9", {})
    band_90 = results.get("9.0-9.4", {})
    if "avg_retention" in band_85 and "avg_retention" in band_90:
        diff = band_90["avg_retention"] - band_85["avg_retention"]  # pyre-ignore[6]
        if diff > 3:
            threshold_justified = f"✅ 9.0 threshold JUSTIFIED — 9.0+ is {diff:.1f}pp better"
        elif diff > 0:
            threshold_justified = f"⚠️ MARGINAL — 9.0+ is only {diff:.1f}pp better, consider lowering to 8.5"
        else:
            threshold_justified = f"❌ 9.0 THRESHOLD TOO HIGH — 8.5-8.9 band performs {abs(diff):.1f}pp BETTER"
    
    return {
        "by_score_band": results,
        "threshold_verdict": threshold_justified or "Insufficient data for threshold analysis"
    }


# ============================================================================
# ANALYSIS 5: EXPLORE VS EXPLOIT
# ============================================================================

def analyze_explore_vs_exploit(videos: List[Dict]) -> Dict:
    """
    Compare retention across hook families.
    If exploration consistently outperforms exploitation,
    the bandit has prematurely converged.
    """
    by_family: Dict[str, List[float]] = {}
    
    for v in videos:
        family = v["hook_family"]
        if family and family != "unknown":
            if family not in by_family:
                by_family[family] = []
            by_family[family].append(v["actual_retention"])
    
    results = {}
    for family, retentions in by_family.items():
        results[family] = {
            "n": len(retentions),
            "avg_retention": round(mean(retentions), 1),  # pyre-ignore[6]
            "median_retention": round(median(retentions), 1),  # pyre-ignore[6]
        }
    
    # Sort by performance
    sorted_families = sorted(results.items(), key=lambda x: x[1].get("avg_retention", 0), reverse=True)
    
    return {
        "by_hook_family": dict(sorted_families),
        "best_family": sorted_families[0][0] if sorted_families else "unknown",
        "worst_family": sorted_families[-1][0] if sorted_families else "unknown",
    }


# ============================================================================
# ANALYSIS 6: FALSE POSITIVES / FALSE NEGATIVES (Outliers)
# ============================================================================

def analyze_outliers(videos: List[Dict]) -> Dict:
    """
    Find the most dangerously wrong predictions.
    
    False Positive: Model said "great!" (predicted 65+) but retention was terrible (<35)
    False Negative: Model said "meh" (predicted <45) but video went viral (>60)
    """
    false_positives = []  # Overconfident disasters
    false_negatives = []  # Missed gems
    
    for v in videos:
        error = v["predicted_retention"] - v["actual_retention"]
        
        # False positive: predicted much higher than actual
        if v["predicted_retention"] >= 55 and v["actual_retention"] < 35:
            false_positives.append({
                "video_id": v["video_id"],
                "title": v["title_used"][:60],
                "predicted": v["predicted_retention"],
                "actual": v["actual_retention"],
                "hook_score": v["hook_score"],
                "error": round(error, 1),
            })
        
        # False negative: predicted much lower than actual
        if v["predicted_retention"] < 50 and v["actual_retention"] >= 55:
            false_negatives.append({
                "video_id": v["video_id"],
                "title": v["title_used"][:60],
                "predicted": v["predicted_retention"],
                "actual": v["actual_retention"],
                "hook_score": v["hook_score"],
                "error": round(error, 1),
            })
    
    # Sort by magnitude of error
    false_positives.sort(key=lambda x: x["error"], reverse=True)
    false_negatives.sort(key=lambda x: x["error"])
    
    return {
        "false_positives": false_positives[:5],  # Top 5 overconfident disasters  # pyre-ignore[6]
        "false_negatives": false_negatives[:5],   # Top 5 missed gems  # pyre-ignore[6]
        "fp_count": len(false_positives),
        "fn_count": len(false_negatives),
    }


# ============================================================================
# CATEGORY RETENTION HEATMAP
# ============================================================================

def analyze_category_performance(videos: List[Dict]) -> Dict:
    """Category-level retention performance."""
    by_category: Dict[str, List[float]] = {}
    
    for v in videos:
        cat = v["category"]
        if cat and cat != "unknown":
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(v["actual_retention"])
    
    results = {}
    for cat, retentions in by_category.items():
        results[cat] = {
            "n": len(retentions),
            "avg_retention": round(mean(retentions), 1),  # pyre-ignore[6]
            "median_retention": round(median(retentions), 1),  # pyre-ignore[6]
            "min": round(min(retentions), 1),  # pyre-ignore[6]
            "max": round(max(retentions), 1),  # pyre-ignore[6]
        }
    
    return dict(sorted(results.items(), key=lambda x: x[1]["avg_retention"], reverse=True))


# ============================================================================
# ANALYSIS 8: REFINE DELTA — Self-Optimization Detection
# ============================================================================

def analyze_refine_delta(videos: List[Dict]) -> Dict:
    """
    Does refine actually improve viewer outcomes, or just evaluator scores?
    
    Three robust metrics (replacing fragile ratio):
    1. Mean hook_score_delta — how much evaluator score inflated
    2. Mean actual_retention_delta — refined vs unrefined actual performance
    3. Pearson correlation(hook_score_delta, actual_retention) — THE test
    
    If correlation ≈ 0 → evaluator is self-optimizing (Goodhart).
    If correlation > 0 → score gains translate to real viewer benefit.
    """
    all_instrumented = []  # All videos with delta data
    
    for v in videos:
        first_hs = v.get("first_hook_score")
        final_hs = v.get("final_hook_score")
        
        if first_hs is None or final_hs is None:
            continue  # Old data without instrumentation
        
        try:
            first_hs = float(first_hs)  # pyre-ignore[6]
            final_hs = float(final_hs)  # pyre-ignore[6]
        except (ValueError, TypeError):
            continue
        
        delta = final_hs - first_hs
        all_instrumented.append({
            "video_id": v["video_id"],
            "first_hook_score": first_hs,
            "final_hook_score": final_hs,
            "hook_score_delta": delta,
            "actual_retention": v["actual_retention"],
            "predicted_retention": v["predicted_retention"],
        })
    
    # Split into refined vs unrefined
    refined = [v for v in all_instrumented if v["hook_score_delta"] > 0.3]
    unrefined = [v for v in all_instrumented if v["hook_score_delta"] <= 0.3]
    
    result: Dict = {  # pyre-ignore[6]
        "instrumented_videos": len(all_instrumented),
        "refined_count": len(refined),
        "unrefined_count": len(unrefined),
    }
    
    if len(all_instrumented) < 5:
        result["status"] = "insufficient_data"
        result["message"] = "Need more videos with hook score delta instrumentation"
        return result
    
    # METRIC 1: Mean hook_score_delta (evaluator inflation)
    all_deltas = [v["hook_score_delta"] for v in all_instrumented]
    avg_delta = mean(all_deltas)
    
    # METRIC 2: Mean retention comparison (refined vs unrefined)
    if len(refined) >= 3 and len(unrefined) >= 3:
        avg_refined_retention = mean([v["actual_retention"] for v in refined])
        avg_unrefined_retention = mean([v["actual_retention"] for v in unrefined])
        retention_diff = avg_refined_retention - avg_unrefined_retention
    else:
        avg_refined_retention = None
        avg_unrefined_retention = None
        retention_diff = None
    
    # METRIC 3: Pearson correlation(hook_score_delta, actual_retention)
    # This is THE definitive test. If ~0 → evaluator is Goodhart'ing.
    deltas = [v["hook_score_delta"] for v in all_instrumented]
    retentions = [v["actual_retention"] for v in all_instrumented]
    
    correlation = None
    if len(all_instrumented) >= 5:
        mean_d = mean(deltas)
        mean_r = mean(retentions)
        
        numerator = sum((d - mean_d) * (r - mean_r) for d, r in zip(deltas, retentions))
        denom_d = math.sqrt(sum((d - mean_d) ** 2 for d in deltas))
        denom_r = math.sqrt(sum((r - mean_r) ** 2 for r in retentions))
        
        if denom_d > 0 and denom_r > 0:
            correlation = numerator / (denom_d * denom_r)
    
    # Detect self-optimization
    self_optimization_detected = (
        avg_delta > 0.5 and  # Evaluator score went up meaningfully
        correlation is not None and
        correlation < 0.1  # But no correlation with actual retention
    )
    
    result.update({
        "mean_hook_score_delta": round(avg_delta, 2),  # pyre-ignore[6]
        "mean_refined_retention": round(avg_refined_retention, 1) if avg_refined_retention else None,  # pyre-ignore[6]
        "mean_unrefined_retention": round(avg_unrefined_retention, 1) if avg_unrefined_retention else None,  # pyre-ignore[6]
        "retention_diff_pp": round(retention_diff, 1) if retention_diff is not None else None,  # pyre-ignore[6]
        "delta_retention_correlation": round(correlation, 3) if correlation is not None else None,  # pyre-ignore[6]
        "self_optimization_detected": self_optimization_detected,
        "verdict": (
            "❌ SELF-OPTIMIZATION — Score delta does NOT correlate with retention"
            if self_optimization_detected else
            "✅ Score gains correlate with real viewer benefit"
            if correlation is not None and correlation > 0.3 else
            "⚠️ Weak or no signal — more data needed"
        ),
    })
    
    return result


# ============================================================================
# MAIN REPORT GENERATOR
# ============================================================================

def generate_calibration_report(region_name: Optional[str] = None) -> Dict:
    """
    Generate complete calibration report.
    Returns structured dict with all 6 analyses.
    """
    videos = load_calibration_data(region_name)
    n = len(videos)
    
    print(f"📊 Loaded {n} calibration-eligible videos")
    
    if n < MIN_VIDEOS_FOR_REPORT:
        return {
            "status": "insufficient_data",
            "n": n,
            "minimum_required": MIN_VIDEOS_FOR_REPORT,
            "message": f"Need {MIN_VIDEOS_FOR_REPORT - n} more complete videos before calibration report is meaningful."
        }
    
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "n": n,
        "status": "ready",
        
        # THE critical analysis
        "1_correlations": analyze_correlations(videos),
        
        # Is the model overconfident?
        "2_calibration_curve": analyze_calibration_curve(videos),
        
        # Does refining help or sterilize?
        "3_refine_impact": analyze_refine_impact(videos),
        
        # Is 9.0 threshold justified?
        "4_hook_score_bands": analyze_hook_score_bands(videos),
        
        # Is bandit exploring enough?
        "5_explore_vs_exploit": analyze_explore_vs_exploit(videos),
        
        # Where is the model dangerously wrong?
        "6_outliers": analyze_outliers(videos),
        
        # Bonus: category heatmap
        "7_category_performance": analyze_category_performance(videos),
        
        # Refine self-optimization detection
        "8_refine_delta": analyze_refine_delta(videos),
    }
    
    return report


# ============================================================================
# SNS NOTIFICATION
# ============================================================================

def format_report_text(report: Dict) -> str:
    """Format report as human-readable text for SNS."""
    if report.get("status") == "insufficient_data":
        return f"📊 Calibration Report: Need {report['minimum_required'] - report['n']} more videos (have {report['n']}/{report['minimum_required']})"
    
    lines = [
        f"📊 CALIBRATION REPORT ({report['n']} videos)",
        f"Generated: {report['generated_at'][:16]}",
        "",
        "═══ 1. SPEARMAN CORRELATIONS ═══",
    ]
    
    corr = report.get("1_correlations", {})
    for key in ["hook_score_vs_retention", "predicted_vs_actual", 
                 "instant_clarity_vs_retention", "curiosity_gap_vs_retention", "swipe_risk_vs_retention"]:
        data = corr.get(key, {})
        label = key.replace("_vs_", " → ").replace("_", " ").title()
        lines.append(f"  {label}: ρ = {data.get('rho', 'N/A')} — {data.get('interpretation', 'N/A')}")
    
    lines.extend(["", "═══ 2. CALIBRATION CURVE ═══"])
    cal = report.get("2_calibration_curve", {})
    lines.append(f"  Overall bias: {cal.get('overall_bias', 'N/A')}pp — {cal.get('bias_direction', 'N/A')}")
    for bucket_label, bucket_data in cal.get("buckets", {}).items():
        if "avg_predicted" in bucket_data:
            lines.append(f"  [{bucket_label}] Predicted: {bucket_data['avg_predicted']}% → Actual: {bucket_data['avg_actual']}% ({bucket_data['direction']})")
        else:
            lines.append(f"  [{bucket_label}] n={bucket_data.get('n', 0)} — insufficient data")
    
    lines.extend(["", "═══ 3. REFINE IMPACT ═══"])
    refine = report.get("3_refine_impact", {})
    lines.append(f"  Verdict: {refine.get('verdict', 'N/A')}")
    for label, data in refine.get("by_refine_count", {}).items():
        if "avg_retention" in data:
            lines.append(f"  {label}: avg {data['avg_retention']}% (n={data['n']})")
        else:
            lines.append(f"  {label}: n={data.get('n', 0)} — insufficient data")
    
    lines.extend(["", "═══ 4. HOOK SCORE BANDS ═══"])
    hook = report.get("4_hook_score_bands", {})
    lines.append(f"  Verdict: {hook.get('threshold_verdict', 'N/A')}")
    for band, data in hook.get("by_score_band", {}).items():
        if "avg_retention" in data:
            lines.append(f"  [{band}] avg {data['avg_retention']}% (n={data['n']})")
    
    lines.extend(["", "═══ 5. HOOK FAMILY (EXPLORE VS EXPLOIT) ═══"])
    explore = report.get("5_explore_vs_exploit", {})
    lines.append(f"  Best: {explore.get('best_family', 'N/A')} | Worst: {explore.get('worst_family', 'N/A')}")
    for family, data in explore.get("by_hook_family", {}).items():
        lines.append(f"  {family}: avg {data['avg_retention']}% (n={data['n']})")
    
    lines.extend(["", "═══ 6. OUTLIERS ═══"])
    outliers = report.get("6_outliers", {})
    lines.append(f"  False Positives (model said great, reality said no): {outliers.get('fp_count', 0)}")
    for fp in outliers.get("false_positives", [])[:3]:
        lines.append(f"    ❌ {fp['title']} — predicted {fp['predicted']}% actual {fp['actual']}%")
    lines.append(f"  False Negatives (model said meh, reality said wow): {outliers.get('fn_count', 0)}")
    for fn in outliers.get("false_negatives", [])[:3]:
        lines.append(f"    💎 {fn['title']} — predicted {fn['predicted']}% actual {fn['actual']}%")
    
    lines.extend(["", "═══ 7. CATEGORY HEATMAP ═══"])
    for cat, data in report.get("7_category_performance", {}).items():
        lines.append(f"  {cat}: avg {data['avg_retention']}% | range [{data['min']}–{data['max']}%] (n={data['n']})")
    
    return "\n".join(lines)


def send_calibration_report(report: Dict, region_name: Optional[str] = None):
    """Send calibration report via SNS."""
    topic_arn = SNS_TOPIC_ARN
    if not topic_arn:
        print("⚠️ SNS_TOPIC_ARN not set, printing report only")
        print(format_report_text(report))
        return
    
    region = region_name or os.environ.get("AWS_REGION_NAME", "us-east-1")
    sns = boto3.client("sns", region_name=region)
    
    text = format_report_text(report)
    
    sns.publish(
        TopicArn=topic_arn,
        Subject=f"📊 Calibration Report ({report.get('n', 0)} videos)",
        Message=text
    )
    print(f"📧 Calibration report sent via SNS ({report.get('n', 0)} videos)")


# ============================================================================
# LAMBDA HANDLER
# ============================================================================

def lambda_handler(event, context):
    """Lambda entry point for calibration report generation."""
    print("📊 Starting calibration report generation...")
    
    region = os.environ.get("AWS_REGION_NAME", "us-east-1")
    report = generate_calibration_report(region)
    
    # Always send (even if insufficient data — so we know)
    send_calibration_report(report, region)
    
    return {
        "statusCode": 200,
        "body": json.dumps({
            "status": report.get("status", "unknown"),
            "n": report.get("n", 0),
        })
    }


# ============================================================================
# LOCAL TESTING
# ============================================================================

if __name__ == "__main__":
    print("📊 Running calibration report locally...")
    report = generate_calibration_report()
    
    # Pretty print
    print("\n" + format_report_text(report))
    
    # Also dump JSON
    print("\n\n--- RAW JSON ---")
    print(json.dumps(report, indent=2, default=str))
