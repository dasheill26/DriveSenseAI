from typing import Dict, Any


def score_to_label(score: float) -> str:
    if score >= 7.5:
        return "High"
    if score >= 4.5:
        return "Medium"
    return "Low"


def label_to_class(label: str) -> str:
    l = (label or "").lower()
    if l == "high":
        return "sev-high"
    if l == "medium":
        return "sev-med"
    return "sev-low"


def compute_severity(dtc_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic severity output (interpretable).
    Returns {score, label, css_class}.
    """
    base_score = float(dtc_record.get("base_score", 3.0))

    # clamp to 0–10
    score = max(0.0, min(10.0, base_score))
    label = score_to_label(score)
    css_class = label_to_class(label)

    return {
        "score": round(score, 1),
        "label": label,
        "css_class": css_class
    }