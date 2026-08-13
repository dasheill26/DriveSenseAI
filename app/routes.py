import os
import json
import base64
import requests

from datetime import datetime
from types import SimpleNamespace
from io import BytesIO
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    request,
    session,
    jsonify,
    redirect,
    send_file,
    current_app
)

from app.services.health_engine import calculate_health_score
from app.services.severity_engine import compute_severity
from app.services.scan_history_service import (
    save_scan_record,
    get_recent_scans,
    clear_scan_history
)
from app.services.service_record_service import (
    add_service_record,
    get_service_records,
    get_service_schedule,
    delete_service_record
)
from app.services.auth_service import (
    create_user,
    verify_user,
    init_auth_db,
    get_user_by_id,
    update_user_profile
)

try:
    from app.ml.predictor import (
        predict_vehicle_risk,
        predict_component_maintenance
    )
except Exception:
    predict_vehicle_risk = None
    predict_component_maintenance = None


main = Blueprint("main", __name__)

# =====================================================
# DEMO / ENET MODE
# =====================================================
# Final project mode:
# BMW ENET requires BMW-specific diagnostic protocols.
# For project stability, the prototype uses safe simulated
# OBD-II / ENET demo data.
obd_service = None

DEMO_OBD_MODE = "BMW ENET / OBD-II Demo Mode"


EXTRA_USER_FIELDS = [
    "vehicle_make",
    "vehicle_colour",
    "top_speed",
    "zero_to_sixty",
    "gearbox",
    "power",
    "max_torque",
    "engine_capacity",
    "cylinders",
    "fuel_consumption_city",
    "fuel_consumption_extra_urban",
    "fuel_consumption_combined",
    "co2_emission",
    "co2_label",
    "tax_status",
    "tax_due",
    "mot_status",
    "mot_pass_rate",
    "mot_passed_count",
    "mot_failed_count",
    "mot_advisory_count",
    "mot_failed_items_count",
    "ncap_rating",
    "ncap_adult",
    "ncap_children",
    "ncap_pedestrian",
    "ncap_safety_systems",
    "ncap_overall",
    "width",
    "height",
    "length",
    "wheel_base",
    "kerb_weight",
    "max_allowed_weight",
    "fuel_tank_capacity",
    "fuel_delivery",
    "number_of_doors",
    "number_of_seats",
    "number_of_axles",
    "engine_number"
]


# =====================================================
# AUTH HELPERS
# =====================================================

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login")
        return fn(*args, **kwargs)
    return wrapper


def _user_id():
    return session.get("user_id")


def _load_user_into_session(user):
    if not user:
        return

    session["user_id"] = user.get("id")
    session["user_name"] = user.get("name", "DriveSense User")
    session["user_email"] = user.get("email", "")

    session["vehicle_name"] = user.get("vehicle_name") or "BMW 1 Series F20"
    session["vehicle_year"] = user.get("vehicle_year") or "2018"
    session["vehicle_model"] = user.get("vehicle_model") or "118i M Sport"
    session["vehicle_engine"] = user.get("vehicle_engine") or "1.5L Petrol"
    session["fuel_type"] = user.get("fuel_type") or "Petrol"
    session["vehicle_mileage"] = int(user.get("vehicle_mileage") or 65081)

    session["vin_number"] = user.get("vin_number") or ""
    session["registration_plate"] = user.get("registration_plate") or "SC67 WME"
    session["mot_expiry"] = user.get("mot_expiry") or "2027-05-05"
    session["insurance_expiry"] = user.get("insurance_expiry") or ""
    session["notifications"] = user.get("notifications") or "Enabled"
    session["obd_port"] = user.get("obd_port") or DEMO_OBD_MODE

    for field in EXTRA_USER_FIELDS:
        if field in user:
            session[field] = user.get(field)


def _refresh_user_session():
    user_id = session.get("user_id")

    if user_id:
        user = get_user_by_id(user_id)

        if user:
            _load_user_into_session(user)


def _auth_context():
    return {
        "vehicle_name": session.get("vehicle_name", "BMW 1 Series F20"),
        "vehicle_year": session.get("vehicle_year", "2018"),
        "connected": False,
        "last_scan": None,
        "active_page": "auth"
    }


# =====================================================
# AUTH ROUTES
# =====================================================

@main.route("/login", methods=["GET", "POST"])
def login():
    init_auth_db()

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        user = verify_user(email, password)

        if user:
            _load_user_into_session(user)
            return redirect("/")

        return render_template(
            "login.html",
            error="Invalid email or password",
            **_auth_context()
        )

    return render_template("login.html", **_auth_context())


