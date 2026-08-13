import os
import sqlite3
from datetime import datetime, timedelta


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "drivesense_history.db")


SERVICE_INTERVALS = {
    "Oil Change": {"months": 12, "miles": 10000},
    "Oil Filter": {"months": 12, "miles": 10000},
    "Air Filter": {"months": 24, "miles": 20000},
    "Cabin Filter": {"months": 12, "miles": 12000},
    "Spark Plugs": {"months": 48, "miles": 40000},
    "Brake Pads": {"months": 36, "miles": 30000},
    "Brake Fluid": {"months": 24, "miles": 20000},
    "Coolant": {"months": 48, "miles": 50000},
    "Tyres": {"months": 60, "miles": 25000},
    "MOT": {"months": 12, "miles": 0},
    "Full Service": {"months": 12, "miles": 12000}
}


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    return conn


def _column_exists(cur, table_name, column_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = cur.fetchall()

    return any(column["name"] == column_name for column in columns)


def init_service_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS service_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service_type TEXT NOT NULL,
            service_date TEXT NOT NULL,
            mileage INTEGER NOT NULL,
            notes TEXT,
            cost REAL,
            next_due_date TEXT,
            next_due_mileage INTEGER,
            created_at TEXT NOT NULL
        )
    """)

    if not _column_exists(cur, "service_records", "user_id"):
        cur.execute("""
            ALTER TABLE service_records
            ADD COLUMN user_id INTEGER
        """)

    conn.commit()
    conn.close()


def calculate_next_due(service_type, service_date, mileage):
    interval = SERVICE_INTERVALS.get(
        service_type,
        {"months": 12, "miles": 10000}
    )

    try:
        date_obj = datetime.strptime(service_date, "%Y-%m-%d")
    except Exception:
        date_obj = datetime.now()

    next_due_date = date_obj + timedelta(days=interval["months"] * 30)
    next_due_mileage = int(mileage) + int(interval["miles"])

    return {
        "next_due_date": next_due_date.strftime("%Y-%m-%d"),
        "next_due_mileage": next_due_mileage
    }


def add_service_record(
    service_type,
    service_date,
    mileage,
    notes="",
    cost=0,
    user_id=None
):
    init_service_db()

    due = calculate_next_due(
        service_type,
        service_date,
        mileage
    )

    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO service_records (
            user_id,
            service_type,
            service_date,
            mileage,
            notes,
            cost,
            next_due_date,
            next_due_mileage,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        service_type,
        service_date,
        int(mileage),
        notes,
        float(cost or 0),
        due["next_due_date"],
        due["next_due_mileage"],
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def get_service_records(user_id=None):
    init_service_db()

    conn = _connect()
    cur = conn.cursor()

    if user_id is not None:
        cur.execute("""
            SELECT *
            FROM service_records
            WHERE user_id = ?
            ORDER BY service_date DESC, id DESC
        """, (user_id,))
    else:
        cur.execute("""
            SELECT *
            FROM service_records
            ORDER BY service_date DESC, id DESC
        """)

    rows = cur.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_service_schedule(current_mileage=65000, user_id=None):
    records = get_service_records(user_id)

    latest_by_type = {}

    for record in records:
        service_type = record["service_type"]

        if service_type not in latest_by_type:
            latest_by_type[service_type] = record

    schedule = []
    today = datetime.now().date()

    for service_type, interval in SERVICE_INTERVALS.items():
        record = latest_by_type.get(service_type)

        if record:
            next_due_date = record["next_due_date"]
            next_due_mileage = record["next_due_mileage"]
            last_done = record["service_date"]
        else:
            next_due = calculate_next_due(
                service_type,
                datetime.now().strftime("%Y-%m-%d"),
                current_mileage
            )

            next_due_date = next_due["next_due_date"]
            next_due_mileage = next_due["next_due_mileage"]
            last_done = "Not logged"

        try:
            due_date_obj = datetime.strptime(
                next_due_date,
                "%Y-%m-%d"
            ).date()

            days_left = (due_date_obj - today).days
        except Exception:
            days_left = 999

        miles_left = int(next_due_mileage) - int(current_mileage)

        if days_left < 0 or miles_left < 0:
            status = "Overdue"
            css_class = "danger"
        elif days_left <= 30 or miles_left <= 1000:
            status = "Due Soon"
            css_class = "warning"
        else:
            status = "OK"
            css_class = "good"

        schedule.append({
            "service_type": service_type,
            "last_done": last_done,
            "next_due_date": next_due_date,
            "next_due_mileage": next_due_mileage,
            "days_left": days_left,
            "miles_left": miles_left,
            "status": status,
            "css_class": css_class
        })

    return schedule


def delete_service_record(record_id, user_id=None):
    init_service_db()

    conn = _connect()
    cur = conn.cursor()

    if user_id is not None:
        cur.execute("""
            DELETE FROM service_records
            WHERE id = ? AND user_id = ?
        """, (record_id, user_id))
    else:
        cur.execute("""
            DELETE FROM service_records
            WHERE id = ?
        """, (record_id,))

    conn.commit()
    conn.close()