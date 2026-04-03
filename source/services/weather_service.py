from utils.weather_api import get_live_weather, get_weather_forecast, normalize_city_name
import requests


def fetch_live_weather(city):
    return get_live_weather(city)


def fetch_weather_forecast(city, days=3):
    return get_weather_forecast(city, days)


def normalize_city(city):
    return normalize_city_name(city)


def fetch_reverse_geocode(lat, lon):
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": lat,
                "lon": lon,
                "format": "jsonv2",
                "addressdetails": 1,
            },
            headers={
                "User-Agent": "FloodGuardIndia/1.0"
            },
            timeout=8,
        )
        if response.status_code != 200:
            return None

        payload = response.json()
        address = payload.get("address", {})
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("hamlet")
            or address.get("suburb")
        )
        state = address.get("state")
        country = address.get("country")

        parts = [part for part in (city, state, country) if part]
        if not parts:
            return None

        return {
            "label": ", ".join(parts),
            "city": city,
            "state": state,
            "country": country,
            "display_name": payload.get("display_name"),
        }
    except Exception:
        return None