@main.route("/register", methods=["GET", "POST"])
def register():
    init_auth_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not name or not email or not password:
            return render_template(
                "register.html",
                error="Please complete all fields",
                **_auth_context()
            )

        if password != confirm_password:
            return render_template(
                "register.html",
                error="Passwords do not match",
                **_auth_context()
            )

        try:
            create_user(name, email, password)
            user = verify_user(email, password)
            _load_user_into_session(user)
            return redirect("/")

        except Exception:
            return render_template(
                "register.html",
                error="Account already exists or could not be created",
                **_auth_context()
            )

    return render_template("register.html", **_auth_context())


@main.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# =====================================================
# CORE HELPERS
# =====================================================

def _data_path(*parts):
    return os.path.join(os.path.dirname(__file__), "data", *parts)


def _load_dtc_db():
    file = _data_path("dtc_database.json")

    if not os.path.exists(file):
        return {}

    with open(file, "r", encoding="utf-8") as f:
        return json.load(f)


def _now():
    return datetime.now().strftime("%d %b %Y • %H:%M")


def _safe_number(value, fallback=0):
    try:
        if isinstance(value, str):
            value = value.replace("°C", "")
            value = value.replace("degC", "")
            value = value.replace("%", "")
            value = value.replace("rpm", "")
            value = value.replace("RPM", "")
            value = value.replace("mph", "")
            value = value.replace("km/h", "")
            value = value.replace("mi", "")
            value = value.strip()

        return float(value)

    except Exception:
        return fallback


def _get_connection_status():
    return {
        "connected": session.get("connected", False),
        "demo_mode": True,
        "port": DEMO_OBD_MODE
    }


def _get_live_data():
    live_data = session.get("live_data") or {
        "rpm": 820,
        "speed": 0,
        "coolant_temp": 91,
        "engine_load": 18,
        "throttle": 18,
        "fuel_level": 82
    }

    session["live_data"] = live_data
    return live_data


def _get_faults():
    db = _load_dtc_db()
    codes = session.get("fault_codes") or ["P0301", "P0171"]

    faults = []

    for code in codes:
        rec = db.get(code.upper(), {})
        severity = compute_severity(rec)

        faults.append(
            SimpleNamespace(
                code=code.upper(),
                title=rec.get("title", "Engine Fault"),
                definition=rec.get("definition", "ECU detected issue."),
                severity=rec.get("severity", "medium"),
                severity_score=severity["score"],
                severity_label=severity["label"],
                sev_class=severity["css_class"],
                causes=rec.get("common_causes", []),
                solutions=rec.get("recommended_fixes", [])
            )
        )

    return faults


def _get_severity_score(faults):
    if not faults:
        return 1

    return sum(float(f.severity_score) for f in faults) / len(faults)


def _ml_context():
    faults = _get_faults()
    severity_score = _get_severity_score(faults)

    live_data = session.get("live_data") or _get_live_data()

    coolant_temp = _safe_number(live_data.get("coolant_temp", 91), 91)
    engine_load = _safe_number(live_data.get("engine_load", 18), 18)
    rpm = _safe_number(live_data.get("rpm", 820), 820)

    if predict_vehicle_risk:
        prediction = predict_vehicle_risk(
            fault_count=len(faults),
            coolant_temp=coolant_temp,
            engine_load=engine_load,
            rpm=rpm,
            severity_score=severity_score
        )
    else:
        prediction = {
            "ml_health_score": session.get("health_score", 82),
            "repair_urgency": "medium",
            "safe_to_drive": True,
            "confidence": 0.7,
            "model_used": "fallback"
        }

    urgency = str(prediction.get("repair_urgency", "medium")).lower()
    urgency_label = urgency.capitalize()
    safe_to_drive = prediction.get("safe_to_drive", True)

    if urgency == "critical":
        ml_message = "Critical risk detected. Avoid driving until checked."
    elif urgency == "high":
        ml_message = "High repair urgency. Book inspection soon."
    elif urgency == "medium":
        ml_message = "Moderate risk. Monitor symptoms and inspect soon."
    else:
        ml_message = "Low risk. Vehicle appears usable."

    return {
        "ml_prediction": prediction,
        "ml_health_score": prediction.get("ml_health_score", session.get("health_score", 82)),
        "repair_urgency": urgency_label,
        "safe_to_drive": safe_to_drive,
        "ml_confidence": prediction.get("confidence", 0.7),
        "ml_message": ml_message,
        "ml_model_used": prediction.get("model_used", "fallback")
    }


