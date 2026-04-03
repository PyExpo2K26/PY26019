import unittest

from app import app


class RouteSmokeTests(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_home_page_loads(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_predict_json_endpoint_returns_prediction(self):
        response = self.client.post(
            "/predict",
            json={"rainfall": 25, "water_level": 2.0, "flow_rate": 100},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["success"])
        self.assertIn("risk_level", payload)

    def test_public_realtime_endpoint_returns_data(self):
        response = self.client.get("/api/public-realtime-data")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("prediction", payload)
        self.assertIn("rainfall", payload)

    def test_protected_api_requires_login(self):
        response = self.client.get("/api/realtime-data")
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
