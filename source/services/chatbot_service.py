import re


class WeatherChatbotService:
    def __init__(
        self,
        *,
        get_live_weather_data,
        predict_flood_risk,
        predict_risk_forecast,
        shelter_service,
        india_locations,
        get_model_status,
    ):
        self.get_live_weather_data = get_live_weather_data
        self.predict_flood_risk = predict_flood_risk
        self.predict_risk_forecast = predict_risk_forecast
        self.shelter_service = shelter_service
        self.india_locations = india_locations
        self.get_model_status = get_model_status
        self._known_locations = self._build_known_locations()

    def _build_known_locations(self):
        known = []
        for state, districts in self.india_locations.items():
            for district, coords in districts.items():
                known.append(
                    {
                        "label": f"{district}, {state}",
                        "district": district,
                        "state": state,
                        "lat": coords["lat"],
                        "lon": coords["lon"],
                    }
                )
        known.sort(key=lambda item: len(item["label"]), reverse=True)
        return known

    def _extract_location(self, message, fallback_location=None):
        text = (message or "").strip().lower()

        for item in self._known_locations:
            full_label = item["label"].lower()
            district = item["district"].lower()
            if full_label in text or re.search(rf"\b{re.escape(district)}\b", text):
                return item

        if fallback_location:
            lower_fallback = fallback_location.strip().lower()
            for item in self._known_locations:
                if item["label"].lower() == lower_fallback:
                    return item
                if item["district"].lower() == lower_fallback:
                    return item

        return self._known_locations[0] if self._known_locations else None

    @staticmethod
    def _extract_number(message, pattern, default):
        match = re.search(pattern, message, re.IGNORECASE)
        if not match:
            return default
        try:
            return float(match.group(1))
        except Exception:
            return default

    def _weather_reply(self, location):
        weather = self.get_live_weather_data(location["label"])
        if not weather:
            return "Live weather is temporarily unavailable. You can still ask for flood risk or forecast guidance."

        return (
            f"Current weather in {location['label']}: {weather.get('temperature', '--')} deg C, "
            f"{weather.get('humidity', '--')}% humidity, rainfall {weather.get('rainfall', 0)} mm, "
            f"and {weather.get('description', 'normal conditions')}."
        )

    def _risk_reply(self, location):
        weather = self.get_live_weather_data(location["label"]) or {}
        rainfall = float(weather.get("rainfall", 20) or 20)
        temperature = float(weather.get("temperature", 28) or 28)
        humidity = float(weather.get("humidity", 80) or 80)
        prediction = self.predict_flood_risk(
            rainfall=rainfall,
            water_level=2.8,
            flow_rate=140,
            location=location["label"],
            live=False,
            temperature=temperature,
            humidity=humidity,
        )
        reasons = prediction.get("reasons", [])[:3]
        reason_text = "; ".join(reasons) if reasons else "risk drivers are currently limited"
        return (
            f"Flood risk in {location['label']} is {prediction['risk']} with "
            f"{prediction['probability']}% probability and {int(prediction.get('confidence', 0) * 100)}% confidence. "
            f"Main reasons: {reason_text}."
        )

    def _forecast_reply(self, location):
        forecast = self.predict_risk_forecast(
            location=location["label"],
            rainfall=20,
            water_level=2.8,
            flow_rate=140,
            temperature=28,
            humidity=80,
        )
        items = []
        for item in forecast[:4]:
            items.append(f"{item['label']}: {item['risk']} ({item['probability']}%)")
        return f"Risk forecast for {location['label']} -> " + ", ".join(items) + "."

    def _shelter_reply(self, location):
        plan = self.shelter_service.build_safe_route_plan(
            location["lat"],
            location["lon"],
            "Moderate",
            preferred_state=location["state"],
            preferred_district=location["district"],
        )
        shelter = plan.get("recommended_shelter")
        if not shelter:
            return f"I could not find shelter data for {location['label']} yet."
        return (
            f"Nearest shelter for {location['label']} is {shelter['name']} in {shelter.get('district', location['district'])}, "
            f"{shelter.get('state', location['state'])}, about {shelter['distance_km']} km away."
        )

    def _route_reply(self, location):
        plan = self.shelter_service.build_safe_route_plan(
            location["lat"],
            location["lon"],
            "High",
            preferred_state=location["state"],
            preferred_district=location["district"],
        )
        shelter = plan.get("recommended_shelter")
        if not shelter:
            return f"Safe-route guidance is unavailable for {location['label']} right now."
        return (
            f"Recommended safe route for {location['label']}: head toward {shelter['name']} "
            f"({shelter['distance_km']} km). Advice: {plan.get('travel_advice', 'Use major roads and avoid low-lying areas')}."
        )

    def _simulation_reply(self, message, location):
        duration = self._extract_number(message, r"(\d+(?:\.\d+)?)\s*(?:hours|hrs|hr)", 6)
        intensity = self._extract_number(message, r"(\d+(?:\.\d+)?)\s*mm", 15)
        total_rainfall = round(duration * intensity, 2)
        prediction = self.predict_flood_risk(
            rainfall=total_rainfall,
            water_level=3.2,
            flow_rate=160,
            location=location["label"],
            live=False,
            temperature=27,
            humidity=84,
        )
        return (
            f"If {location['label']} receives about {intensity} mm per hour for {duration} hours "
            f"(roughly {total_rainfall} mm total), the projected risk is {prediction['risk']} "
            f"with {prediction['probability']}% probability."
        )

    def _status_reply(self):
        status = self.get_model_status()
        mode = str(status.get("active_mode", "unknown")).replace("_", " ")
        note = status.get("compatibility_note") or "Model artifacts are currently compatible."
        return f"Current prediction mode: {mode}. {note}"

    @staticmethod
    def _help_reply():
        return (
            "I can help with weather, flood risk, forecast, shelters, safe routes, and scenario questions. "
            "Try messages like: 'weather in Chennai', 'flood risk in Erode', "
            "'24 hour forecast for Coimbatore', 'nearest shelter in Salem', or "
            "'simulate 12 mm for 8 hours in Chennai'."
        )

    def process_message(self, message, context=None):
        context = context or {}
        cleaned = (message or "").strip()
        if not cleaned:
            return {
                "intent": "empty",
                "reply": self._help_reply(),
                "location": None,
                "data": {},
            }

        lowered = cleaned.lower()
        fallback_location = context.get("location")
        location = self._extract_location(cleaned, fallback_location=fallback_location)
        location_label = location["label"] if location else None

        if any(word in lowered for word in ("hello", "hi", "hey", "help")):
            intent = "help"
            reply = self._help_reply()
        elif "model" in lowered and "status" in lowered:
            intent = "model_status"
            reply = self._status_reply()
        elif any(word in lowered for word in ("simulate", "scenario")):
            intent = "simulation"
            reply = self._simulation_reply(cleaned, location)
        elif "route" in lowered:
            intent = "route"
            reply = self._route_reply(location)
        elif "shelter" in lowered:
            intent = "shelter"
            reply = self._shelter_reply(location)
        elif "forecast" in lowered:
            intent = "forecast"
            reply = self._forecast_reply(location)
        elif any(word in lowered for word in ("explain", "why")):
            intent = "risk_explanation"
            reply = self._risk_reply(location)
        elif "weather" in lowered or "temperature" in lowered or "humidity" in lowered:
            intent = "weather"
            reply = self._weather_reply(location)
        elif "risk" in lowered or "flood" in lowered:
            intent = "risk"
            reply = self._risk_reply(location)
        else:
            intent = "help"
            reply = self._help_reply()

        return {
            "intent": intent,
            "reply": reply,
            "location": location_label,
            "data": {"location": location_label},
        }
