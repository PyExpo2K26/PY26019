from functools import wraps
from math import atan2, cos, radians, sin, sqrt

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for


predictions_bp = Blueprint("predictions", __name__)
_ctx = {}


def configure_predictions(**kwargs):
    _ctx.update(kwargs)


def _cfg(name):
    value = _ctx.get(name)
    if value is None:
        raise RuntimeError(f"Predictions routes not configured: missing '{name}'")
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


def _distance_km(lat1, lon1, lat2, lon2):
    radius = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return radius * 2 * atan2(sqrt(a), sqrt(1 - a))


def _nearest_known_location(lat, lon, india_locations):
    nearest = None
    nearest_distance = None
    for state, districts in india_locations.items():
        for district, coords in districts.items():
            distance = _distance_km(lat, lon, coords["lat"], coords["lon"])
            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest = {
                    "district": district,
                    "state": state,
                    "label": f"{district}, {state}",
                    "distance_km": round(distance, 2),
                }
    return nearest


def _resolve_location(location, india_locations):
    parts = [part.strip() for part in (location or "").split(",")]
    district = parts[0] if len(parts) >= 1 and parts[0] else None
    state = parts[1] if len(parts) >= 2 and parts[1] else None
    lat = lon = None
    if district and state:
        coords = india_locations.get(state, {}).get(district)
        if coords:
            lat = coords["lat"]
            lon = coords["lon"]
    return district, state, lat, lon