def _seed_real_service_records():
    user_id = _user_id()
    records = get_service_records(user_id)

    if records and len(records) > 0:
        return

    real_records = [
        {"date": "2025-01-10", "mileage": 65081, "notes": "Service completed at OSS Glasgow independent BMW specialists LTD. Overview: Automatic."},
        {"date": "2023-02-14", "mileage": 47609, "notes": "Service completed at OSS Glasgow independent BMW specialists LTD. Overview: Automatic."},
        {"date": "2021-12-17", "mileage": 36575, "notes": "Service completed at OSS Glasgow independent BMW specialists LTD. Overview: Manual."},
        {"date": "2021-02-05", "mileage": 26219, "notes": "Service completed at Harry Fairbairn Glasgow. Overview: Automatic."},
        {"date": "2020-01-28", "mileage": 18032, "notes": "Service completed at Harry Fairbairn Glasgow. Overview: Automatic."},
        {"date": "2018-03-05", "mileage": 12, "notes": "Pre-delivery/new vehicle service completed at Harry Fairbairn Glasgow. Overview: Manual."}
    ]

    for record in real_records:
        add_service_record(
            service_type="Full Service",
            service_date=record["date"],
            mileage=record["mileage"],
            notes=record["notes"],
            cost=0,
            user_id=user_id
        )


def _service_context():
    _seed_real_service_records()

    current_mileage = int(session.get("vehicle_mileage", 65081))
    schedule = get_service_schedule(current_mileage, _user_id())

    due_items = [
        item for item in schedule
        if item.get("status") in ["Overdue", "Due Soon"]
    ]

    next_service_item = due_items[0] if due_items else (
        schedule[0] if schedule else None
    )

    return {
        "vehicle_mileage": current_mileage,
        "service_schedule": schedule,
        "due_items": due_items,
        "next_service_item": next_service_item
    }


def _vehicle_report_context():
    mot_history = [
        {"label": "MOT #8", "date": "2026-05-02 10:41", "test_number": "572525247768", "result": "Passed", "next_expiry": "2027-05-05"},
        {"label": "MOT #7", "date": "2025-05-06 14:46", "test_number": "114821838583", "result": "Passed"},
        {"label": "MOT #6", "date": "2025-03-04 10:35", "test_number": "892503774771", "result": "Passed"},
        {"label": "MOT #5", "date": "2024-03-01 13:13", "test_number": "298858937593", "result": "Passed"},
        {"label": "MOT #4", "date": "2023-03-03 14:32", "test_number": "539261112280", "result": "Passed"},
        {"label": "MOT #3", "date": "2022-03-01 11:58", "test_number": "654498603142", "result": "Passed"},
        {"label": "MOT #2", "date": "2021-03-05 10:00", "test_number": "409975113744", "result": "Passed"},
        {"label": "MOT #1", "date": "2020-09-10 15:50", "test_number": "386637129911", "result": "Passed"}
    ]

    return {
        "mot_history": mot_history,
        "report_date": datetime.now().strftime("%Y-%m-%d")
    }


def _add_scan_history(health_score, fault_codes, live_data, ml_data):
    record = {
        "time": _now(),
        "user_id": _user_id(),
        "vehicle_name": session.get("vehicle_name", "BMW 1 Series F20"),
        "health_score": int(health_score),
        "fault_count": len(fault_codes),
        "fault_codes": fault_codes,
        "repair_urgency": ml_data.get("repair_urgency", "Medium"),
        "safe_to_drive": ml_data.get("safe_to_drive", True),
        "ml_health_score": int(ml_data.get("ml_health_score", health_score)),
        "ml_confidence": float(ml_data.get("ml_confidence", 0.7)),
        "rpm": _safe_number(live_data.get("rpm", 820), 820),
        "speed": _safe_number(live_data.get("speed", 0), 0),
        "coolant_temp": _safe_number(live_data.get("coolant_temp", 91), 91),
        "engine_load": _safe_number(live_data.get("engine_load", 18), 18)
    }

    try:
        save_scan_record(record)
    except Exception as e:
        print("SCAN HISTORY SAVE ERROR:", e)

    session_history = session.get("scan_history", [])
    session_history.insert(0, record)
    session["scan_history"] = session_history[:8]
    session.modified = True

    return record


