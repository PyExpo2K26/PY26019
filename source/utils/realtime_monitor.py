# ═══════════════════════════════════════════════════════════════════════════
# REAL-TIME MONITORING & AUTOMATED PREDICTIONS
# FILE: utils/realtime_monitor.py
# ═══════════════════════════════════════════════════════════════════════════

import os
import sys
import time
import requests
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import json
import threading

# ── Fix import path ──────────────────────────────────────────────────────────
_utils_path = os.path.abspath(os.path.join(os.path.dirname(__file__)))
if _utils_path not in sys.path:
    sys.path.insert(0, _utils_path)

try:
    import schedule
except ImportError:
    schedule = None  # Optional — only needed for start_monitoring()

from alert_service import AlertService  # ← fixed: import the class, not a function

# alert_history is optional — won't crash if it doesn't exist
try:
    from alert_history import log_alert as _log_alert_external
except ImportError:
    _log_alert_external = None

# combined_predictor is optional
try:
    from combined_predictor import CombinedFloodPredictor
    _has_predictor = True
except ImportError:
    _has_predictor = False


class RealtimeFloodMonitor:
    """
    Automated flood monitoring system that runs predictions periodically.
    """

    def __init__(self, locations, check_interval_hours=6, workspace='hydro_data'):
        self.locations        = locations
        self.check_interval   = check_interval_hours
        self.workspace        = workspace
        self.is_running       = False
        self.last_check       = {}
        self.prediction_log   = []

        # Initialize alert service
        self.alert_service = AlertService()

        # Initialize predictor if available
        self.predictor = CombinedFloodPredictor(workspace=workspace) if _has_predictor else None

        # Weather sources
        self.weather_sources = {
            'openweathermap': {
                'enabled': False,
                'api_key': None,
                'base_url': 'https://api.openweathermap.org/data/2.5/weather'
            },
            'gpm': {'enabled': False, 'credentials': None}
        }

        # Alert config
        self.alert_config = {
            'email_enabled': False,
            'email_address': None,
            'sms_enabled':   False,
            'phone_number':  None
        }

        # Log file
        self.log_file = os.path.join(workspace, 'monitoring_log.json')
        self._load_log()

    # ── Configuration ─────────────────────────────────────────────────────────

    def configure_weather_api(self, service='openweathermap', api_key=None, credentials=None):
        if service == 'openweathermap':
            self.weather_sources['openweathermap']['enabled'] = True
            self.weather_sources['openweathermap']['api_key'] = api_key
            print("✓ OpenWeatherMap configured")
        elif service == 'gpm':
            self.weather_sources['gpm']['enabled'] = True
            self.weather_sources['gpm']['credentials'] = credentials
            print("✓ NASA GPM configured")

    def configure_alerts(self, email=None, phone=None):
        if email:
            self.alert_config['email_enabled'] = True
            self.alert_config['email_address'] = email
            print(f"✓ Email alerts enabled: {email}")
        if phone:
            self.alert_config['sms_enabled'] = True
            self.alert_config['phone_number'] = phone
            print(f"✓ SMS alerts enabled: {phone}")

    # ── Weather fetching ──────────────────────────────────────────────────────

    def fetch_live_rainfall(self, location):
        if self.weather_sources['openweathermap']['enabled']:
            try:
                return self._fetch_openweathermap(location)
            except Exception as e:
                print(f"OpenWeatherMap fetch failed: {e}")

        print(f"Warning: Using simulated rainfall data for {location}")
        return {
            'rainfall_mm': float(np.random.uniform(10, 150)),
            'temperature':  float(np.random.uniform(25, 32)),
            'humidity':     float(np.random.uniform(70, 95)),
            'wind_speed':   float(np.random.uniform(5, 25)),
            'source':       'simulated'
        }

    def _fetch_openweathermap(self, location):
        api_key  = self.weather_sources['openweathermap']['api_key']
        base_url = self.weather_sources['openweathermap']['base_url']
        city     = location.split(',')[0].strip()

        resp = requests.get(
            base_url,
            params={'q': city, 'appid': api_key, 'units': 'metric'},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        rainfall = 0
        if 'rain' in data:
            rainfall = data['rain'].get('1h', data['rain'].get('3h', 0))

        return {
            'rainfall_mm': rainfall,
            'temperature':  data['main']['temp'],
            'humidity':     data['main']['humidity'],
            'wind_speed':   data['wind']['speed'] * 3.6,
            'source':       'openweathermap',
            'timestamp':    datetime.now().isoformat()
        }

    # ── Prediction check ──────────────────────────────────────────────────────

    def run_check(self, location):
        print(f"\n{'='*70}")
        print(f"Running check for {location}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")

        weather = self.fetch_live_rainfall(location)
        print(f"  Rainfall:    {weather['rainfall_mm']:.1f} mm")
        print(f"  Temperature: {weather['temperature']:.1f} °C")
        print(f"  Humidity:    {weather['humidity']:.0f} %")
        print(f"  Source:      {weather['source']}")

        if self.predictor:
            result = self.predictor.predict(
                location=location,
                rainfall=weather['rainfall_mm'],
                water_level=7.5,
                temperature=weather['temperature'],
                humidity=weather['humidity'],
                return_maps=True
            )
        else:
            # Fallback: simple threshold-based result
            rf = weather['rainfall_mm']
            prob = min(0.99, rf / 200)
            result = {
                'ml_prediction':     {'probability': prob},
                'combined_risk_level': 'High' if rf > 100 else 'Medium' if rf > 50 else 'Low',
                'decision':          {'run_hydro': rf > 80},
                'weather':           weather
            }

        result['weather'] = weather

        self.prediction_log.append({
            'timestamp':      datetime.now().isoformat(),
            'location':       location,
            'rainfall_mm':    weather['rainfall_mm'],
            'ml_probability': result['ml_prediction']['probability'],
            'combined_risk':  result['combined_risk_level'],
            'hydro_run':      result['decision']['run_hydro']
        })
        self._save_log()

        self._check_and_send_alert(location, result)
        self.last_check[location] = datetime.now()

        print(f"\nCheck complete. Risk: {result['combined_risk_level']}")
        print(f"{'='*70}\n")
        return result

    # ── Alert sending ─────────────────────────────────────────────────────────

    def _check_and_send_alert(self, location, result):
        risk_level  = result['combined_risk_level']
        probability = result['ml_prediction']['probability']
        rainfall    = result['weather']['rainfall_mm']

        if risk_level not in ['High', 'Very High']:
            return

        if not (self.alert_config['email_enabled'] or self.alert_config['sms_enabled']):
            return

        print(f"\n🚨 ALERT TRIGGERED: {risk_level} risk detected for {location}!")

        # ── Use AlertService class methods (fixed) ────────────────────────────
        if self.alert_config['email_enabled'] and self.alert_config['email_address']:
            body = (
                f"FLOOD ALERT [{risk_level.upper()}]\n"
                f"Location   : {location}\n"
                f"Time       : {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n"
                f"Probability: {round(probability * 100, 1)}%\n"
                f"Rainfall   : {rainfall:.1f} mm\n"
                f"Action     : EVACUATE NOW. Move to higher ground.\n"
                f"Helpline   : 1070"
            )
            self.alert_service.send_email(
                to_email=self.alert_config['email_address'],
                subject=f"[FLOOD ALERT] {risk_level} Risk - {location}",
                body=body
            )

        if self.alert_config['sms_enabled'] and self.alert_config['phone_number']:
            sms_body = (
                f"FLOOD ALERT [{risk_level.upper()}] - {location}\n"
                f"Probability: {round(probability*100,1)}% | Rain: {rainfall:.1f}mm\n"
                f"EVACUATE NOW. Helpline: 1070"
            )
            self.alert_service.send_sms(
                to_number=self.alert_config['phone_number'],
                body=sms_body
            )

        # External log (optional)
        if _log_alert_external:
            try:
                _log_alert_external(
                    location=location,
                    risk_level=risk_level,
                    probability=probability,
                    rainfall=rainfall,
                    water_level=7.5,
                    channels_sent=(
                        ['email'] if self.alert_config['email_enabled'] else []
                    )
                )
            except Exception as e:
                print(f"[Monitor] External alert log error: {e}")

    # ── Log helpers ───────────────────────────────────────────────────────────

    def _load_log(self):
        try:
            if os.path.exists(self.log_file):
                with open(self.log_file, 'r') as f:
                    self.prediction_log = json.load(f)
        except Exception:
            self.prediction_log = []

    def _save_log(self):
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, 'w') as f:
                json.dump(self.prediction_log, f, indent=2)
        except Exception as e:
            print(f"[Monitor] Log save error: {e}")

    def get_recent_predictions(self, location=None, hours=24):
        cutoff   = datetime.now() - timedelta(hours=hours)
        filtered = [
            p for p in self.prediction_log
            if datetime.fromisoformat(p['timestamp']) > cutoff
            and (location is None or p['location'] == location)
        ]
        return pd.DataFrame(filtered)

    # ── Monitoring loop ───────────────────────────────────────────────────────

    def start_monitoring(self):
        if schedule is None:
            print("Install schedule first:  pip install schedule")
            return

        if self.is_running:
            print("Monitoring already running.")
            return

        print(f"Starting automated monitoring...")
        print(f"Locations: {', '.join(self.locations)}")
        print(f"Interval : every {self.check_interval} hours")
        print("Press Ctrl+C to stop.\n")

        self.is_running = True

        for loc in self.locations:
            schedule.every(self.check_interval).hours.do(self.run_check, location=loc)

        # Run initial check immediately
        for loc in self.locations:
            try:
                self.run_check(loc)
            except Exception as e:
                print(f"Error in initial check for {loc}: {e}")

        try:
            while self.is_running:
                schedule.run_pending()
                time.sleep(60)
        except KeyboardInterrupt:
            print("\nMonitoring stopped by user.")
            self.is_running = False

    def start_monitoring_background(self):
        thread = threading.Thread(target=self.start_monitoring, daemon=True)
        thread.start()
        print("Background monitoring started.")
        return thread

    def stop_monitoring(self):
        self.is_running = False
        if schedule:
            schedule.clear()
        print("Monitoring stopped.")