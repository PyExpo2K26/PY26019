import json
import os
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "artifacts" / "models"
BASE_MODEL_PATH = ARTIFACT_DIR / "flood_prediction_model.pkl"
BASE_SCALER_PATH = ARTIFACT_DIR / "scaler.pkl"
COMBINED_MODEL_PATH = ARTIFACT_DIR / "combined_flood_model.pkl"
COMBINED_SCALER_PATH = ARTIFACT_DIR / "combined_scaler.pkl"
METADATA_PATH = ARTIFACT_DIR / "model_metadata.json"


def train_base_model():
    csv_path = ROOT / "flood.csv"
    data = pd.read_csv(csv_path)
    x = data.drop("FloodProbability", axis=1)
    y = (data["FloodProbability"] >= 0.5).astype(int)

    x_train, _, y_train, _ = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    scaler = StandardScaler()
    x_train_scaled = scaler.fit_transform(x_train)
    model = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    model.fit(x_train_scaled, y_train)

    with BASE_SCALER_PATH.open("wb") as f:
        pickle.dump(scaler, f)
    with BASE_MODEL_PATH.open("wb") as f:
        pickle.dump(model, f)

    return {
        "feature_count": int(x.shape[1]),
        "feature_names": x.columns.tolist(),
        "rows": int(len(data)),
    }


def train_combined_model():
    rng = np.random.default_rng(42)
    rows = 6000
    rainfall = rng.uniform(0, 260, rows)
    water_level = rng.uniform(0.5, 8.0, rows)

    score = (rainfall / 250.0) * 0.7 + (water_level / 8.0) * 0.6
    probability = 1 / (1 + np.exp(-(score * 4 - 2.2)))
    labels = (probability >= 0.5).astype(int)

    x = np.column_stack([rainfall, water_level])
    scaler = StandardScaler()
    x_scaled = scaler.fit_transform(x)
    model = LogisticRegression(max_iter=1000, random_state=42)
    model.fit(x_scaled, labels)

    with COMBINED_SCALER_PATH.open("wb") as f:
        pickle.dump(scaler, f)
    with COMBINED_MODEL_PATH.open("wb") as f:
        pickle.dump(model, f)

    return {
        "feature_count": 2,
        "feature_names": ["rainfall", "water_level"],
        "rows": rows,
    }


def main():
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        base_meta = train_base_model()
        combined_meta = train_combined_model()

    metadata = {
        "base_model": base_meta,
        "combined_model": combined_meta,
        "generated_from": "scripts/retrain_models.py",
    }
    with METADATA_PATH.open("w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("Base model saved to", BASE_MODEL_PATH)
    print("Base scaler saved to", BASE_SCALER_PATH)
    print("Combined model saved to", COMBINED_MODEL_PATH)
    print("Combined scaler saved to", COMBINED_SCALER_PATH)
    print("Metadata saved to", METADATA_PATH)


if __name__ == "__main__":
    main()