def _vehicle_context():
    _refresh_user_session()

    ml_data = _ml_context()
    connection_status = _get_connection_status()

    try:
        recent = get_recent_scans(8)
    except Exception as e:
        print("SCAN HISTORY LOAD ERROR:", e)
        recent = []

    if not recent:
        recent = session.get("scan_history", [])

    service_data = _service_context()

    context = dict(
        connected=session.get("connected", False) or connection_status.get("connected", False),
        demo_mode=connection_status.get("demo_mode", True),
        obd_port=session.get("obd_port", connection_status.get("port", DEMO_OBD_MODE)),
        vehicle_name=session.get("vehicle_name", "BMW 1 Series F20"),
        vehicle_year=session.get("vehicle_year", "2018"),
        vehicle_model=session.get("vehicle_model", "118i M Sport"),
        vehicle_engine=session.get("vehicle_engine", "1.5L Petrol"),
        fuel_type=session.get("fuel_type", "Petrol"),
        vin_number=session.get("vin_number", ""),
        registration_plate=session.get("registration_plate", "SC67 WME"),
        mot_expiry=session.get("mot_expiry", "2027-05-05"),
        insurance_expiry=session.get("insurance_expiry", ""),
        notifications=session.get("notifications", "Enabled"),
        user_name=session.get("user_name", "DriveSense User"),
        user_email=session.get("user_email", "user@drivesense.local"),
        last_scan=session.get("last_scan"),
        health_score=session.get("health_score", 82),
        scan_history=recent,
        recent_scans=recent[:5],
        **service_data,
        **ml_data
    )

    for field in EXTRA_USER_FIELDS:
        context[field] = session.get(field, "")

    return context


# =====================================================
# PAGE ROUTES
# =====================================================

@main.route("/")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        active_page="dashboard",
        faults=_get_faults(),
        **_vehicle_context()
    )


@main.route("/diagnostics")
@login_required
def diagnostics():
    return render_template(
        "diagnostics.html",
        active_page="diagnostics",
        faults=_get_faults(),
        **_vehicle_context()
    )


@main.route("/fault/<code>")
@login_required
def fault_detail(code):
    db = _load_dtc_db()
    rec = db.get(code.upper(), {})
    severity = compute_severity(rec)

    fault = {
        "code": code.upper(),
        "title": rec.get("title", "Engine Fault"),
        "definition": rec.get("definition", "ECU detected abnormal condition."),
        "severity": rec.get("severity", "medium"),
        "severity_score": severity["score"],
        "severity_label": severity["label"],
        "sev_class": severity["css_class"],
        "causes": rec.get("common_causes", []),
        "solutions": rec.get("recommended_fixes", [])
    }

    return render_template(
        "fault_detail.html",
        fault=fault,
        active_page="diagnostics",
        **_vehicle_context()
    )


@main.route("/profile")
@login_required
def profile():
    return render_template(
        "profile.html",
        active_page="profile",
        faults=_get_faults(),
        **_vehicle_context()
    )


@main.route("/vehicle-report")
@login_required
def vehicle_report_page():
    return render_template(
        "vehicle_report.html",
        active_page="vehicle_report",
        faults=_get_faults(),
        **_vehicle_context(),
        **_vehicle_report_context()
    )


@main.route("/scan")
@login_required
def scan():
    return render_template(
        "scan.html",
        active_page="scan",
        **_vehicle_context()
    )


@main.route("/live")
@login_required
def live_page():
    return render_template(
        "live.html",
        active_page="live",
        **_vehicle_context()
    )


@main.route("/ai")
@login_required
def ai_page():
    code = request.args.get("code", "")

    return render_template(
        "ai.html",
        active_page="ai",
        code=code,
        **_vehicle_context()
    )


@main.route("/service")
@login_required
def service_page():
    context = _vehicle_context()

    return render_template(
        "service.html",
        active_page="service",
        service_records=get_service_records(_user_id()),
        current_mileage=context["vehicle_mileage"],
        **context
    )


@main.route("/predictive")
@login_required
def predictive_page():
    current_mileage = int(session.get("vehicle_mileage", 65081))
    faults = _get_faults()
    live_data = session.get("live_data") or _get_live_data()
    service_records = get_service_records(_user_id())

    severity_score = _get_severity_score(faults)

    if predict_component_maintenance:
        predictive_items = predict_component_maintenance(
            current_mileage=current_mileage,
            fault_count=len(faults),
            coolant_temp=_safe_number(live_data.get("coolant_temp", 91), 91),
            engine_load=_safe_number(live_data.get("engine_load", 18), 18),
            rpm=_safe_number(live_data.get("rpm", 820), 820),
            severity_score=severity_score,
            service_records=service_records
        )
    else:
        predictive_items = [
            {
                "component": "Engine Oil",
                "status": "Due Soon",
                "risk": 72,
                "remaining_miles": 1200,
                "recommendation": "Oil quality degrading. Book oil service soon."
            },
            {
                "component": "Brake Pads",
                "status": "Monitor",
                "risk": 48,
                "remaining_miles": 4200,
                "recommendation": "Brake wear detected from mileage pattern."
            },
            {
                "component": "Battery",
                "status": "Attention Recommended",
                "risk": 63,
                "remaining_miles": 2500,
                "recommendation": "Voltage aging pattern detected."
            }
        ]

    return render_template(
        "predictive.html",
        active_page="predictive",
        predictive_items=predictive_items,
        current_mileage=current_mileage,
        faults=faults,
        **_vehicle_context()
    )


