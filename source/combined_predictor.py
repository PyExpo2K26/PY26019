import os
import pickle
import warnings
import numpy as np
import pandas as pd


class CombinedFloodPredictor:
    """
    Combines ML model predictions with hydrological model predictions
    to produce a unified flood risk assessment.
    """

    def __init__(
        self,
        ml_model_path: str = None,
        scaler_path: str = None,
        workspace: str = 'hydro_data',
    ):
        self.workspace = workspace
        self.ml_model_path = ml_model_path or os.getenv(
            'COMBINED_MODEL_PATH',
            'artifacts/models/combined_flood_model.pkl'
        )
        self.scaler_path = scaler_path or os.getenv(
            'COMBINED_SCALER_PATH',
            'artifacts/models/combined_scaler.pkl'
        )
        self.ml_model = None
        self.scaler = None
        self.artifacts_compatible = True
        self.compatibility_note = None

        self._load_ml_assets()

    def _load_ml_assets(self):
        """Load the pickled model and scaler if they exist."""
        if os.path.exists(self.ml_model_path):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Trying to unpickle estimator")
                with open(self.ml_model_path, 'rb') as f:
                    self.ml_model = pickle.load(f)
        else:
            print(
                f"[CombinedFloodPredictor] ML model not found at '{self.ml_model_path}'. "
                "Predictions will use rule-based fallback."
            )

        if os.path.exists(self.scaler_path):
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", message="Trying to unpickle estimator")
                with open(self.scaler_path, 'rb') as f:
                    self.scaler = pickle.load(f)
        else:
            print(
                f"[CombinedFloodPredictor] Scaler not found at '{self.scaler_path}'. "
                "Raw features will be used."
            )

        expected_counts = [
            getattr(self.scaler, "n_features_in_", None),
            getattr(self.ml_model, "n_features_in_", None),
        ]
        expected_counts = [count for count in expected_counts if count is not None]
        if expected_counts and any(count != 2 for count in expected_counts):
            expected = max(expected_counts)
            self.artifacts_compatible = False
            self.compatibility_note = (
                f"Incompatible ML artifacts detected: saved assets expect {expected} features, "
                "but CombinedFloodPredictor currently supplies 2. Rule-based fallback will be used."
            )
            self.ml_model = None
            self.scaler = None
            print(f"[CombinedFloodPredictor] {self.compatibility_note}")

    def _ml_predict(self, rainfall: float, water_level: float) -> dict:
        """Return ML probability and risk level."""
        features = np.array([[rainfall, water_level]])
        prob = min(1.0, (rainfall / 250.0) * 0.7 + (water_level / 15.0) * 0.3)
        if self.scaler is not None and self.ml_model is not None:
            try:
                features = self.scaler.transform(features)
                prob = float(self.ml_model.predict_proba(features)[0][1])
            except Exception as e:
                print(f"[CombinedFloodPredictor] Falling back to rule-based ML score: {e}")

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
        Replace or extend this with your real hydrological model.
        """
        runoff_coeff = min(0.95, 0.3 + (rainfall / 500.0))
        runoff_mm = rainfall * runoff_coeff
        wl_rise = runoff_mm / 50.0
        flooded_pct = min(100.0, runoff_mm / 2.0)
        max_depth = min(10.0, wl_rise * 1.5)
        avg_depth = max_depth * 0.4

        return {
            'runoff_mm': round(runoff_mm, 2),
            'water_level_rise_m': round(wl_rise, 3),
            'flooded_area_pct': round(flooded_pct, 2),
            'max_depth_m': round(max_depth, 3),
            'avg_depth_m': round(avg_depth, 3),
            'flood_depth_raster': None,
            'severity_raster': None,
        }

    @staticmethod
    def _combine_risk(ml_risk: str, hydro: dict) -> str:
        """Merge ML risk and hydrological metrics into one risk label."""
        rank = {'Low': 1, 'Medium': 2, 'High': 3, 'Very High': 4}

        hydro_risk = 'Low'
        if hydro['flooded_area_pct'] > 50 or hydro['max_depth_m'] > 3:
            hydro_risk = 'Very High'
        elif hydro['flooded_area_pct'] > 25 or hydro['max_depth_m'] > 1.5:
            hydro_risk = 'High'
        elif hydro['flooded_area_pct'] > 10 or hydro['max_depth_m'] > 0.5:
            hydro_risk = 'Medium'

        combined_rank = max(rank[ml_risk], rank[hydro_risk])
        reverse_rank = {v: k for k, v in rank.items()}
        return reverse_rank[combined_rank]

    def predict(
        self,
        location: str,
        rainfall: float,
        water_level: float,
        temperature: float = None,
        humidity: float = None,
        force_hydro: bool = True,
        return_maps: bool = False,
    ) -> dict:
        """
        Run a combined ML + hydrological flood prediction.
        """
        ml_result = self._ml_predict(rainfall, water_level)
        hydro_result = self._hydro_predict(rainfall, water_level)
        combined = self._combine_risk(ml_result['risk_level'], hydro_result)

        return {
            'location': location,
            'rainfall': rainfall,
            'water_level': water_level,
            'temperature': temperature,
            'humidity': humidity,
            'ml_prediction': ml_result,
            'hydro_prediction': hydro_result,
            'combined_risk_level': combined,
            'force_hydro': force_hydro,
            'return_maps': return_maps,
        }
