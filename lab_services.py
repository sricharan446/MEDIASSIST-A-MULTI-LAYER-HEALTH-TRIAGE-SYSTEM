import re
from typing import Any, Dict, List, Optional


LAB_PATTERNS = [
    {
        "key": "hba1c",
        "label": "HbA1c",
        "pattern": r"HbA1c[:\s]+([\d\.]+)",
        "risk": lambda v: "high" if v >= 6.5 else ("borderline" if v >= 5.7 else "normal"),
        "finding": lambda v: f"HbA1c is high ({v}%) -> Diabetes risk" if v >= 6.5 else (f"HbA1c borderline ({v}%) -> Prediabetes risk" if v >= 5.7 else None),
    },
    {
        "key": "creatinine",
        "label": "Creatinine",
        "pattern": r"Creatinine[:\s]+([\d\.]+)",
        "risk": lambda v: "high" if v > 1.3 else "normal",
        "finding": lambda v: f"Creatinine elevated ({v}) -> Kidney concern" if v > 1.3 else None,
    },
    {
        "key": "hemoglobin",
        "label": "Hemoglobin",
        "pattern": r"Hemoglobin[:\s]+([\d\.]+)",
        "risk": lambda v: "low" if v < 12 else "normal",
        "finding": lambda v: f"Hemoglobin low ({v}) -> Possible anemia" if v < 12 else None,
    },
    {
        "key": "cholesterol",
        "label": "Cholesterol",
        "pattern": r"Cholesterol[:\s]+([\d\.]+)",
        "risk": lambda v: "high" if v > 200 else "normal",
        "finding": lambda v: f"Cholesterol high ({v}) -> Heart disease risk" if v > 200 else None,
    },
    {
        "key": "vitamin_d",
        "label": "Vitamin D",
        "pattern": r"Vitamin D[:\s]+([\d\.]+)",
        "risk": lambda v: "low" if v < 20 else "normal",
        "finding": lambda v: f"Vitamin D deficiency ({v}) -> Bone health risk" if v < 20 else None,
    },
    {
        "key": "tsh",
        "label": "TSH",
        "pattern": r"TSH[:\s]+([\d\.]+)",
        "risk": lambda v: "high" if v > 4 else ("low" if v < 0.4 else "normal"),
        "finding": lambda v: f"TSH elevated ({v}) -> Possible hypothyroidism" if v > 4 else (f"TSH low ({v}) -> Possible hyperthyroidism" if v < 0.4 else None),
    },
    {
        "key": "wbc",
        "label": "WBC",
        "pattern": r"WBC[:\s]+([\d\.]+)",
        "risk": lambda v: "high" if v > 11000 else "normal",
        "finding": lambda v: f"WBC elevated ({v}) -> Possible infection" if v > 11000 else None,
    },
    {
        "key": "rbc",
        "label": "RBC",
        "pattern": r"RBC[:\s]+([\d\.]+)",
        "risk": lambda v: "low" if v < 4 else "normal",
        "finding": lambda v: f"RBC low ({v}) -> Possible anemia" if v < 4 else None,
    },
    {
        "key": "platelets",
        "label": "Platelets",
        "pattern": r"Platelets[:\s]+([\d\.]+)",
        "risk": lambda v: "low" if v < 150000 else ("high" if v > 450000 else "normal"),
        "finding": lambda v: f"Platelets low ({v}) -> Bleeding risk" if v < 150000 else (f"Platelets high ({v}) -> Clotting risk" if v > 450000 else None),
    },
]