@main.route("/project-evidence")
@login_required
def project_evidence_page():
    return render_template(
        "project_evidence.html",
        active_page="project_evidence",
        faults=_get_faults(),
        **_vehicle_context()
    )


# =====================================================
# PROFILE API
# =====================================================

@main.route("/api/update_profile", methods=["POST"])
@login_required
def update_profile_api():
    try:
        form = request.form
        user_id = session.get("user_id")
        data = {}

        field_map = {
            "user_name": "name",
            "user_email": "email",
            "vehicle_name": "vehicle_name",
            "vehicle_year": "vehicle_year",
            "vehicle_model": "vehicle_model",
            "vehicle_engine": "vehicle_engine",
            "fuel_type": "fuel_type",
            "vehicle_mileage": "vehicle_mileage",
            "vin_number": "vin_number",
            "registration_plate": "registration_plate",
            "mot_expiry": "mot_expiry",
            "insurance_expiry": "insurance_expiry",
            "notifications": "notifications",
            "obd_port": "obd_port"
        }

        for field in EXTRA_USER_FIELDS:
            field_map[field] = field

        for form_key, db_key in field_map.items():
            if form_key in form:
                value = form.get(form_key, "").strip()

                if form_key in [
                    "vehicle_mileage",
                    "mot_passed_count",
                    "mot_failed_count",
                    "mot_advisory_count",
                    "mot_failed_items_count"
                ]:
                    try:
                        value = int(value)
                    except Exception:
                        value = 0

                data[db_key] = value

        update_user_profile(user_id, data)

        updated_user = get_user_by_id(user_id)
        _load_user_into_session(updated_user)

        return redirect("/profile")

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =====================================================
# SERVICE API
# =====================================================

@main.route("/api/service_records")
@login_required
def service_records_api():
    service_data = _service_context()

    return jsonify({
        "ok": True,
        "service_records": get_service_records(_user_id()),
        "service_schedule": service_data["service_schedule"],
        "due_items": service_data["due_items"],
        "next_service_item": service_data["next_service_item"]
    })


@main.route("/api/add_service_record", methods=["POST"])
@login_required
def add_service_record_api():
    try:
        data = request.form if request.form else request.get_json()

        service_type = data.get("service_type", "Full Service")
        service_date = data.get("service_date", datetime.now().strftime("%Y-%m-%d"))
        mileage = int(data.get("mileage", 65081))
        notes = data.get("notes", "")
        cost = float(data.get("cost", 0) or 0)

        add_service_record(
            service_type=service_type,
            service_date=service_date,
            mileage=mileage,
            notes=notes,
            cost=cost,
            user_id=_user_id()
        )

        session["vehicle_mileage"] = max(
            int(session.get("vehicle_mileage", 65081)),
            mileage
        )

        if session.get("user_id"):
            update_user_profile(
                session["user_id"],
                {"vehicle_mileage": session["vehicle_mileage"]}
            )

        return redirect("/service")

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@main.route("/api/delete_service_record/<int:record_id>", methods=["POST", "GET"])
@login_required
def delete_service_record_api(record_id):
    delete_service_record(record_id, _user_id())
    return redirect("/service")


# =====================================================
# CONNECT / DISCONNECT
# =====================================================

@main.route("/connect")
@login_required
def connect_vehicle():
    live_data = _get_live_data()

    session["connected"] = True
    session["last_scan"] = _now()
    session["health_score"] = 92
    session["fault_codes"] = ["P0301", "P0171"]
    session["live_data"] = live_data
    session["obd_port"] = DEMO_OBD_MODE

    return redirect("/")


@main.route("/disconnect", methods=["POST", "GET"])
@login_required
def disconnect_vehicle():
    keep_user = {
        "user_id": session.get("user_id"),
        "user_name": session.get("user_name"),
        "user_email": session.get("user_email"),
        "vehicle_name": session.get("vehicle_name"),
        "vehicle_year": session.get("vehicle_year"),
        "vehicle_mileage": session.get("vehicle_mileage"),
        "vehicle_model": session.get("vehicle_model"),
        "vehicle_engine": session.get("vehicle_engine"),
        "fuel_type": session.get("fuel_type"),
        "vin_number": session.get("vin_number"),
        "registration_plate": session.get("registration_plate"),
        "mot_expiry": session.get("mot_expiry"),
        "insurance_expiry": session.get("insurance_expiry"),
        "notifications": session.get("notifications"),
        "obd_port": DEMO_OBD_MODE
    }

    for field in EXTRA_USER_FIELDS:
        keep_user[field] = session.get(field)

    session.clear()

    for key, value in keep_user.items():
        if value is not None:
            session[key] = value

    session["connected"] = False

    return redirect("/")


