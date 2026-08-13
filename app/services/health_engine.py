def _safe_number(value, fallback=0):
    try:
        if isinstance(value, str):
            value = value.replace("°C", "")
            value = value.replace("degC", "")
            value = value.replace("%", "")
            value = value.replace("rpm", "")
            value = value.replace("RPM", "")
            value = value.strip()

        return float(value)

    except Exception:
        return fallback


def calculate_health_score(live_data, dtc_codes):
    score = 100

    if not dtc_codes:
        dtc_codes = []

    if isinstance(dtc_codes, str):
        dtc_codes = [dtc_codes]

    if isinstance(dtc_codes, int):
        dtc_codes = []

    fault_count = len(dtc_codes)

    score -= fault_count * 15

    coolant = _safe_number(
        live_data.get("coolant_temp", 91),
        91
    )

    engine_load = _safe_number(
        live_data.get("engine_load", 18),
        18
    )

    rpm = _safe_number(
        live_data.get("rpm", 820),
        820
    )

    if coolant > 110:
        score -= 25

    if engine_load > 75:
        score -= 10

    if rpm > 4500:
        score -= 8

    if score < 0:
        score = 0

    if score > 100:
        score = 100

    return int(score)