import random as random_module
from datetime import datetime as datetime_cls, timedelta as timedelta_cls

import numpy as np
import requests


class PredictorService:
    def __init__(
        self,
        *,
        combined_ok,
        combined_predictor,
        base_model,
        db_ok,
        db,
        broadcast_alert,
        weather_ok,
        fetch_live_weather,
        fetch_weather_forecast,
        normalize_city,
        city_api_map,
        owm_api_key,
        base_values,
        alert_log,
        alert_cooldowns,
        datetime_provider=datetime_cls,
        timedelta_provider=timedelta_cls,
        random_provider=random_module,
    ):
        self.combined_ok = combined_ok
        self.combined_predictor = combined_predictor
        self.base_model = base_model
        self.db_ok = db_ok
        self.db = db
        self.broadcast_alert = broadcast_alert
        self.weather_ok = weather_ok
        self.fetch_live_weather = fetch_live_weather
        self.fetch_weather_forecast = fetch_weather_forecast
        self.normalize_city = normalize_city
        self.city_api_map = city_api_map
        self.owm_api_key = owm_api_key
        self.base_values = base_values
        self.alert_log = alert_log
        self.alert_cooldowns = alert_cooldowns
        self.datetime = datetime_provider
        self.timedelta = timedelta_provider
        self.random = random_provider

    def _build_reasons(self, rainfall, water_level, flow_rate, probability, temperature, humidity):
        reasons = []

        if rainfall >= 120:
            reasons.append("Extreme rainfall detected")
        elif rainfall >= 70:
            reasons.append("Heavy rainfall detected")
        elif rainfall >= 35:
            reasons.append("Moderate rainfall detected")

        if water_level >= 5.0:
            reasons.append("Water level is critically high")
        elif water_level >= 3.5:
            reasons.append("Water level is above normal")
        elif water_level >= 2.0:
            reasons.append("Water level is rising")

        if flow_rate >= 220:
            reasons.append("River flow rate is very high")
        elif flow_rate >= 160:
            reasons.append("River flow rate is elevated")

        if humidity is not None and humidity >= 85:
            reasons.append("High humidity suggests saturated atmospheric conditions")

        if temperature is not None and temperature <= 24:
            reasons.append("Cooler conditions may support prolonged rainfall persistence")

        if probability >= 80:
            reasons.append("Overall flood probability is critically high")
        elif probability >= 60:
            reasons.append("Overall flood probability is high")

        if not reasons:
            reasons.append("Current indicators remain within lower-risk range")

        return reasons

    def _calculate_confidence(self, rainfall, water_level, flow_rate, used_model):
        score = 0.55

        if used_model == "Combined ML+Hydro":
            score += 0.20
        elif used_model == "Base ML":
            score += 0.12
        else:
            score += 0.05

        if rainfall > 0:
            score += 0.05
        if water_level > 0:
            score += 0.05
        if flow_rate > 0:
            score += 0.05

        return round(min(score, 0.95), 2)

    def predict_flood_risk(
        self,
        rainfall,
        water_level,
        flow_rate=150,
        location="Unknown",
        live=False,
        temperature=28,
        humidity=80,
    ):
        try:
            if self.combined_ok and self.combined_predictor is not None:
                res = self.combined_predictor.predict(
                    location=location,
                    rainfall=rainfall,
                    water_level=water_level,
                    temperature=temperature,
                    humidity=humidity,
                )
                ml = res.get("ml_prediction", {})
                out = {
                    "risk": res.get("combined_risk_level", "Unknown"),
                    "probability": round(ml.get("probability", 0.5) * 100, 2),
                    "model": "Combined ML+Hydro",
                    "hydro": res.get("hydro_prediction", {}),
                }
            elif self.base_model is not None:
                feat = np.array([[rainfall, water_level, flow_rate]])
                pred = self.base_model.predict(feat)[0]
                proba = self.base_model.predict_proba(feat)[0]
                out = {
                    "risk": "High" if pred == 1 else "Low",
                    "probability": round(float(proba[1]) * 100, 2),
                    "model": "Base ML",
                }
            else:
                score = rainfall * 0.4 + water_level * 30 + flow_rate * 0.2

                if score > 180:
                    risk, prob = "Very High", round(min(98, score / 2), 2)
                elif score > 150:
                    risk, prob = "High", round(min(92, score / 2.2), 2)
                elif score > 100:
                    risk, prob = "Moderate", round(min(70, score / 2.8), 2)
                else:
                    risk, prob = "Low", round(min(40, score / 3.5), 2)

                out = {
                    "risk": risk,
                    "probability": prob,
                    "model": "Rule-based",
                }

            out["confidence"] = self._calculate_confidence(
                rainfall=rainfall,
                water_level=water_level,
                flow_rate=flow_rate,
                used_model=out["model"],
            )
            out["reasons"] = self._build_reasons(
                rainfall=rainfall,
                water_level=water_level,
                flow_rate=flow_rate,
                probability=out["probability"],
                temperature=temperature,
                humidity=humidity,
            )

            self._log_prediction(location, rainfall, out)

            if live and out["risk"] in ("High", "Very High"):
                self._auto_alert(location, out["risk"], out["probability"], rainfall, water_level)

            return out

        except Exception as e:
            print(f"[predict] {e}")
            return {
                "risk": "Unknown",
                "probability": 0,
                "confidence": 0.0,
                "reasons": ["Prediction failed due to an internal error"],
                "model": "Error",
            }

    def _log_prediction(self, location, rainfall, out):
        if not self.db_ok or self.db is None:
            return
        try:
            self.db.log_prediction(
                location=location,
                rainfall_mm=rainfall,
                risk_level=out["risk"],
                probability=out["probability"] / 100,
                prediction_type=out["model"],
            )
        except Exception:
            pass

    def _auto_alert(self, location, risk, prob, rainfall, water_level):
        now = self.datetime.now()
        last = self.alert_cooldowns.get(location)
        if last and (now - last).seconds < 1800:
            return

        self.alert_cooldowns[location] = now
        self.alert_log.append(
            {
                "timestamp": now,
                "location": location,
                "risk_level": risk,
                "probability": round(prob, 1),
                "rainfall": rainfall,
                "water_level": water_level,
            }
        )

        if self.db_ok and self.db is not None:
            try:
                self.db.log_alert(
                    location=location,
                    risk_level=risk,
                    alert_method="Auto-Broadcast",
                    recipient="all_users",
                    status="Sent",
                    message=f"Auto {risk}",
                )
            except Exception:
                pass

        self.broadcast_alert(location, risk, prob, rainfall, water_level)

    def get_live_weather_data(self, location):
        if not self.weather_ok or self.fetch_live_weather is None or self.normalize_city is None:
            return None
        try:
            city = self.city_api_map.get(location, self.normalize_city(location))
            return self.fetch_live_weather(city)
        except Exception:
            return None

    def get_realtime_rainfall(self, lat=13.0827, lon=80.2707):
        if not self.owm_api_key:
            return None
        try:
            url = (
                "https://api.openweathermap.org/data/2.5/weather"
                f"?lat={lat}&lon={lon}&appid={self.owm_api_key}&units=metric"
            )
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                return round(resp.json().get("rain", {}).get("1h", 0), 2)
        except Exception:
            pass
        return None

    def predict_risk_forecast(
        self,
        location,
        rainfall,
        water_level,
        flow_rate=150,
        temperature=28,
        humidity=80,
    ):
        timeline = [
            {"label": "now", "hours": 0, "rainfall_scale": 1.00, "water_level_delta": 0.00, "flow_scale": 1.00},
            {"label": "6h", "hours": 6, "rainfall_scale": 1.08, "water_level_delta": 0.20, "flow_scale": 1.05},
            {"label": "24h", "hours": 24, "rainfall_scale": 1.18, "water_level_delta": 0.45, "flow_scale": 1.10},
            {"label": "72h", "hours": 72, "rainfall_scale": 1.28, "water_level_delta": 0.65, "flow_scale": 1.16},
        ]

        forecast_entries = []
        if self.weather_ok and self.fetch_weather_forecast and self.normalize_city:
            try:
                city = self.city_api_map.get(location, self.normalize_city(location))
                forecast_entries = self.fetch_weather_forecast(city, days=3) or []
            except Exception:
                forecast_entries = []

        results = []
        for idx, slot in enumerate(timeline):
            forecast_item = forecast_entries[idx] if idx < len(forecast_entries) else {}
            forecast_rain = forecast_item.get("rainfall", 0) or 0
            forecast_temp = forecast_item.get("temperature", temperature)
            forecast_humidity = forecast_item.get("humidity", humidity)

            projected_rainfall = max(0, round((rainfall * slot["rainfall_scale"]) + forecast_rain, 2))
            projected_water = max(0, round(water_level + slot["water_level_delta"] + (forecast_rain / 120.0), 2))
            projected_flow = max(0, round(flow_rate * slot["flow_scale"] + (forecast_rain * 0.8), 2))

            pred = self.predict_flood_risk(
                projected_rainfall,
                projected_water,
                projected_flow,
                location=location,
                live=False,
                temperature=forecast_temp,
                humidity=forecast_humidity,
            )

            results.append(
                {
                    "label": slot["label"],
                    "hours_ahead": slot["hours"],
                    "rainfall": projected_rainfall,
                    "water_level": projected_water,
                    "flow_rate": projected_flow,
                    "temperature": forecast_temp,
                    "humidity": forecast_humidity,
                    "risk": pred["risk"],
                    "probability": pred["probability"],
                    "confidence": pred.get("confidence", 0.0),
                    "reasons": pred.get("reasons", []),
                }
            )

        return results

    def get_model_status(self):
        combined_available = self.combined_ok and self.combined_predictor is not None
        artifacts_compatible = True
        compatibility_note = None

        if self.combined_predictor is not None:
            artifacts_compatible = getattr(self.combined_predictor, "artifacts_compatible", True)
            compatibility_note = getattr(self.combined_predictor, "compatibility_note", None)

        if combined_available and artifacts_compatible:
            active_mode = "combined_ml_hydro"
        elif combined_available and not artifacts_compatible:
            active_mode = "combined_rule_based_fallback"
        elif self.base_model is not None:
            active_mode = "base_ml"
        else:
            active_mode = "rule_based_only"

        return {
            "combined_available": combined_available,
            "combined_artifacts_compatible": artifacts_compatible,
            "base_model_available": self.base_model is not None,
            "active_mode": active_mode,
            "compatibility_note": compatibility_note,
        }

    def gen_history(self, location, hours=24):
        base = self.base_values.get(location, {"rainfall": 40, "water": 7.0})
        rows = []

        for i in range(hours):
            ts = self.datetime.now() - self.timedelta(hours=hours - i)
            rf = max(0, base["rainfall"] + self.random.uniform(-15, 25))
            wl = max(0, base["water"] + self.random.uniform(-1, 2))
            flow = max(0, 150 + self.random.uniform(-30, 80))
            pred = self.predict_flood_risk(rf, wl, flow, location)

            rows.append(
                {
                    "timestamp": ts.strftime("%Y-%m-%d %H:%M"),
                    "location": location,
                    "rainfall_mm": round(rf, 1),
                    "water_level_m": round(wl, 2),
                    "flow_rate": round(flow, 1),
                    "risk_level": pred["risk"],
                    "probability": pred["probability"],
                    "confidence": pred.get("confidence", 0.0),
                    "reasons": pred.get("reasons", []),
                }
            )

        return rows
