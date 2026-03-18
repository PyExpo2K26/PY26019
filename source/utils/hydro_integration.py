"""
hydro_integration.py
Place this file in: D:/FloodPredictionApp/utils/hydro_integration.py

Rewritten to remove rasterio, rasterstats, geopandas, pysheds dependencies.
Uses only numpy, pandas, scipy — all already installed in your venv.
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime


# ─────────────────────────────────────────────────────────────────────────────
# Location presets — bounds and curve numbers for Indian cities
# ─────────────────────────────────────────────────────────────────────────────
LOCATION_PRESETS = {
    "Mumbai":     {"bounds": (72.77, 18.89, 72.99, 19.27), "cn": 85, "area_km2": 603},
    "Chennai":    {"bounds": (80.17, 12.90, 80.32, 13.23), "cn": 78, "area_km2": 426},
    "Kolkata":    {"bounds": (88.20, 22.40, 88.50, 22.70), "cn": 82, "area_km2": 185},
    "Assam":      {"bounds": (90.50, 25.50, 92.80, 27.50), "cn": 75, "area_km2": 78438},
    "Kerala":     {"bounds": (74.85, 8.18,  77.42, 12.78), "cn": 72, "area_km2": 38852},
    "Coimbatore": {"bounds": (76.80, 10.85, 77.10, 11.10), "cn": 70, "area_km2": 246},
}


class HydroModel:
    """
    Hydrology model for flood prediction.
    Uses SCS Curve Number method + simplified HAND-based inundation.
    No GIS libraries required — works with numpy/pandas only.
    """

    def __init__(self, location="Mumbai", bounds=None, workspace="hydro_data"):
        self.location  = location
        self.workspace = os.path.join(workspace, location.lower())
        os.makedirs(self.workspace, exist_ok=True)

        preset = LOCATION_PRESETS.get(location, LOCATION_PRESETS["Mumbai"])
        self.bounds   = bounds or preset["bounds"]
        self.base_cn  = preset["cn"]
        self.area_km2 = preset["area_km2"]

        # Basin always "ready" — no GIS files needed
        self.basin_ready = True

    # ── Status ────────────────────────────────────────────────────────────────

    def check_basin_ready(self):
        return True

    def setup_basin(self, pour_point=None):
        """No GIS setup needed in this version."""
        print(f"Basin for {self.location} is ready (lightweight mode).")
        return {"status": "ready", "location": self.location}

    # ── Core hydrology ────────────────────────────────────────────────────────

    def _calculate_runoff(self, rainfall_mm, cn=None, antecedent="II"):
        """
        SCS Curve Number method.
        Returns runoff depth in mm.
        """
        cn = cn or self.base_cn

        # Antecedent moisture correction
        if antecedent == "I":    cn = max(30, cn - 10)
        elif antecedent == "III": cn = min(99, cn + 10)

        S  = (25400 / cn) - 254          # Potential max retention (mm)
        Ia = 0.2 * S                      # Initial abstraction

        if rainfall_mm <= Ia:
            return 0.0

        runoff = ((rainfall_mm - Ia) ** 2) / (rainfall_mm - Ia + S)
        return round(max(0.0, runoff), 2)

    def _estimate_peak_flow(self, runoff_mm, duration_hr=6):
        """
        Simplified rational / SCS peak flow estimate.
        Returns peak flow in m³/s.
        """
        area_m2    = self.area_km2 * 1e6
        runoff_m   = runoff_mm / 1000
        volume_m3  = area_m2 * runoff_m
        peak_flow  = volume_m3 / (duration_hr * 3600)
        return round(peak_flow, 2)

    def _estimate_water_level(self, runoff_mm):
        """
        Estimate stream water level rise from runoff depth.
        Returns water level rise in metres.
        """
        # Simplified: assume bankfull at ~50 mm runoff for most Indian rivers
        bankfull_runoff = 50.0
        level_rise = (runoff_mm / bankfull_runoff) * 3.0   # up to ~3 m rise
        return round(min(level_rise, 8.0), 3)

    def _simulate_inundation(self, water_level_m):
        """
        Simulate flood inundation using a synthetic HAND distribution.
        Returns flood statistics dict.
        """
        # Synthetic HAND distribution (metres above nearest drainage)
        rng  = np.random.default_rng(seed=42)
        hand = np.abs(rng.exponential(scale=4.0, size=10000))

        flooded    = hand < water_level_m
        pct        = flooded.mean() * 100
        depths     = np.where(flooded, water_level_m - hand[flooded], 0)
        flood_area = self.area_km2 * (pct / 100)

        return {
            "flooded_percent": round(pct, 1),
            "flood_area_km2":  round(flood_area, 1),
            "max_depth_m":     round(float(depths.max()) if depths.size else 0, 2),
            "avg_depth_m":     round(float(depths.mean()) if depths.size else 0, 2),
            "water_level_m":   round(water_level_m, 3),
        }

    # ── Main prediction ───────────────────────────────────────────────────────

    def predict_flood(self, rainfall_mm, antecedent="II", duration_hr=6):
        """
        Complete flood prediction for a given rainfall event.

        Args:
            rainfall_mm   : Total rainfall (mm)
            antecedent    : Soil moisture condition — 'I', 'II', or 'III'
            duration_hr   : Storm duration in hours

        Returns:
            dict with full prediction results
        """
        runoff_mm      = self._calculate_runoff(rainfall_mm, antecedent=antecedent)
        peak_flow      = self._estimate_peak_flow(runoff_mm, duration_hr)
        water_level_m  = self._estimate_water_level(runoff_mm)
        inundation     = self._simulate_inundation(water_level_m)

        # Risk classification
        if inundation["flooded_percent"] >= 30 or water_level_m >= 3.0:
            risk = "Very High"
        elif inundation["flooded_percent"] >= 15 or water_level_m >= 1.5:
            risk = "High"
        elif inundation["flooded_percent"] >= 5 or water_level_m >= 0.5:
            risk = "Medium"
        else:
            risk = "Low"

        probability = min(0.99, inundation["flooded_percent"] / 100 * 2.5)

        result = {
            "location":         self.location,
            "timestamp":        datetime.now().isoformat(),
            "rainfall_mm":      rainfall_mm,
            "runoff_mm":        runoff_mm,
            "infiltration_mm":  round(rainfall_mm - runoff_mm, 2),
            "peak_flow_m3s":    peak_flow,
            "water_level_rise_m": water_level_m,
            "stats":            inundation,
            "risk_level":       risk,
            "probability":      round(probability, 3),
            "curve_number":     self.base_cn,
            "area_km2":         self.area_km2,
        }

        self._save_result(result, rainfall_mm)
        return result

    # ── Batch prediction ──────────────────────────────────────────────────────

    def batch_predict(self, rainfall_scenarios):
        """
        Run predictions for multiple rainfall amounts.

        Args:
            rainfall_scenarios: list of rainfall values in mm

        Returns:
            pandas DataFrame with one row per scenario
        """
        rows = []
        for rf in rainfall_scenarios:
            r = self.predict_flood(rf)
            rows.append({
                "rainfall_mm":      r["rainfall_mm"],
                "runoff_mm":        r["runoff_mm"],
                "water_level_m":    r["water_level_rise_m"],
                "peak_flow_m3s":    r["peak_flow_m3s"],
                "flooded_percent":  r["stats"]["flooded_percent"],
                "flood_area_km2":   r["stats"]["flood_area_km2"],
                "max_depth_m":      r["stats"]["max_depth_m"],
                "avg_depth_m":      r["stats"]["avg_depth_m"],
                "risk_level":       r["risk_level"],
                "probability":      r["probability"],
            })
        return pd.DataFrame(rows)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def get_location_info(self):
        """Return metadata about the current location."""
        west, south, east, north = self.bounds
        return {
            "location":  self.location,
            "bounds":    self.bounds,
            "center":    ((south + north) / 2, (west + east) / 2),
            "area_km2":  self.area_km2,
            "base_cn":   self.base_cn,
        }

    def _save_result(self, result, rainfall_mm):
        """Save prediction result to CSV log."""
        try:
            log_path = os.path.join(self.workspace, "predictions_log.csv")
            flat = {
                "timestamp":        result["timestamp"],
                "location":         result["location"],
                "rainfall_mm":      result["rainfall_mm"],
                "runoff_mm":        result["runoff_mm"],
                "water_level_m":    result["water_level_rise_m"],
                "peak_flow_m3s":    result["peak_flow_m3s"],
                "flooded_percent":  result["stats"]["flooded_percent"],
                "flood_area_km2":   result["stats"]["flood_area_km2"],
                "max_depth_m":      result["stats"]["max_depth_m"],
                "risk_level":       result["risk_level"],
                "probability":      result["probability"],
            }
            df  = pd.DataFrame([flat])
            hdr = not os.path.exists(log_path)
            df.to_csv(log_path, mode="a", header=hdr, index=False)
        except Exception as e:
            print(f"[HydroModel] Log save error: {e}")

    def calculate_hand(self):
        """
        Placeholder — HAND calculation not needed in lightweight mode.
        Inundation is simulated directly from runoff depth.
        """
        print(f"[HydroModel] HAND calculation skipped (lightweight mode).")
        self.hand_path = None
        return None

    def create_web_map(self, flood_result, output_html=None):
        """
        Placeholder — returns None (no GIS map in lightweight mode).
        The Streamlit page renders charts instead.
        """
        return None