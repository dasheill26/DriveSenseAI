import os
import sqlite3
import shutil
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "drivesense_history.db")


USER_COLUMNS = {
    "vehicle_name": "TEXT DEFAULT 'BMW 1 Series F20'",
    "vehicle_year": "TEXT DEFAULT '2018'",
    "vehicle_model": "TEXT DEFAULT '118i M Sport'",
    "vehicle_engine": "TEXT DEFAULT '1.5L Petrol'",
    "fuel_type": "TEXT DEFAULT 'Petrol'",
    "vehicle_mileage": "INTEGER DEFAULT 65081",
    "vin_number": "TEXT DEFAULT ''",
    "registration_plate": "TEXT DEFAULT 'SC67 WME'",
    "mot_expiry": "TEXT DEFAULT '2027-05-05'",
    "insurance_expiry": "TEXT DEFAULT ''",
    "notifications": "TEXT DEFAULT 'Enabled'",
    "obd_port": "TEXT DEFAULT 'COM5'",

    "vehicle_make": "TEXT DEFAULT 'BMW'",
    "vehicle_colour": "TEXT DEFAULT 'White'",
    "top_speed": "TEXT DEFAULT '130 mph'",
    "zero_to_sixty": "TEXT DEFAULT '8.7 seconds'",
    "gearbox": "TEXT DEFAULT '8 speed automatic'",
    "power": "TEXT DEFAULT '134 BHP'",
    "max_torque": "TEXT DEFAULT '220 Nm at 1,250 rpm'",
    "engine_capacity": "TEXT DEFAULT '1,499 cc'",
    "cylinders": "TEXT DEFAULT '3'",
    "fuel_consumption_city": "TEXT DEFAULT '44.1 mpg'",
    "fuel_consumption_extra_urban": "TEXT DEFAULT '61.4 mpg'",
    "fuel_consumption_combined": "TEXT DEFAULT '54.3 mpg'",
    "co2_emission": "TEXT DEFAULT '122 g/km'",
    "co2_label": "TEXT DEFAULT 'D'",

    "tax_status": "TEXT DEFAULT 'Taxed'",
    "tax_due": "TEXT DEFAULT '2027-05-01'",
    "mot_status": "TEXT DEFAULT 'MOT'",
    "mot_pass_rate": "TEXT DEFAULT '100%'",
    "mot_passed_count": "INTEGER DEFAULT 8",
    "mot_failed_count": "INTEGER DEFAULT 0",
    "mot_advisory_count": "INTEGER DEFAULT 0",
    "mot_failed_items_count": "INTEGER DEFAULT 0",

    "ncap_rating": "TEXT DEFAULT '5 stars'",
    "ncap_adult": "TEXT DEFAULT '91%'",
    "ncap_children": "TEXT DEFAULT '83%'",
    "ncap_pedestrian": "TEXT DEFAULT '63%'",
    "ncap_safety_systems": "TEXT DEFAULT '86%'",
    "ncap_overall": "TEXT DEFAULT '83%'",

    "width": "TEXT DEFAULT '1765 mm'",
    "height": "TEXT DEFAULT '1421 mm'",
    "length": "TEXT DEFAULT '4329 mm'",
    "wheel_base": "TEXT DEFAULT '2690 mm'",
    "kerb_weight": "TEXT DEFAULT '1320 kg'",
    "max_allowed_weight": "TEXT DEFAULT '1885 kg'",
    "fuel_tank_capacity": "TEXT DEFAULT '52 l'",
    "fuel_delivery": "TEXT DEFAULT 'Direct Injection'",
    "number_of_doors": "TEXT DEFAULT '5'",
    "number_of_seats": "TEXT DEFAULT '5'",
    "number_of_axles": "TEXT DEFAULT '2'",
    "engine_number": "TEXT DEFAULT '40255303'"
}


