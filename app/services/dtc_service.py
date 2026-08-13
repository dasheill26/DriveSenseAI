import json
import os
from functools import lru_cache
from typing import Optional, Dict, Any, List


@lru_cache(maxsize=1)
def load_dtc_db() -> Dict[str, Dict[str, Any]]:
    base_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, "..", ".."))
    db_path = os.path.join(project_root, "data", "dtc_database.json")

    if not os.path.exists(db_path):
        return {}

    with open(db_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    normalized = {}

    for key, value in data.items():
        normalized[str(key).upper().strip()] = value

    return normalized


def get_dtc(code: str) -> Optional[Dict[str, Any]]:
    if not code:
        return None

    db = load_dtc_db()
    return db.get(code.upper().strip())


def _as_list(value) -> List[str]:
    if not value:
        return []

    if isinstance(value, list):
        return value

    if isinstance(value, str):
        return [value]

    return []


def get_dtc_intelligence(code: str) -> Dict[str, Any]:
    record = get_dtc(code) or {}
    clean_code = str(code or "").upper().strip()

    title = record.get("title", "Unknown Diagnostic Trouble Code")
    definition = record.get("definition", "The vehicle ECU has detected an abnormal condition.")
    severity = str(record.get("severity", "medium")).lower()

    causes = _as_list(record.get("common_causes"))
    fixes = _as_list(record.get("recommended_fixes"))

    if not causes:
        causes = [
            "Sensor reading outside expected range",
            "Wiring, connector or electrical issue",
            "Component wear or failure",
            "ECU detected abnormal operating condition"
        ]

    if not fixes:
        fixes = [
            "Confirm the code with a diagnostic scan",
            "Inspect related wiring and connectors",
            "Check live data for abnormal readings",
            "Book professional inspection if the warning returns"
        ]

    if severity in ["critical", "high"]:
        safe_to_drive = False
        drive_advice = "Avoid unnecessary driving. Continued use may cause further damage."
        urgency = "High priority"
        risk_label = "High Risk"
    elif severity in ["medium", "moderate"]:
        safe_to_drive = True
        drive_advice = "Drive carefully and arrange inspection soon, especially if symptoms are present."
        urgency = "Inspection recommended"
        risk_label = "Moderate Risk"
    else:
        safe_to_drive = True
        drive_advice = "Usually safe to drive short-term, but monitor symptoms and re-scan."
        urgency = "Monitor"
        risk_label = "Low Risk"

    affected_system = "Engine Management"

    if clean_code.startswith("P03"):
        affected_system = "Ignition / Misfire System"
    elif clean_code.startswith("P01"):
        affected_system = "Fuel / Air Mixture System"
    elif clean_code.startswith("P04"):
        affected_system = "Emissions / EGR System"
    elif clean_code.startswith("P05"):
        affected_system = "Idle / Speed Control System"
    elif clean_code.startswith("P06"):
        affected_system = "ECU / Computer Control System"

    return {
        "code": clean_code,
        "title": title,
        "definition": definition,
        "severity": severity,
        "risk_label": risk_label,
        "affected_system": affected_system,
        "safe_to_drive": safe_to_drive,
        "drive_advice": drive_advice,
        "repair_urgency": urgency,
        "common_causes": causes,
        "recommended_fixes": fixes,
        "ai_summary": (
            f"{clean_code} relates to {affected_system}. "
            f"{definition} DriveSense classifies this as {risk_label}. "
            f"{drive_advice}"
        )
    }