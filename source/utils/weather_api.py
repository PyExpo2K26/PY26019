"""
Weather API Integration for Flood Prediction System
Uses OpenWeatherMap API to fetch live weather data
"""

import requests
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("OWM_API_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OpenWeatherMap API Configuration
BASE_URL = "https://api.openweathermap.org/data/2.5/weather"

def get_live_weather(city):
    """
    Fetch live weather data from OpenWeatherMap API
    
    Args:
        city (str): City name (e.g., 'Mumbai', 'Chennai', 'Kolkata')
    
    Returns:
        dict: Weather data including temperature, humidity, rainfall, wind speed
        None: If API call fails
    """
    try:
        # Build API request
        params = {
            'q': city,
            'appid': API_KEY,
            'units': 'metric'  # Celsius for temperature
        }
        
        logger.info(f"Fetching weather data for {city}...")
        
        # Make API request with timeout
        response = requests.get(BASE_URL, params=params, timeout=10)
        
        # Check if request was successful
        if response.status_code != 200:
            logger.error(f"API Error: Status {response.status_code} for {city}")
            logger.error(f"Response: {response.text}")
            return None
        
        # Parse JSON response
        data = response.json()
        
        # Extract weather data
        weather_data = {
            "temperature": round(data["main"]["temp"], 1),
            "humidity": data["main"]["humidity"],
            "rainfall": data.get("rain", {}).get("1h", 0),  # Rainfall in last hour (mm)
            "wind_speed": round(data["wind"]["speed"] * 3.6, 1),  # Convert m/s to km/h
            "pressure": data["main"]["pressure"],
            "city": data["name"],
            "description": data["weather"][0]["description"],
            "feels_like": round(data["main"]["feels_like"], 1),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        logger.info(f"Successfully fetched weather for {city}: {weather_data['temperature']}°C, {weather_data['humidity']}% humidity")
        
        return weather_data
    
    except requests.Timeout:
        logger.error(f"Timeout while fetching weather for {city}")
        return None
    
    except requests.RequestException as e:
        logger.error(f"Network error while fetching weather for {city}: {e}")
        return None
    
    except KeyError as e:
        logger.error(f"Unexpected API response format for {city}: {e}")
        return None
    
    except Exception as e:
        logger.error(f"Unexpected error fetching weather for {city}: {e}")
        return None


def get_weather_forecast(city, days=3):
    """
    Fetch weather forecast for upcoming days
    
    Args:
        city (str): City name
        days (int): Number of days (max 5 for free tier)
    
    Returns:
        list: Forecast data for each day
        None: If API call fails
    """
    try:
        forecast_url = "https://api.openweathermap.org/data/2.5/forecast"
        
        params = {
            'q': city,
            'appid': API_KEY,
            'units': 'metric',
            'cnt': days * 8  # API returns 3-hour intervals, so 8 per day
        }
        
        logger.info(f"Fetching {days}-day forecast for {city}...")
        
        response = requests.get(forecast_url, params=params, timeout=10)
        
        if response.status_code != 200:
            logger.error(f"Forecast API Error: Status {response.status_code}")
            return None
        
        data = response.json()
        
        # Process forecast data
        forecast_list = []
        for item in data['list']:
            forecast_list.append({
                'datetime': item['dt_txt'],
                'temperature': round(item['main']['temp'], 1),
                'humidity': item['main']['humidity'],
                'rainfall': item.get('rain', {}).get('3h', 0),
                'description': item['weather'][0]['description']
            })
        
        logger.info(f"Successfully fetched {len(forecast_list)} forecast entries for {city}")
        
        return forecast_list
    
    except Exception as e:
        logger.error(f"Error fetching forecast for {city}: {e}")
        return None


def test_api_connection():
    """
    Test if OpenWeatherMap API is working
    
    Returns:
        bool: True if API is working, False otherwise
    """
    try:
        test_city = "Mumbai"
        weather = get_live_weather(test_city)
        
        if weather and 'temperature' in weather:
            logger.info(f"✓ API Connection Successful - Test city: {test_city}, Temp: {weather['temperature']}°C")
            return True
        else:
            logger.error("✗ API Connection Failed - No valid response")
            return False
    
    except Exception as e:
        logger.error(f"✗ API Connection Test Failed: {e}")
        return False


# City name mapping for common variations
CITY_ALIASES = {
    "mumbai maharashtra": "Mumbai",
    "kolkata west bengal": "Kolkata",
    "chennai tamil nadu": "Chennai",
    "assam valley": "Guwahati",
    "kerala coast": "Kochi",
    "delhi": "Delhi",
    "hyderabad telangana": "Hyderabad",
    "bangalore": "Bangalore",
    "bengaluru": "Bangalore"
}


def normalize_city_name(location):
    """
    Convert location string to API-compatible city name
    
    Args:
        location (str): Location name from app
    
    Returns:
        str: Normalized city name for API
    """
    location_lower = location.lower().strip()
    
    # Check aliases
    if location_lower in CITY_ALIASES:
        return CITY_ALIASES[location_lower]
    
    # Extract first word (usually the city)
    return location.split(',')[0].strip()


if __name__ == "__main__":
    """Test the weather API"""
    print("=" * 60)
    print("WEATHER API TEST")
    print("=" * 60)
    
    # Test API connection
    print("\n1. Testing API Connection...")
    if test_api_connection():
        print("   ✓ API is working correctly")
    else:
        print("   ✗ API connection failed")
    
    # Test multiple cities
    print("\n2. Testing Multiple Cities...")
    test_cities = ["Mumbai", "Chennai", "Kolkata", "Delhi", "Guwahati"]
    
    for city in test_cities:
        weather = get_live_weather(city)
        if weather:
            print(f"\n   {city}:")
            print(f"   - Temperature: {weather['temperature']}°C")
            print(f"   - Humidity: {weather['humidity']}%")
            print(f"   - Rainfall: {weather['rainfall']} mm")
            print(f"   - Wind Speed: {weather['wind_speed']} km/h")
            print(f"   - Condition: {weather['description']}")
        else:
            print(f"\n   {city}: Failed to fetch data")
    
    print("\n" + "=" * 60)
