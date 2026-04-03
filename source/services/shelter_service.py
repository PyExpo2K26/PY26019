import json
import math
from pathlib import Path


class ShelterService:
    def __init__(self, data_path="artifacts/data/shelters.json"):
        self.data_path = Path(data_path)
        self._shelters = self._load()

    def _load(self):
        if not self.data_path.exists():
            return []
        with self.data_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _distance_km(lat1, lon1, lat2, lon2):
        r = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (
            math.sin(dlat / 2) ** 2
            + math.cos(math.radians(lat1))
            * math.cos(math.radians(lat2))
            * math.sin(dlon / 2) ** 2
        )
        return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def nearest_shelters(self, lat, lon, limit=5, preferred_state=None, preferred_district=None):
        ranked = []
        for shelter in self._shelters:
            distance = self._distance_km(lat, lon, shelter["lat"], shelter["lon"])
            ranked.append(
                {
                    **shelter,
                    "distance_km": round(distance, 2),
                }
            )
        same_district = []
        same_state = []
        others = []

        preferred_state = (preferred_state or "").strip().lower()
        preferred_district = (preferred_district or "").strip().lower()

        for item in ranked:
            shelter_state = str(item.get("state", "")).strip().lower()
            shelter_district = str(item.get("district", "")).strip().lower()
            if preferred_district and shelter_district == preferred_district and shelter_state == preferred_state:
                same_district.append(item)
            elif preferred_state and shelter_state == preferred_state:
                same_state.append(item)
            else:
                others.append(item)

        same_district.sort(key=lambda item: item["distance_km"])
        same_state.sort(key=lambda item: item["distance_km"])
        others.sort(key=lambda item: item["distance_km"])
        return (same_district + same_state + others)[:limit]

    def build_safe_route_plan(self, lat, lon, risk_level, limit=3, preferred_state=None, preferred_district=None):
        shelters = self.nearest_shelters(
            lat,
            lon,
            limit=limit,
            preferred_state=preferred_state,
            preferred_district=preferred_district,
        )
        if not shelters:
            return {
                "recommended_shelter": None,
                "travel_advice": "No shelter data available for this area.",
                "route_status": "unknown",
                "avoid_zones": [],
                "nearest_shelters": [],
            }

        primary = shelters[0]
        avoid_zones = [
            "Low-lying underpasses",
            "Riverbank roads",
            "Waterlogged junctions",
        ]

        if risk_level == "Very High":
            advice = "Move immediately to the nearest shelter using major roads only. Avoid low-lying routes."
            route_status = "evacuate_now"
        elif risk_level == "High":
            advice = "Travel to the nearest safe shelter soon. Avoid flooded streets and river-adjacent roads."
            route_status = "evacuate_soon"
        elif risk_level == "Moderate":
            advice = "Prepare a safe route and monitor updates. Use elevated roads if travel becomes necessary."
            route_status = "prepare_route"
        else:
            advice = "No immediate evacuation needed. Keep the nearest shelter details ready."
            route_status = "monitor"

        return {
            "recommended_shelter": primary,
            "travel_advice": advice,
            "route_status": route_status,
            "avoid_zones": avoid_zones,
            "nearest_shelters": shelters,
        }