# =====================================================
# LIVE DATA / SCAN API
# =====================================================

@main.route("/api/live_data")
@login_required
def live_data_api():
    try:
        live_data = _get_live_data()
        connection_status = _get_connection_status()

        rpm = _safe_number(live_data.get("rpm", 820), 820)
        speed = _safe_number(live_data.get("speed", 0), 0)
        coolant_temp = _safe_number(live_data.get("coolant_temp", 91), 91)
        engine_load = _safe_number(live_data.get("engine_load", 18), 18)
        throttle = _safe_number(live_data.get("throttle", 18), 18)
        fuel_level = _safe_number(live_data.get("fuel_level", 82), 82)

        session["live_data"] = {
            "rpm": rpm,
            "speed": speed,
            "coolant_temp": coolant_temp,
            "engine_load": engine_load,
            "throttle": throttle,
            "fuel_level": fuel_level
        }

        return jsonify({
            "ok": True,
            "connected": connection_status.get("connected", False),
            "demo_mode": connection_status.get("demo_mode", True),
            "port": connection_status.get("port", DEMO_OBD_MODE),
            "rpm": rpm,
            "speed": speed,
            "coolant_temp": coolant_temp,
            "engine_load": engine_load,
            "throttle": throttle,
            "fuel_level": fuel_level,
            **_ml_context()
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "error": str(e),
            "rpm": 820,
            "speed": 0,
            "coolant_temp": 91,
            "engine_load": 18,
            "throttle": 18,
            "fuel_level": 82,
            "connected": False,
            "demo_mode": True,
            "port": DEMO_OBD_MODE
        })


