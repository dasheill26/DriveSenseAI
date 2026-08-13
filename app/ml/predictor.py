import os
import pickle


BASE_DIR = os.path.dirname(__file__)
MODEL_PATH = os.path.join(BASE_DIR, "drivesense_ml_model.pkl")


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


def _load_model():
    if not os.path.exists(MODEL_PATH):
        return None

    try:
        with open(MODEL_PATH, "rb") as f:
            return pickle.load(f)

    except Exception:
        return None


def _clamp(value, minimum=0, maximum=100):
    return max(minimum, min(maximum, int(round(value))))


def _status_from_risk(risk):
    risk = _safe_number(risk, 0)

    if risk >= 75:
        return "High Risk"
    elif risk >= 60:
        return "Due Soon"
    elif risk >= 40:
        return "Monitor"
    else:
        return "Healthy"


def _fallback_prediction(
    fault_count,
    coolant_temp,
    engine_load,
    rpm,
    severity_score
):
    score = 100

    score -= fault_count * 14
    score -= severity_score * 4

    if coolant_temp > 110:
        score -= 18
    elif coolant_temp > 100:
        score -= 8

    if engine_load > 65:
        score -= 10
    elif engine_load > 45:
        score -= 5

    if rpm > 1300:
        score -= 5

    score = _clamp(score)

    if score >= 75:
        urgency = "low"
    elif score >= 50:
        urgency = "medium"
    elif score >= 30:
        urgency = "high"
    else:
        urgency = "critical"

    return {
        "ml_health_score": score,
        "repair_urgency": urgency,
        "safe_to_drive": urgency in ["low", "medium"],
        "confidence": 0.72,
        "model_used": "fallback_interpretable_model"
    }


def predict_vehicle_risk(
    fault_count=0,
    coolant_temp=90,
    engine_load=20,
    rpm=850,
    severity_score=3
):
    fault_count = _safe_number(fault_count, 0)
    coolant_temp = _safe_number(coolant_temp, 90)
    engine_load = _safe_number(engine_load, 20)
    rpm = _safe_number(rpm, 850)
    severity_score = _safe_number(severity_score, 3)

    model_bundle = _load_model()

    if not model_bundle:
        return _fallback_prediction(
            fault_count,
            coolant_temp,
            engine_load,
            rpm,
            severity_score
        )

    try:
        features = [[
            fault_count,
            coolant_temp,
            engine_load,
            rpm,
            severity_score
        ]]

        health = model_bundle["health_model"].predict(features)[0]
        urgency = model_bundle["urgency_model"].predict(features)[0]

        health = _clamp(health)

        return {
            "ml_health_score": health,
            "repair_urgency": urgency,
            "safe_to_drive": urgency in ["low", "medium"],
            "confidence": model_bundle.get("urgency_accuracy", 0.8),
            "health_mae": model_bundle.get("health_mae", None),
            "model_used": "decision_tree_random_forest"
        }

    except Exception:
        return _fallback_prediction(
            fault_count,
            coolant_temp,
            engine_load,
            rpm,
            severity_score
        )


