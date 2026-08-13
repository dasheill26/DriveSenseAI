import os
import sqlite3
import json
from datetime import datetime


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "drivesense_history.db")


def init_scan_history_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scan_time TEXT NOT NULL,
            vehicle_name TEXT,
            health_score INTEGER,
            ml_health_score INTEGER,
            repair_urgency TEXT,
            safe_to_drive INTEGER,
            confidence REAL,
            fault_count INTEGER,
            fault_codes TEXT,
            rpm REAL,
            speed REAL,
            coolant_temp REAL,
            engine_load REAL
        )
    """)

    conn.commit()
    conn.close()


def save_scan_record(record):
    init_scan_history_db()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO scan_history (
            scan_time,
            vehicle_name,
            health_score,
            ml_health_score,
            repair_urgency,
            safe_to_drive,
            confidence,
            fault_count,
            fault_codes,
            rpm,
            speed,
            coolant_temp,
            engine_load
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record.get("time", datetime.now().strftime("%d %b %Y • %H:%M")),
        record.get("vehicle_name", "BMW 1 Series F20"),
        int(record.get("health_score", 0)),
        int(record.get("ml_health_score", 0)),
        record.get("repair_urgency", "Medium"),
        1 if record.get("safe_to_drive", True) else 0,
        float(record.get("ml_confidence", 0.7)),
        int(record.get("fault_count", 0)),
        json.dumps(record.get("fault_codes", [])),
        float(record.get("rpm", 0)),
        float(record.get("speed", 0)),
        float(record.get("coolant_temp", 0)),
        float(record.get("engine_load", 0))
    ))

    conn.commit()
    conn.close()


def get_recent_scans(limit=8):
    init_scan_history_db()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM scan_history
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()
    conn.close()

    scans = []

    for row in rows:
        scans.append({
            "id": row["id"],
            "time": row["scan_time"],
            "vehicle_name": row["vehicle_name"],
            "health_score": row["health_score"],
            "ml_health_score": row["ml_health_score"],
            "repair_urgency": row["repair_urgency"],
            "safe_to_drive": bool(row["safe_to_drive"]),
            "ml_confidence": row["confidence"],
            "fault_count": row["fault_count"],
            "fault_codes": json.loads(row["fault_codes"] or "[]"),
            "rpm": row["rpm"],
            "speed": row["speed"],
            "coolant_temp": row["coolant_temp"],
            "engine_load": row["engine_load"]
        })

    return scans


def clear_scan_history():
    init_scan_history_db()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DELETE FROM scan_history")

    conn.commit()
    conn.close()