def _backup_broken_database():
    if os.path.exists(DB_PATH):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(DATA_DIR, f"broken_drivesense_history_{timestamp}.db")
        shutil.move(DB_PATH, backup_path)


def _connect():
    os.makedirs(DATA_DIR, exist_ok=True)

    try:
        conn = sqlite3.connect(DB_PATH)
        check = conn.execute("PRAGMA integrity_check").fetchone()

        if check and check[0] != "ok":
            raise sqlite3.DatabaseError("Database integrity check failed")

        conn.row_factory = sqlite3.Row
        return conn

    except sqlite3.DatabaseError:
        try:
            conn.close()
        except Exception:
            pass

        _backup_broken_database()

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn


def _column_exists(cur, table_name, column_name):
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = cur.fetchall()
    return any(column["name"] == column_name for column in columns)


def init_auth_db():
    conn = _connect()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    for column_name, column_type in USER_COLUMNS.items():
        if not _column_exists(cur, "users", column_name):
            cur.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")

    conn.commit()
    conn.close()


def create_user(name, email, password):
    init_auth_db()

    clean_name = name.strip()
    clean_email = email.lower().strip()
    password_hash = generate_password_hash(password)

    existing_user = get_user_by_email(clean_email)

    conn = _connect()
    cur = conn.cursor()

    if existing_user:
        cur.execute("""
            UPDATE users
            SET
                name = ?,
                password_hash = ?,
                vehicle_name = COALESCE(vehicle_name, 'BMW 1 Series F20'),
                vehicle_year = COALESCE(vehicle_year, '2018'),
                vehicle_model = COALESCE(vehicle_model, '118i M Sport'),
                vehicle_engine = COALESCE(vehicle_engine, '1.5L Petrol'),
                fuel_type = COALESCE(fuel_type, 'Petrol'),
                vehicle_mileage = COALESCE(vehicle_mileage, 65081),
                registration_plate = COALESCE(registration_plate, 'SC67 WME'),
                mot_expiry = COALESCE(mot_expiry, '2027-05-05'),
                notifications = COALESCE(notifications, 'Enabled'),
                obd_port = COALESCE(obd_port, 'COM5')
            WHERE email = ?
        """, (
            clean_name,
            password_hash,
            clean_email
        ))
    else:
        cur.execute("""
            INSERT INTO users (
                name,
                email,
                password_hash,
                vehicle_name,
                vehicle_year,
                vehicle_model,
                vehicle_engine,
                fuel_type,
                vehicle_mileage,
                registration_plate,
                mot_expiry,
                notifications,
                obd_port,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            clean_name,
            clean_email,
            password_hash,
            "BMW 1 Series F20",
            "2018",
            "118i M Sport",
            "1.5L Petrol",
            "Petrol",
            65081,
            "SC67 WME",
            "2027-05-05",
            "Enabled",
            "COM5",
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

    conn.commit()
    conn.close()


def get_user_by_email(email):
    init_auth_db()

    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE email = ?",
        (email.lower().strip(),)
    )

    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


def get_user_by_id(user_id):
    init_auth_db()

    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    )

    row = cur.fetchone()
    conn.close()

    return dict(row) if row else None


def verify_user(email, password):
    user = get_user_by_email(email)

    if not user:
        return None

    if check_password_hash(user["password_hash"], password):
        return user

    return None

def update_user_profile(user_id, data):
    init_auth_db()

    allowed_fields = [
        "name",
        "email",
        *USER_COLUMNS.keys()
    ]

    clean_data = {}

    for key, value in data.items():
        if key in allowed_fields:
            clean_data[key] = value

    if not clean_data:
        return

    set_clause = ", ".join([f"{key} = ?" for key in clean_data.keys()])
    values = list(clean_data.values())
    values.append(user_id)

    conn = _connect()
    cur = conn.cursor()

    cur.execute(
        f"UPDATE users SET {set_clause} WHERE id = ?",
        values
    )

    conn.commit()
    conn.close()