def predict_component_maintenance(
    current_mileage=65081,
    fault_count=0,
    coolant_temp=90,
    engine_load=20,
    rpm=850,
    severity_score=3,
    service_records=None
):
    current_mileage = int(_safe_number(current_mileage, 65081))
    fault_count = _safe_number(fault_count, 0)
    coolant_temp = _safe_number(coolant_temp, 90)
    engine_load = _safe_number(engine_load, 20)
    rpm = _safe_number(rpm, 850)
    severity_score = _safe_number(severity_score, 3)

    service_records = service_records or []

    last_service_mileage = {}

    for record in service_records:
        service_type = record.get("service_type", "")
        mileage = int(_safe_number(record.get("mileage", 0), 0))

        if service_type and mileage > last_service_mileage.get(service_type, 0):
            last_service_mileage[service_type] = mileage

    oil_miles = current_mileage - last_service_mileage.get(
        "Oil Change",
        current_mileage - 8500
    )

    full_service_miles = current_mileage - last_service_mileage.get(
        "Full Service",
        current_mileage - 10000
    )

    brake_miles = current_mileage - last_service_mileage.get(
        "Brake Pads",
        current_mileage - 18000
    )

    spark_miles = current_mileage - last_service_mileage.get(
        "Spark Plugs",
        current_mileage - 28000
    )

    coolant_miles = current_mileage - last_service_mileage.get(
        "Coolant",
        current_mileage - 22000
    )

    air_filter_miles = current_mileage - last_service_mileage.get(
        "Air Filter",
        current_mileage - 12000
    )

    cabin_filter_miles = current_mileage - last_service_mileage.get(
        "Cabin Filter",
        current_mileage - 9000
    )

    brake_fluid_miles = current_mileage - last_service_mileage.get(
        "Brake Fluid",
        current_mileage - 16000
    )

    tyre_miles = current_mileage - last_service_mileage.get(
        "Tyres",
        current_mileage - 16000
    )

    oil_risk = (oil_miles / 10000) * 100
    full_service_risk = (full_service_miles / 12000) * 100
    brake_risk = (brake_miles / 30000) * 100
    spark_risk = (spark_miles / 40000) * 100
    coolant_risk = (coolant_miles / 50000) * 100
    air_filter_risk = (air_filter_miles / 20000) * 100
    cabin_filter_risk = (cabin_filter_miles / 12000) * 100
    brake_fluid_risk = (brake_fluid_miles / 20000) * 100
    tyre_risk = (tyre_miles / 25000) * 100

    battery_risk = 45 + (fault_count * 6) + (severity_score * 2)

    if coolant_temp > 105:
        coolant_risk += 22
        oil_risk += 8
    elif coolant_temp > 100:
        coolant_risk += 14

    if engine_load > 65:
        oil_risk += 12
        brake_risk += 8
        air_filter_risk += 6
    elif engine_load > 45:
        oil_risk += 8
        brake_risk += 5

    if rpm > 1400:
        spark_risk += 10
        battery_risk += 7
    elif rpm > 1200:
        spark_risk += 6
        battery_risk += 5

    if fault_count > 0:
        oil_risk += fault_count * 3
        spark_risk += fault_count * 4
        battery_risk += fault_count * 5
        full_service_risk += fault_count * 4

    if severity_score >= 6:
        battery_risk += 8
        full_service_risk += 8
        spark_risk += 6

    items = [
        {
            "component": "Engine Oil",
            "risk": _clamp(oil_risk),
            "remaining_miles": max(0, int(10000 - oil_miles)),
            "recommendation": "Oil condition may be degrading based on mileage, engine load and service history."
        },
        {
            "component": "Full Service",
            "risk": _clamp(full_service_risk),
            "remaining_miles": max(0, int(12000 - full_service_miles)),
            "recommendation": "Full service risk is based on mileage since the latest full service record."
        },
        {
            "component": "Brake Pads",
            "risk": _clamp(brake_risk),
            "remaining_miles": max(0, int(30000 - brake_miles)),
            "recommendation": "Brake wear prediction is based on mileage since last brake service and driving load."
        },
        {
            "component": "Spark Plugs",
            "risk": _clamp(spark_risk),
            "remaining_miles": max(0, int(40000 - spark_miles)),
            "recommendation": "Spark plug risk increases with mileage, RPM pattern and active engine faults."
        },
        {
            "component": "Battery",
            "risk": _clamp(battery_risk),
            "remaining_miles": max(0, int(12000 - (current_mileage % 12000))),
            "recommendation": "Battery risk is estimated from fault count, severity and live electrical load symptoms."
        },
        {
            "component": "Coolant System",
            "risk": _clamp(coolant_risk),
            "remaining_miles": max(0, int(50000 - coolant_miles)),
            "recommendation": "Coolant risk increases when coolant temperature rises or service interval is ageing."
        },
        {
            "component": "Air Filter",
            "risk": _clamp(air_filter_risk),
            "remaining_miles": max(0, int(20000 - air_filter_miles)),
            "recommendation": "Air filter risk is estimated from mileage interval and engine load behaviour."
        },
        {
            "component": "Cabin Filter",
            "risk": _clamp(cabin_filter_risk),
            "remaining_miles": max(0, int(12000 - cabin_filter_miles)),
            "recommendation": "Cabin filter risk is based mainly on mileage interval since last replacement."
        },
        {
            "component": "Brake Fluid",
            "risk": _clamp(brake_fluid_risk),
            "remaining_miles": max(0, int(20000 - brake_fluid_miles)),
            "recommendation": "Brake fluid risk is based on service interval and estimated age since last maintenance."
        },
        {
            "component": "Tyres",
            "risk": _clamp(tyre_risk),
            "remaining_miles": max(0, int(25000 - tyre_miles)),
            "recommendation": "Tyre risk is estimated from mileage interval and expected wear pattern."
        }
    ]

    for item in items:
        item["status"] = _status_from_risk(item["risk"])

    items.sort(key=lambda item: item["risk"], reverse=True)

    return items