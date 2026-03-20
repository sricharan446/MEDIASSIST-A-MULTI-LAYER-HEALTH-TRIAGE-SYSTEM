"""
Health Analytics & Trends Module
Tracks health metrics over time and generates analytics
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path


def add_health_metric(username: str, metric_name: str, value: float, unit: str, status: str = "normal"):
    """
    Add a health metric to user's analytics history
    """
    analytics_file = Path("memory") / username / "analytics.json"
    analytics_file.parent.mkdir(parents=True, exist_ok=True)
    
    analytics = {}
    if analytics_file.exists():
        with open(analytics_file, "r") as f:
            analytics = json.load(f)
    
    if "metrics" not in analytics:
        analytics["metrics"] = []
    
    analytics["metrics"].append({
        "metric": metric_name,
        "value": value,
        "unit": unit,
        "status": status,
        "timestamp": datetime.now().isoformat(),
    })
    
    # Keep only last 100 metrics
    if len(analytics["metrics"]) > 100:
        analytics["metrics"] = analytics["metrics"][-100:]
    
    with open(analytics_file, "w") as f:
        json.dump(analytics, f, indent=2)


def get_health_trends(username: str, metric_name: Optional[str] = None, days: int = 30) -> Dict[str, Any]:
    """
    Get health trends for a user
    """
    analytics_file = Path("memory") / username / "analytics.json"
    
    if not analytics_file.exists():
        return {"trends": [], "summary": {}}
    
    with open(analytics_file, "r") as f:
        analytics = json.load(f)
    
    metrics = analytics.get("metrics", [])
    
    # Filter by metric name if provided
    if metric_name:
        metrics = [m for m in metrics if m["metric"].lower() == metric_name.lower()]
    
    # Calculate statistics
    if not metrics:
        return {"trends": [], "summary": {}}
    
    values = [m["value"] for m in metrics]
    
    summary = {
        "metric": metric_name or "all",
        "count": len(metrics),
        "average": sum(values) / len(values),
        "min": min(values),
        "max": max(values),
        "latest": metrics[-1]["value"] if metrics else None,
        "trend": "improving" if len(values) > 1 and values[-1] < values[-5] else "declining" if len(values) > 1 else "stable",
    }
    
    return {
        "trends": metrics,
        "summary": summary,
    }


def get_dashboard_summary(username: str) -> Dict[str, Any]:
    """
    Get a dashboard summary of user's health data
    """
    analytics_file = Path("memory") / username / "analytics.json"
    profile_file = Path("memory") / username / "profile.json"
    
    dashboard = {
        "last_updated": datetime.now().isoformat(),
        "health_metrics": {},
        "recent_visits": [],
        "alerts": [],
    }
    
    # Load analytics
    if analytics_file.exists():
        with open(analytics_file, "r") as f:
            analytics = json.load(f)
            metrics = analytics.get("metrics", [])
            
            # Group by metric name
            grouped = {}
            for m in metrics[-20:]:  # Last 20 metrics
                metric_name = m["metric"]
                if metric_name not in grouped:
                    grouped[metric_name] = []
                grouped[metric_name].append(m)
            
            dashboard["health_metrics"] = grouped
    
    # Load profile
    if profile_file.exists():
        with open(profile_file, "r") as f:
            profile = json.load(f)
            dashboard["profile"] = {
                "age": profile.get("age"),
                "conditions": profile.get("known_conditions", []),
                "medications": profile.get("current_medications", []),
            }
    
    return dashboard


def generate_health_report(username: str) -> str:
    """
    Generate a text-based health report for the user
    """
    dashboard = get_dashboard_summary(username)
    
    report_lines = [
        "=== HEALTH DASHBOARD REPORT ===",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    
    # Profile summary
    if "profile" in dashboard:
        profile = dashboard["profile"]
        report_lines.append("PROFILE SUMMARY:")
        report_lines.append(f"  Age: {profile.get('age', 'N/A')}")
        if profile.get("conditions"):
            report_lines.append(f"  Known Conditions: {', '.join(profile['conditions'])}")
        if profile.get("medications"):
            report_lines.append(f"  Current Medications: {', '.join(profile['medications'])}")
        report_lines.append("")
    
    # Health metrics
    if dashboard.get("health_metrics"):
        report_lines.append("RECENT HEALTH METRICS:")
        for metric_name, values in dashboard["health_metrics"].items():
            if values:
                latest = values[-1]
                report_lines.append(f"  {metric_name}: {latest['value']} {latest.get('unit', '')}")
        report_lines.append("")
    
    report_lines.append("=== END REPORT ===")
    
    return "\n".join(report_lines)
