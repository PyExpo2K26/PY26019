import unittest
from collections import deque

from services.predictor_service import PredictorService


class PredictorServiceTests(unittest.TestCase):
    def make_service(self):
        self.broadcast_calls = []

        def broadcast_alert(location, risk, prob, rainfall, water_level):
            self.broadcast_calls.append((location, risk, prob, rainfall, water_level))

        return PredictorService(
            combined_ok=False,
            combined_predictor=None,
            base_model=None,
            db_ok=False,
            db=None,
            broadcast_alert=broadcast_alert,
            weather_ok=False,
            fetch_live_weather=None,
            fetch_weather_forecast=None,
            normalize_city=None,
            city_api_map={},
            owm_api_key=None,
            base_values={"Test City": {"rainfall": 40, "water": 7.0}},
            alert_log=deque(maxlen=10),
            alert_cooldowns={},
        )

    def test_rule_based_prediction_returns_expected_shape(self):
        service = self.make_service()

        result = service.predict_flood_risk(30, 2.5, 100, location="Test City")

        self.assertIn("risk", result)
        self.assertIn("probability", result)
        self.assertEqual(result["model"], "Rule-based")

    def test_live_high_risk_prediction_triggers_broadcast(self):
        service = self.make_service()

        result = service.predict_flood_risk(200, 5.0, 220, location="Test City", live=True)

        self.assertIn(result["risk"], ("High", "Very High"))
        self.assertEqual(len(self.broadcast_calls), 1)

    def test_history_generation_uses_requested_length(self):
        service = self.make_service()

        rows = service.gen_history("Test City", hours=5)

        self.assertEqual(len(rows), 5)
        self.assertIn("timestamp", rows[0])
        self.assertIn("risk_level", rows[0])

    def test_model_status_reports_rule_based_mode(self):
        service = self.make_service()

        status = service.get_model_status()

        self.assertEqual(status["active_mode"], "rule_based_only")
        self.assertFalse(status["base_model_available"])


if __name__ == "__main__":
    unittest.main()