@main.route("/api/real_scan", methods=["POST"])
@login_required
def real_scan():
    try:
        live_data = _get_live_data()

        dtc_codes = ["P0301", "P0171"]

        health = calculate_health_score(live_data, dtc_codes)

        session["fault_codes"] = dtc_codes
        session["health_score"] = health
        session["last_scan"] = _now()
        session["connected"] = True
        session["live_data"] = live_data
        session["obd_port"] = DEMO_OBD_MODE

        ml_data = _ml_context()
        scan_record = _add_scan_history(health, dtc_codes, live_data, ml_data)

        try:
            recent = get_recent_scans(8)
        except Exception:
            recent = session.get("scan_history", [])

        return jsonify({
            "ok": True,
            "fault_codes": dtc_codes,
            "health_score": health,
            "live_data": live_data,
            "scan_record": scan_record,
            "scan_history": recent,
            "demo_mode": True,
            "port": DEMO_OBD_MODE,
            **ml_data
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@main.route("/api/scan_history")
@login_required
def scan_history_api():
    try:
        recent = get_recent_scans(8)
    except Exception:
        recent = []

    if not recent:
        recent = session.get("scan_history", [])

    return jsonify({
        "ok": True,
        "scan_history": recent
    })


@main.route("/api/clear_scan_history", methods=["POST"])
@login_required
def clear_scan_history_api():
    clear_scan_history()
    session["scan_history"] = []
    session.modified = True

    return jsonify({
        "ok": True,
        "scan_history": []
    })


@main.route("/api/ml_prediction")
@login_required
def ml_prediction_api():
    _get_live_data()

    return jsonify({
        "ok": True,
        **_ml_context()
    })


# =====================================================
# PDF REPORT EXPORT
# =====================================================

@main.route("/report/pdf")
@login_required
def export_pdf_report():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import (
            SimpleDocTemplate,
            Paragraph,
            Spacer,
            Table,
            TableStyle,
            Image as RLImage,
            PageBreak
        )

        buffer = BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=34,
            leftMargin=34,
            topMargin=30,
            bottomMargin=30
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "DriveSenseTitle",
            parent=styles["Title"],
            fontSize=26,
            textColor=colors.HexColor("#00AEEF"),
            spaceAfter=6
        )

        subtitle_style = ParagraphStyle(
            "DriveSenseSubtitle",
            parent=styles["BodyText"],
            fontSize=10,
            textColor=colors.HexColor("#4B5563"),
            alignment=1,
            spaceAfter=12
        )

        heading_style = ParagraphStyle(
            "DriveSenseHeading",
            parent=styles["Heading2"],
            fontSize=15,
            textColor=colors.HexColor("#111827"),
            spaceBefore=12,
            spaceAfter=8
        )

        normal = styles["BodyText"]

        faults = _get_faults()
        ml_data = _ml_context()
        live_data = session.get("live_data") or _get_live_data()
        service_data = _service_context()
        service_records = get_service_records(_user_id())
        connection_status = _get_connection_status()

        story = []

        story.append(Paragraph("DriveSense AI Diagnostic Report", title_style))
        story.append(Paragraph(
            "Vehicle health • fault analysis • maintenance prediction • AI risk summary",
            subtitle_style
        ))

        image_candidates = [
            os.path.join(current_app.static_folder, "img", "my_car.png"),
            os.path.join(current_app.root_path, "static", "img", "my_car.png"),
            os.path.join(os.getcwd(), "static", "img", "my_car.png"),
            os.path.join(os.getcwd(), "app", "static", "img", "my_car.png")
        ]

        car_image_path = None

        for path in image_candidates:
            if path and os.path.exists(path):
                car_image_path = path
                break

        if car_image_path:
            try:
                car_img = RLImage(car_image_path)
                car_img.drawWidth = 420
                car_img.drawHeight = 190
                car_img.hAlign = "CENTER"
                story.append(car_img)
                story.append(Spacer(1, 12))
            except Exception:
                story.append(Spacer(1, 6))

        status_colour = colors.HexColor("#16A34A") if ml_data["safe_to_drive"] else colors.HexColor("#DC2626")

        summary_table = Table([
            ["Owner", session.get("user_name", "DriveSense User"), "Generated", _now()],
            ["Vehicle", session.get("vehicle_name", "BMW 1 Series F20"), "Year", session.get("vehicle_year", "2018")],
            ["Mileage", f'{service_data["vehicle_mileage"]} mi', "Mode", "Demo Mode" if connection_status.get("demo_mode", True) else "Live OBD"],
            ["Registration", session.get("registration_plate", "SC67 WME"), "MOT Expiry", session.get("mot_expiry", "2027-05-05")],
            ["Health Score", f'{session.get("health_score", 82)}%', "ML Health", f'{ml_data["ml_health_score"]}%'],
            ["Faults Found", str(len(faults)), "Safe To Drive", "Yes" if ml_data["safe_to_drive"] else "No"],
            ["Urgency", ml_data["repair_urgency"], "Email", session.get("user_email", "N/A")]
        ], colWidths=[95, 150, 95, 150])

        summary_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("TEXTCOLOR", (3, 5), (3, 5), status_colour),
            ("PADDING", (0, 0), (-1, -1), 8)
        ]))

        story.append(summary_table)

        story.append(Paragraph("Diagnostic Recommendation", heading_style))
        story.append(Paragraph(
            f'DriveSense AI has assessed the vehicle as '
            f'<b>{"safe to drive" if ml_data["safe_to_drive"] else "not safe to drive"}</b> '
            f'with <b>{ml_data["repair_urgency"]}</b> repair urgency. '
            f'{ml_data["ml_message"]}',
            normal
        ))

        story.append(Paragraph("Live Vehicle Data", heading_style))

        live_table = Table([
            ["RPM", str(live_data.get("rpm", "N/A")), "Speed", str(live_data.get("speed", "N/A"))],
            ["Coolant", str(live_data.get("coolant_temp", "N/A")), "Engine Load", str(live_data.get("engine_load", "N/A"))],
            ["Throttle", str(live_data.get("throttle", "N/A")), "Fuel Level", str(live_data.get("fuel_level", "N/A"))]
        ], colWidths=[115, 125, 115, 125])

        live_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 8)
        ]))

        story.append(live_table)

        story.append(Paragraph("Detected Fault Codes", heading_style))

        if faults:
            fault_rows = [["Code", "Fault Title", "Severity", "Definition"]]

            for fault in faults:
                fault_rows.append([
                    fault.code,
                    fault.title,
                    fault.severity_label,
                    fault.definition
                ])

            fault_table = Table(
                fault_rows,
                colWidths=[58, 130, 70, 222]
            )

            fault_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#00AEEF")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP")
            ]))

            story.append(fault_table)
        else:
            story.append(Paragraph("No active faults detected.", normal))

        story.append(PageBreak())
        story.append(Paragraph("Vehicle Report Details", heading_style))

        vehicle_rows = [
            ["Make", session.get("vehicle_make", "BMW"), "Model", session.get("vehicle_model", "118i M Sport")],
            ["Colour", session.get("vehicle_colour", "White"), "Gearbox", session.get("gearbox", "8 speed automatic")],
            ["Power", session.get("power", "134 BHP"), "Torque", session.get("max_torque", "220 Nm at 1,250 rpm")],
            ["CO2", session.get("co2_emission", "122 g/km"), "CO2 Label", session.get("co2_label", "D")],
            ["Tax", session.get("tax_status", "Taxed"), "Tax Due", session.get("tax_due", "2027-05-01")]
        ]

        vehicle_table = Table(vehicle_rows, colWidths=[95, 150, 95, 150])
        vehicle_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
            ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
            ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
            ("PADDING", (0, 0), (-1, -1), 8)
        ]))

        story.append(vehicle_table)

        story.append(Paragraph("Service Records", heading_style))

        if service_records:
            service_rows = [["Date", "Type", "Mileage", "Notes"]]

            for record in service_records[:12]:
                service_rows.append([
                    record.get("service_date", ""),
                    record.get("service_type", ""),
                    f'{record.get("mileage", "")} mi',
                    record.get("notes", "")[:110]
                ])

            service_table = Table(
                service_rows,
                colWidths=[80, 95, 80, 225]
            )

            service_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#111827")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#CBD5E1")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("PADDING", (0, 0), (-1, -1), 7),
                ("VALIGN", (0, 0), (-1, -1), "TOP")
            ]))

            story.append(service_table)
        else:
            story.append(Paragraph("No service records stored.", normal))

        story.append(Spacer(1, 16))
        story.append(Paragraph(
            "Report generated by DriveSense AI. This report is intended for diagnostic support and should not replace professional mechanical inspection.",
            normal
        ))

        doc.build(story)
        buffer.seek(0)

        return send_file(
            buffer,
            as_attachment=True,
            download_name="DriveSense_Diagnostic_Report.pdf",
            mimetype="application/pdf"
        )

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =====================================================
# AI CHAT
# =====================================================