def _build_realtime_payload(lat, lon, location):
    get_realtime_rainfall = _cfg("get_realtime_rainfall")
    predict_flood_risk = _cfg("predict_flood_risk")
    sensor_history = _cfg("sensor_history")
    datetime = _cfg("datetime")
    random = _cfg("random")
    try:
        rf = get_realtime_rainfall(lat, lon) or round(random.uniform(0, 100), 2)
        wl = round(random.uniform(1.5, 4.5), 2)
        flow = round(random.uniform(80, 250), 2)
        pred = predict_flood_risk(rf, wl, flow, location, live=False)
    except Exception as e:
        print(f"[realtime payload] falling back to simulated data: {e}")
        rf = round(random.uniform(5, 80), 2)
        wl = round(random.uniform(1.5, 4.0), 2)
        flow = round(random.uniform(90, 220), 2)
        pred = {
            "risk": "Moderate" if rf > 45 or wl > 3.0 else "Low",
            "probability": round(min(85, rf * 0.7 + wl * 8), 2),
            "confidence": 0.65,
            "reasons": ["Using simulated fallback data because live feed is temporarily unavailable"],
            "model": "Fallback Simulation",
        }

    try:
        sensor_history.append(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "location": location,
                "rainfall": rf,
                "water_level": wl,
                "flow": flow,
                "risk": pred["risk"],
            }
        )
    except Exception:
        pass

    return {
        "success": True,
        "rainfall": rf,
        "water_level": wl,
        "flow_rate": flow,
        "prediction": pred,
        "location": location,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


@predictions_bp.route("/")
def home():
    return render_template("index.html")


@predictions_bp.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@predictions_bp.route("/api/realtime-data")
@login_required
def get_realtime_data():
    lat = float(request.args.get("lat", 13.0827))
    lon = float(request.args.get("lon", 80.2707))
    location = request.args.get("location", "Chennai, Tamil Nadu")
    return jsonify(_build_realtime_payload(lat, lon, location))


@predictions_bp.route("/api/public-realtime-data")
def get_public_realtime_data():
    lat = float(request.args.get("lat", 13.0827))
    lon = float(request.args.get("lon", 80.2707))
    location = request.args.get("location", "Chennai, Tamil Nadu")
    return jsonify(_build_realtime_payload(lat, lon, location))


@predictions_bp.route("/api/location-risk")
@login_required
def location_risk():
    predict_flood_risk = _cfg("predict_flood_risk")
    datetime = _cfg("datetime")
    random = _cfg("random")
    india_locations = _cfg("INDIA_LOCATIONS")
    fetch_reverse_geocode = _cfg("fetch_reverse_geocode")
    lat = float(request.args.get("lat", 13.0827))
    lon = float(request.args.get("lon", 80.2707))
    rf = round(random.uniform(0, 100), 2)
    wl = round(random.uniform(1.5, 4.5), 2)
    flow = round(random.uniform(80, 250), 2)
    nearest = _nearest_known_location(lat, lon, india_locations)
    reverse_geocode = fetch_reverse_geocode(lat, lon) if fetch_reverse_geocode else None
    return jsonify(
        {
            "latitude": lat,
            "longitude": lon,
            "prediction": predict_flood_risk(rf, wl, flow),
            "display_location": reverse_geocode,
            "resolved_location": nearest,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    )


@predictions_bp.route("/api/states")
def get_states():
    india_locations = _cfg("INDIA_LOCATIONS")
    return jsonify({"states": sorted(india_locations.keys())})


@predictions_bp.route("/api/districts/<state>")
def get_districts(state):
    india_locations = _cfg("INDIA_LOCATIONS")
    if state not in india_locations:
        return jsonify({"districts": []}), 404
    return jsonify({"districts": sorted(india_locations[state].keys())})


@predictions_bp.route("/api/district-prediction", methods=["POST"])
@login_required
def district_prediction():
    india_locations = _cfg("INDIA_LOCATIONS")
    get_realtime_rainfall = _cfg("get_realtime_rainfall")
    predict_flood_risk = _cfg("predict_flood_risk")
    datetime = _cfg("datetime")
    random = _cfg("random")
    try:
        data = request.get_json() or {}
        state = data.get("state")
        district = data.get("district")
        if state not in india_locations or district not in india_locations[state]:
            return jsonify({"success": False, "error": "Invalid state or district"}), 400
        coords = india_locations[state][district]
        lat, lon = coords["lat"], coords["lon"]
        location = f"{district}, {state}"
        rf = get_realtime_rainfall(lat, lon) or round(random.uniform(0, 100), 2)
        wl = round(random.uniform(1.5, 4.5), 2)
        flow = round(random.uniform(80, 250), 2)
        temperature = round(24 + random.uniform(-3, 9), 1)
        humidity = round(68 + random.uniform(0, 28), 1)
        pred = predict_flood_risk(
            rf, wl, flow, location, live=True, temperature=temperature, humidity=humidity
        )
        return jsonify(
            {
                "success": True,
                "state": state,
                "district": district,
                "latitude": lat,
                "longitude": lon,
                "rainfall": rf,
                "water_level": wl,
                "flow_rate": flow,
                "temperature": temperature,
                "humidity": humidity,
                "prediction": pred,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@predictions_bp.route("/predict", methods=["GET", "POST"])
def predict():
    predict_flood_risk = _cfg("predict_flood_risk")
    if request.method == "GET":
        return render_template("index.html")
    try:
        if request.is_json:
            data = request.get_json() or {}
            rf = float(data.get("rainfall", 0))
            wl = float(data.get("water_level", 0))
            flow = float(data.get("flow_rate", 0))
            temperature = float(data.get("temperature", 28))
            humidity = float(data.get("humidity", 80))
            location = data.get("location", "Unknown")
        else:
            rf = float(request.form.get("rainfall", 0))
            wl = float(request.form.get("water_level", 0))
            flow = float(request.form.get("flow_rate", 0))
            temperature = float(request.form.get("temperature", 28))
            humidity = float(request.form.get("humidity", 80))
            location = request.form.get("location", "Unknown")

        pred = predict_flood_risk(
            rf, wl, flow, location=location, temperature=temperature, humidity=humidity
        )

        if request.is_json:
            return jsonify(
                {
                    "success": True,
                    "risk_level": pred["risk"],
                    "probability": pred["probability"],
                    "confidence": pred.get("confidence", 0.0),
                    "reasons": pred.get("reasons", []),
                    "model": pred.get("model", ""),
                    "rainfall": rf,
                    "water_level": wl,
                    "flow_rate": flow,
                    "temperature": temperature,
                    "humidity": humidity,
                    "location": location,
                }
            )

        return render_template(
            "result.html",
            prediction=f"Flood Risk: {pred['risk']}",
            risk_level=pred["risk"],
            probability=pred["probability"],
            confidence=pred.get("confidence", 0.0),
            reasons=pred.get("reasons", []),
            rainfall=rf,
            water_level=wl,
            river_flow=flow,
            temperature=temperature,
            humidity=humidity,
            location=location,
        )
    except Exception as e:
        print(f"[predict error] {e}")
        if request.is_json:
            return jsonify({"success": False, "error": str(e)}), 500
        return render_template(
            "result.html",
            prediction="Error",
            risk_level="Low",
            probability=0,
            confidence=0.0,
            reasons=["Prediction failed"],
            rainfall=0,
            water_level=0,
            river_flow=0,
            temperature=0,
            humidity=0,
            location="Unknown",
        )


@predictions_bp.route("/api/weather")
def api_weather():
    get_live_weather_data = _cfg("get_live_weather_data")
    location = request.args.get("location", "Chennai, Tamil Nadu")
    weather = get_live_weather_data(location)
    if weather:
        return jsonify({"success": True, **weather})
    return jsonify({"success": False, "error": "Weather unavailable"}), 503


@predictions_bp.route("/api/weather-forecast")
def api_weather_forecast():
    weather_ok = _cfg("WEATHER_OK")
    city_api_map = _cfg("CITY_API_MAP")
    normalize_city = _cfg("normalize_city")
    fetch_weather_forecast = _cfg("fetch_weather_forecast")
    if not weather_ok:
        return jsonify({"success": False}), 503
    location = request.args.get("location", "Chennai, Tamil Nadu")
    try:
        city = city_api_map.get(location, normalize_city(location))
        fc = fetch_weather_forecast(city, days=3)
        return jsonify({"success": True, "forecast": fc or []})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@predictions_bp.route("/api/risk-forecast")
@login_required
def api_risk_forecast():
    predict_risk_forecast = _cfg("predict_risk_forecast")
    get_live_weather_data = _cfg("get_live_weather_data")
    random = _cfg("random")
    location = request.args.get("location", "Chennai, Tamil Nadu")
    weather = get_live_weather_data(location) or {}
    rainfall = float(request.args.get("rainfall", weather.get("rainfall", 20) or 20))
    water_level = float(request.args.get("water_level", 2.5))
    flow_rate = float(request.args.get("flow_rate", random.uniform(100, 180)))
    temperature = float(request.args.get("temperature", weather.get("temperature", 28) or 28))
    humidity = float(request.args.get("humidity", weather.get("humidity", 80) or 80))
    forecast = predict_risk_forecast(
        location=location,
        rainfall=rainfall,
        water_level=water_level,
        flow_rate=flow_rate,
        temperature=temperature,
        humidity=humidity,
    )
    return jsonify({"success": True, "location": location, "forecast": forecast})


@predictions_bp.route("/api/nearest-shelters")
@login_required
def api_nearest_shelters():
    shelter_service = _cfg("shelter_service")
    india_locations = _cfg("INDIA_LOCATIONS")
    location = request.args.get("location", "Chennai, Tamil Nadu")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    district = state = None
    if lat is None or lon is None:
        district, state, lat, lon = _resolve_location(location, india_locations)
    else:
        district, state, _, _ = _resolve_location(location, india_locations)
        lat = float(lat)
        lon = float(lon)
    if lat is None or lon is None:
        return jsonify({"success": False, "error": "Unknown location"}), 400
    shelters = shelter_service.nearest_shelters(
        lat,
        lon,
        limit=int(request.args.get("limit", 5)),
        preferred_state=state,
        preferred_district=district,
    )
    return jsonify({"success": True, "location": location, "shelters": shelters})


@predictions_bp.route("/api/safe-route")
@login_required
def api_safe_route():
    shelter_service = _cfg("shelter_service")
    india_locations = _cfg("INDIA_LOCATIONS")
    predict_flood_risk = _cfg("predict_flood_risk")
    location = request.args.get("location", "Chennai, Tamil Nadu")
    lat = request.args.get("lat")
    lon = request.args.get("lon")
    risk_level = request.args.get("risk_level")
    district = state = None
    if lat is None or lon is None:
        district, state, lat, lon = _resolve_location(location, india_locations)
    else:
        district, state, _, _ = _resolve_location(location, india_locations)
        lat = float(lat)
        lon = float(lon)
    if lat is None or lon is None:
        return jsonify({"success": False, "error": "Unknown location"}), 400
    if not risk_level:
        rainfall = float(request.args.get("rainfall", 25))
        water_level = float(request.args.get("water_level", 2.8))
        flow_rate = float(request.args.get("flow_rate", 140))
        risk_level = predict_flood_risk(rainfall, water_level, flow_rate, location=location, live=False)["risk"]
    plan = shelter_service.build_safe_route_plan(
        lat,
        lon,
        risk_level,
        limit=int(request.args.get("limit", 5)),
        preferred_state=state,
        preferred_district=district,
    )
    return jsonify({"success": True, "location": location, "risk_level": risk_level, **plan})


@predictions_bp.route("/api/district-analytics")
@login_required
def api_district_analytics():
    india_locations = _cfg("INDIA_LOCATIONS")
    predict_flood_risk = _cfg("predict_flood_risk")
    predict_risk_forecast = _cfg("predict_risk_forecast")
    shelter_service = _cfg("shelter_service")
    random = _cfg("random")
    datetime = _cfg("datetime")
    get_model_status = _cfg("get_model_status")
    state = request.args.get("state", "Tamil Nadu")
    district = request.args.get("district", "Chennai")
    if state not in india_locations or district not in india_locations[state]:
        return jsonify({"success": False, "error": "Invalid state or district"}), 400
    coords = india_locations[state][district]
    location = f"{district}, {state}"
    lat = coords["lat"]
    lon = coords["lon"]
    rainfall = round(float(request.args.get("rainfall", random.uniform(20, 95))), 2)
    water_level = round(float(request.args.get("water_level", random.uniform(1.8, 4.8))), 2)
    flow_rate = round(float(request.args.get("flow_rate", random.uniform(90, 240))), 2)
    temperature = round(float(request.args.get("temperature", 26 + random.uniform(-2, 8))), 1)
    humidity = round(float(request.args.get("humidity", 70 + random.uniform(5, 22))), 1)
    prediction = predict_flood_risk(
        rainfall, water_level, flow_rate, location=location, live=False, temperature=temperature, humidity=humidity
    )
    forecast = predict_risk_forecast(
        location=location,
        rainfall=rainfall,
        water_level=water_level,
        flow_rate=flow_rate,
        temperature=temperature,
        humidity=humidity,
    )
    shelters = shelter_service.nearest_shelters(
        lat, lon, limit=3, preferred_state=state, preferred_district=district
    )
    safe_route = shelter_service.build_safe_route_plan(
        lat, lon, prediction["risk"], limit=3, preferred_state=state, preferred_district=district
    )
    if prediction["risk"] in ("High", "Very High"):
        recommended_action = "Prepare evacuation and use shelter guidance immediately."
    elif prediction["risk"] in ("Moderate", "Medium"):
        recommended_action = "Monitor local conditions and keep a safe route ready."
    else:
        recommended_action = "Continue monitoring with no immediate evacuation needed."
    return jsonify(
        {
            "success": True,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "state": state,
            "district": district,
            "location": location,
            "latitude": lat,
            "longitude": lon,
            "inputs": {
                "rainfall": rainfall,
                "water_level": water_level,
                "flow_rate": flow_rate,
                "temperature": temperature,
                "humidity": humidity,
            },
            "prediction": prediction,
            "forecast": forecast,
            "shelters": shelters,
            "safe_route": safe_route,
            "recommended_action": recommended_action,
            "model_status": get_model_status(),
        }
    )
