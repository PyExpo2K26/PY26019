import os
import pickle
import numpy as np
import pandas as pd


class CombinedFloodPredictor:
    """
    Combines ML model predictions with hydrological model predictions
    to produce a unified flood risk assessment.
    """

    def __init__(
        self,
        ml_model_path: str = 'flood_prediction_model_hydro.pkl',
        scaler_path: str   = 'scaler_hydro.pkl',
        workspace: str     = 'hydro_data',
    ):
        self.workspace      = workspace
        self.ml_model_path  = ml_model_path
        self.scaler_path    = scaler_path
        self.ml_model       = None
        self.scaler         = None

        # Load ML model + scaler if they exist on disk
        self._load_ml_assets()

    # ──────────────────────────────────────────────────────────────────────
    # Private helpers
    # ──────────────────────────────────────────────────────────────────────

    def _load_ml_assets(self):
        """Load the pickled model and scaler (silently skip if not found)."""
        if os.path.exists(self.ml_model_path):
            with open(self.ml_model_path, 'rb') as f:
                self.ml_model = pickle.load(f)
        else:
            print(f"[CombinedFloodPredictor] ML model not found at '{self.ml_model_path}'. "
                  "Predictions will use rule-based fallback.")

        if os.path.exists(self.scaler_path):
            with open(self.scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
        else:
            print(f"[CombinedFloodPredictor] Scaler not found at '{self.scaler_path}'. "
                  "Raw features will be used.")

    def _ml_predict(self, rainfall: float, water_level: float) -> dict:
        """Return ML probability and risk level."""
        features = np.array([[rainfall, water_level]])

        if self.scaler is not None:
            features = self.scaler.transform(features)

        if self.ml_model is not None:
            prob = float(self.ml_model.predict_proba(features)[0][1])
        else:
            # Simple rule-based fallback when no model is loaded
            prob = min(1.0, (rainfall / 250.0) * 0.7 + (water_level / 15.0) * 0.3)

        if prob < 0.30:
            risk = 'Low'
        elif prob < 0.50:
            risk = 'Medium'
        elif prob < 0.70:
            risk = 'High'
        else:
            risk = 'Very High'

        return {'probability': prob, 'risk_level': risk}

    def _hydro_predict(self, rainfall: float, water_level: float) -> dict:
        """
        Simple hydrological estimates.
        Replace / extend this with your real hydrological model.
        """
        # Rational method approximation
        runoff_coeff   = min(0.95, 0.3 + (rainfall / 500.0))
        runoff_mm      = rainfall * runoff_coeff
        wl_rise        = runoff_mm / 50.0                        # rough m rise
        flooded_pct    = min(100.0, runoff_mm / 2.0)
        max_depth      = min(10.0,  wl_rise * 1.5)
        avg_depth      = max_depth * 0.4

        return {
            'runoff_mm':          round(runoff_mm,   2),
            'water_level_rise_m': round(wl_rise,     3),
            'flooded_area_pct':   round(flooded_pct, 2),
            'max_depth_m':        round(max_depth,   3),
            'avg_depth_m':        round(avg_depth,   3),
            # Raster paths are None unless a full GIS pipeline runs
            'flood_depth_raster': None,
            'severity_raster':    None,
        }

    @staticmethod
    def _combine_risk(ml_risk: str, hydro: dict) -> str:
        """Merge ML risk and hydrological metrics into one risk label."""
        rank = {'Low': 1, 'Medium': 2, 'High': 3, 'Very High': 4}

        # Bump up if hydrological signals are severe
        hydro_risk = 'Low'
        if hydro['flooded_area_pct'] > 50 or hydro['max_depth_m'] > 3:
            hydro_risk = 'Very High'
        elif hydro['flooded_area_pct'] > 25 or hydro['max_depth_m'] > 1.5:
            hydro_risk = 'High'
        elif hydro['flooded_area_pct'] > 10 or hydro['max_depth_m'] > 0.5:
            hydro_risk = 'Medium'

        combined_rank  = max(rank[ml_risk], rank[hydro_risk])
        reverse_rank   = {v: k for k, v in rank.items()}
        return reverse_rank[combined_rank]

    # ──────────────────────────────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────────────────────────────

    def predict(
        self,
        location: str,
        rainfall: float,
        water_level: float,
        force_hydro: bool = True,
        return_maps: bool = False,
    ) -> dict:
        """
        Run a combined ML + hydrological flood prediction.

        Args:
            location    : place name string
            rainfall    : rainfall in mm
            water_level : current water level in metres
            force_hydro : always run hydrological model (default True)
            return_maps : generate raster maps (requires full GIS pipeline)

        Returns:
            dict with keys:
              ml_prediction, hydro_prediction,
              combined_risk_level, location, rainfall, water_level
        """
        ml_result    = self._ml_predict(rainfall, water_level)
        hydro_result = self._hydro_predict(rainfall, water_level)
        combined     = self._combine_risk(ml_result['risk_level'], hydro_result)

        return {
            'location':            location,
            'rainfall':            rainfall,
            'water_level':         water_level,
            'ml_prediction':       ml_result,
            'hydro_prediction':    hydro_result,
            'combined_risk_level': combined,
        }