@main.route("/api/ai_chat", methods=["POST"])
@login_required
def ai_chat():
    try:
        data = request.get_json()
        message = data.get("message", "").strip()

        if not message:
            return jsonify({"ok": False, "error": "No message"}), 400

        ml_data = _ml_context()
        live_data = session.get("live_data") or _get_live_data()

        prompt = f"""
You are DriveSense AI.

You are a professional automotive technician and intelligent diagnostic assistant.

Current mode:
- {DEMO_OBD_MODE}

Current live data:
- RPM: {live_data.get("rpm", "N/A")}
- Speed: {live_data.get("speed", "N/A")}
- Coolant temperature: {live_data.get("coolant_temp", "N/A")}
- Engine load: {live_data.get("engine_load", "N/A")}
- Throttle: {live_data.get("throttle", "N/A")}
- Fuel level: {live_data.get("fuel_level", "N/A")}

Current ML prediction:
- ML health score: {ml_data["ml_health_score"]}%
- Repair urgency: {ml_data["repair_urgency"]}
- Safe to drive: {ml_data["safe_to_drive"]}
- ML message: {ml_data["ml_message"]}

User said:
{message}

Reply professionally and clearly. Keep the explanation practical and useful for a vehicle owner.
"""

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llama3",
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        result = response.json()
        answer = result.get("response", "").strip()

        return jsonify({
            "ok": True,
            "answer": answer
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# =====================================================
# IMAGE ANALYSIS
# =====================================================

@main.route("/api/image_analyze", methods=["POST"])
@main.route("/api/analyze_image", methods=["POST"])
@login_required
def image_analyze():
    try:
        data = request.get_json()
        image_data = data.get("image", "")

        if not image_data:
            return jsonify({"ok": False, "error": "No image"}), 400

        if "," in image_data:
            image_data = image_data.split(",")[1]

        try:
            base64.b64decode(image_data)
        except Exception:
            return jsonify({"ok": False, "error": "Invalid image data"}), 400

        prompt = """
You are DriveSense AI.

You are an expert automotive diagnostic assistant.

Analyze this vehicle image carefully.

Describe only what is visible. Do not guess if the image is unclear.

Check for:
- dashboard warning lights
- engine damage
- leaks
- worn components
- tyre condition
- brake wear
- rust
- smoke
- loose parts
- visible mechanical issues

Give a clear professional explanation.
"""

        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": "llava",
                "prompt": prompt,
                "images": [image_data],
                "stream": False
            },
            timeout=300
        )

        result = response.json()
        answer = result.get("response", "Unable to analyze image.").strip()

        return jsonify({
            "ok": True,
            "answer": answer,
            "result": answer
        })

    except Exception as e:
        print("IMAGE ANALYZE ERROR:", e)
        return jsonify({"ok": False, "error": str(e)}), 500