def extract_lab_metrics(text: str) -> List[Dict[str, Any]]:
    metrics: List[Dict[str, Any]] = []
    for definition in LAB_PATTERNS:
        match = re.search(definition["pattern"], text, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            continue
        metrics.append(
            {
                "key": definition["key"],
                "label": definition["label"],
                "value": value,
                "risk": definition["risk"](value),
            }
        )

    bp = re.search(r"(?:Blood Pressure|BP)[:\s]*(\d{2,3})/(\d{2,3})|(\d{2,3})/(\d{2,3})", text, re.IGNORECASE)
    if bp:
        systolic = int(bp.group(1) or bp.group(3))
        diastolic = int(bp.group(2) or bp.group(4))
        risk = "high" if systolic >= 140 or diastolic >= 90 else "normal"
        metrics.append(
            {
                "key": "blood_pressure",
                "label": "Blood Pressure",
                "value": {"systolic": systolic, "diastolic": diastolic},
                "display": f"{systolic}/{diastolic}",
                "risk": risk,
            }
        )
    return metrics


def analyze_lab_values(text: str) -> List[str]:
    findings: List[str] = []
    for definition in LAB_PATTERNS:
        match = re.search(definition["pattern"], text, re.IGNORECASE)
        if not match:
            continue
        try:
            value = float(match.group(1))
        except (TypeError, ValueError):
            continue
        finding = definition["finding"](value)
        if finding:
            findings.append(finding)

    bp = re.search(r"(?:Blood Pressure|BP)[:\s]*(\d{2,3})/(\d{2,3})|(\d{2,3})/(\d{2,3})", text, re.IGNORECASE)
    if bp:
        systolic = int(bp.group(1) or bp.group(3))
        diastolic = int(bp.group(2) or bp.group(4))
        if systolic >= 140 or diastolic >= 90:
            findings.append(f"Blood Pressure high ({systolic}/{diastolic}) -> Hypertension risk")
    return findings


def _metric_to_number(metric: Dict[str, Any]) -> Optional[float]:
    value = metric.get("value")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):
        systolic = value.get("systolic")
        diastolic = value.get("diastolic")
        if isinstance(systolic, (int, float)) and isinstance(diastolic, (int, float)):
            return float(systolic) + (float(diastolic) / 1000.0)
    return None


def compare_lab_records(current_metrics: List[Dict[str, Any]], previous_metrics: List[Dict[str, Any]]) -> List[str]:
    previous_by_key = {metric["key"]: metric for metric in previous_metrics}
    trend_lines: List[str] = []
    for current in current_metrics:
        previous = previous_by_key.get(current["key"])
        if not previous:
            continue
        if current["key"] == "blood_pressure":
            prev_sys = previous["value"]["systolic"]
            prev_dia = previous["value"]["diastolic"]
            cur_sys = current["value"]["systolic"]
            cur_dia = current["value"]["diastolic"]
            if prev_sys == cur_sys and prev_dia == cur_dia:
                trend_lines.append(f"Blood Pressure unchanged at {current.get('display', f'{cur_sys}/{cur_dia}')}.")
            else:
                direction = "up" if (cur_sys > prev_sys or cur_dia > prev_dia) else "down"
                trend_lines.append(f"Blood Pressure moved {direction}: {prev_sys}/{prev_dia} -> {cur_sys}/{cur_dia}.")
            continue

        prev_num = _metric_to_number(previous)
        cur_num = _metric_to_number(current)
        if prev_num is None or cur_num is None:
            continue
        if abs(cur_num - prev_num) < 1e-9:
            trend_lines.append(f"{current['label']} unchanged at {cur_num:g}.")
        else:
            direction = "up" if cur_num > prev_num else "down"
            trend_lines.append(f"{current['label']} moved {direction}: {prev_num:g} -> {cur_num:g}.")
    return trend_lines


def summarize_metric_snapshot(metrics: List[Dict[str, Any]]) -> str:
    if not metrics:
        return "No structured lab values extracted."
    parts = []
    for metric in metrics:
        if metric["key"] == "blood_pressure":
            value_text = metric.get("display", "")
        else:
            value = metric.get("value")
            value_text = f"{value:g}" if isinstance(value, (int, float)) else str(value)
        parts.append(f"{metric['label']}: {value_text} ({metric.get('risk', 'unknown')})")
    return "; ".join(parts)
