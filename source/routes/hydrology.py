from functools import wraps

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for


hydrology_bp = Blueprint("hydrology", __name__)
_ctx = {}


def configure_hydrology(**kwargs):
    _ctx.update(kwargs)


def _cfg(name):
    value = _ctx.get(name)
    if value is None:
        raise RuntimeError(f"Hydrology routes not configured: missing '{name}'")
    return value


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_email" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"success": False, "error": "Authentication required"}), 401
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)

    return decorated_function


@hydrology_bp.route("/hydrology")
@login_required
def hydrology_page():
    return render_template("Hydrology.html")


@hydrology_bp.route("/api/hydrology")
@login_required
def api_hydrology():
    scs_compute = _cfg("scs_compute")
    combined_ok = _cfg("COMBINED_OK")
    combined_predictor = _cfg("combined_predictor")
    datetime = _cfg("datetime")

    location = request.args.get("location", "Chennai, Tamil Nadu")
    rf = float(request.args.get("rainfall", 50))
    wl = float(request.args.get("water_level", 3.0))
    cn = float(request.args.get("curve_number", 75))
    amc = request.args.get("amc", "II")

    ml_prob = 0.0
    ml_risk = "Unknown"
    combined = "Low"

    if combined_ok:
        try:
            res = combined_predictor.predict(location, rf, wl)
            ml_pred = res.get("ml_prediction", {})
            ml_prob = round(ml_pred.get("probability", 0) * 100, 1)
            ml_risk = ml_pred.get("risk_level", "Unknown")
            combined = res.get("combined_risk_level", "Low")
        except Exception as e:
            print(f"[hydrology] combined_predictor error: {e}")
    else:
        score = rf * 0.4 + wl * 30
        ml_prob = round(min(95, score / 2), 1)
        ml_risk = "High" if ml_prob >= 60 else "Moderate" if ml_prob >= 40 else "Low"
        combined = ml_risk

    scs = scs_compute(rf, cn, amc)
    scenarios = []
    for test_rf in [10, 25, 50, 75, 100, 125, 150, 175, 200, 250, 300]:
        s = scs_compute(test_rf, cn, amc)
        scenarios.append(
            {
                "rainfall_mm": test_rf,
                "runoff_mm": s["runoff_mm"],
                "flooded_area_pct": s["flooded_area_pct"],
                "max_depth_m": s["max_depth_m"],
            }
        )

    return jsonify(
        {
            "location": location,
            "rainfall": rf,
            "water_level": wl,
            "curve_number": cn,
            "amc": amc,
            "combined_risk": combined,
            "ml_probability": ml_prob,
            "ml_risk": ml_risk,
            "flooded_area_pct": scs["flooded_area_pct"],
            "max_depth_m": scs["max_depth_m"],
            "avg_depth_m": scs["avg_depth_m"],
            "runoff_mm": scs["runoff_mm"],
            "infiltration_mm": scs["infiltration_mm"],
            "runoff_coefficient": scs["runoff_coefficient"],
            "water_level_rise_m": scs["water_level_rise_m"],
            "severity_level": scs["severity_level"],
            "severity_label": scs["severity_label"],
            "scenarios": scenarios,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


@hydrology_bp.route("/api/hydrology/batch", methods=["POST"])
@login_required
def api_hydrology_batch():
    scs_compute = _cfg("scs_compute")
    try:
        data = request.get_json() or {}
        location = data.get("location", "Chennai, Tamil Nadu")
        cn = float(data.get("curve_number", 75))
        amc = data.get("amc", "II")
        rainfalls = data.get("rainfalls", [10, 25, 50, 75, 100, 125, 150, 175, 200, 250, 300])
        sev_map = {
            "No Flood": "None",
            "Minor Flood": "Low",
            "Moderate Flood": "Moderate",
            "Significant Flood": "Significant",
            "Extreme Flood": "Extreme",
        }
        results = []
        for rf in rainfalls:
            scs = scs_compute(rf, cn, amc)
            results.append(
                {
                    "rainfall_mm": rf,
                    "runoff_mm": scs["runoff_mm"],
                    "infiltration_mm": scs["infiltration_mm"],
                    "runoff_coeff": scs["runoff_coefficient"],
                    "water_level_rise": scs["water_level_rise_m"],
                    "flooded_area_pct": scs["flooded_area_pct"],
                    "max_depth_m": scs["max_depth_m"],
                    "severity": sev_map.get(scs["severity_label"], "None"),
                }
            )
        return jsonify({"success": True, "results": results, "location": location})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@hydrology_bp.route("/api/scenario-simulate", methods=["POST"])
@login_required
def api_scenario_simulate():
    scs_compute = _cfg("scs_compute")
    predict_flood_risk = _cfg("predict_flood_risk")
    predict_risk_forecast = _cfg("predict_risk_forecast")
    datetime = _cfg("datetime")
    shelter_service = _cfg("shelter_service")
    india_locations = _cfg("INDIA_LOCATIONS")
    try:
        data = request.get_json() or {}
        location = data.get("location", "Chennai, Tamil Nadu")
        rainfall_intensity = float(data.get("rainfall_intensity", 20))
        duration_hours = float(data.get("duration_hours", 6))
        initial_water_level = float(data.get("initial_water_level", 2.5))
        flow_rate = float(data.get("flow_rate", 140))
        temperature = float(data.get("temperature", 28))
        humidity = float(data.get("humidity", 80))
        curve_number = float(data.get("curve_number", 75))
        amc = data.get("amc", "II")
        terrain_sensitivity = float(data.get("terrain_sensitivity", 1.0))

        total_rainfall = round(rainfall_intensity * duration_hours, 2)
        hydro = scs_compute(total_rainfall, curve_number, amc)
        projected_water_level = round(initial_water_level + (hydro["water_level_rise_m"] * max(0.5, terrain_sensitivity)), 2)
        projected_flow_rate = round(flow_rate + (hydro["runoff_mm"] * max(0.4, terrain_sensitivity)), 2)
        prediction = predict_flood_risk(
            total_rainfall,
            projected_water_level,
            projected_flow_rate,
            location=location,
            live=False,
            temperature=temperature,
            humidity=humidity,
        )
        forecast = predict_risk_forecast(
            location=location,
            rainfall=total_rainfall,
            water_level=projected_water_level,
            flow_rate=projected_flow_rate,
            temperature=temperature,
            humidity=humidity,
        )

        lat = lon = None
        parts = [part.strip() for part in location.split(",")]
        if len(parts) >= 2:
            district, state = parts[0], parts[1]
            coords = india_locations.get(state, {}).get(district)
            if coords:
                lat = coords["lat"]
                lon = coords["lon"]

        safe_route = None
        if lat is not None and lon is not None:
            safe_route = shelter_service.build_safe_route_plan(lat, lon, prediction["risk"], limit=3)

        return jsonify(
            {
                "success": True,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "location": location,
                "inputs": {
                    "rainfall_intensity": rainfall_intensity,
                    "duration_hours": duration_hours,
                    "initial_water_level": initial_water_level,
                    "flow_rate": flow_rate,
                    "temperature": temperature,
                    "humidity": humidity,
                    "curve_number": curve_number,
                    "amc": amc,
                    "terrain_sensitivity": terrain_sensitivity,
                },
                "simulation": {
                    "total_rainfall_mm": total_rainfall,
                    "projected_water_level_m": projected_water_level,
                    "projected_flow_rate": projected_flow_rate,
                    "hydrology": hydro,
                },
                "prediction": prediction,
                "forecast": forecast,
                "safe_route": safe_route,
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@hydrology_bp.route("/api/chart-data")
@login_required
def api_chart_data():
    gen_history = _cfg("gen_history")
    location = request.args.get("location", "Chennai, Tamil Nadu")
    return jsonify({"success": True, "rows": gen_history(location, 24)})


@hydrology_bp.route("/api/flood-zones")
@login_required
def api_flood_zones():
    india_locations = _cfg("INDIA_LOCATIONS")
    zones = []
    for state, districts in india_locations.items():
        for district, coords in districts.items():
            zones.append({"state": state, "district": district, "lat": coords["lat"], "lon": coords["lon"]})
    return jsonify({"success": True, "zones": zones})


@hydrology_bp.route("/api/location-metrics")
@login_required
def api_location_metrics():
    get_live_weather_data = _cfg("get_live_weather_data")
    location = request.args.get("location", "Chennai, Tamil Nadu")
    return jsonify({"success": True, "location": location, "weather": get_live_weather_data(location) or {}})


@hydrology_bp.route("/api/statistics")
@login_required
def api_statistics():
    db_ok = _cfg("DB_OK")
    db = _cfg("db")
    if not db_ok or db is None:
        return jsonify({"success": True, "stats": {}})
    try:
        return jsonify({"success": True, "stats": db.get_prediction_stats(None)})
    except Exception:
        return jsonify({"success": True, "stats": {}})
