import unittest

from app import app


class PredictionRouteTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def login_session(self):
        with self.client.session_transaction() as session:
            session["user_email"] = "predict@example.com"
            session["user_name"] = "Predict User"

    def test_predict_json_returns_explainable_fields(self):
        response = self.client.post(
            "/predict",
            json={
                "location": "Chennai, Tamil Nadu",
                "rainfall": 45,
                "water_level": 2.4,
                "flow_rate": 120,
                "temperature": 29,
                "humidity": 82,
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("confidence", payload)
        self.assertIn("reasons", payload)
        self.assertIn("risk_level", payload)

    def test_district_prediction_requires_login(self):
        response = self.client.post(
            "/api/district-prediction",
            json={"state": "Tamil Nadu", "district": "Chennai"},
        )

        self.assertEqual(response.status_code, 401)

    def test_district_prediction_returns_success_for_valid_location(self):
        self.login_session()

        response = self.client.post(
            "/api/district-prediction",
            json={"state": "Tamil Nadu", "district": "Chennai"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["district"], "Chennai")
        self.assertIn("prediction", payload)

    def test_weather_forecast_endpoint_returns_json_shape(self):
        response = self.client.get("/api/weather-forecast?location=Chennai, Tamil Nadu")

        self.assertIn(response.status_code, (200, 500, 503))
        payload = response.get_json()
        self.assertIn("success", payload)

    def test_risk_forecast_endpoint_returns_timeline_when_logged_in(self):
        self.login_session()

        response = self.client.get("/api/risk-forecast?location=Chennai, Tamil Nadu")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(len(payload["forecast"]), 4)
        self.assertEqual(payload["forecast"][0]["label"], "now")

    def test_nearest_shelters_endpoint_returns_ranked_results(self):
        self.login_session()

        response = self.client.get("/api/nearest-shelters?location=Chennai, Tamil Nadu")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertGreaterEqual(len(payload["shelters"]), 1)
        self.assertIn("distance_km", payload["shelters"][0])

    def test_safe_route_endpoint_returns_route_plan(self):
        self.login_session()

        response = self.client.get("/api/safe-route?location=Chennai, Tamil Nadu&risk_level=High")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["risk_level"], "High")
        self.assertIn("recommended_shelter", payload)
        self.assertIn("travel_advice", payload)

    def test_safe_route_prefers_same_state_shelters(self):
        self.login_session()

        response = self.client.get("/api/safe-route?location=Erode, Tamil Nadu&risk_level=Moderate")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["recommended_shelter"]["state"], "Tamil Nadu")

    def test_district_analytics_endpoint_returns_combined_context(self):
        self.login_session()

        response = self.client.get("/api/district-analytics?state=Tamil Nadu&district=Chennai")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("prediction", payload)
        self.assertIn("forecast", payload)
        self.assertIn("safe_route", payload)
        self.assertIn("model_status", payload)


if __name__ == "__main__":
    unittest.main()
